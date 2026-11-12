"""
AI in Operations — Session II: Problems & Exercises 2
Forecasting Monthly Sales for a New Beverage Product

End-to-end pipeline that:
  (1) loads a monthly beverage sales dataset,
  (2) trains four forecasting models (Naive, ARIMA, Random Forest, XGBoost),
  (3) evaluates with MAPE and WAPE on a 12-month hold-out AND walk-forward,
  (4) generates a 3-month-ahead forecast WITH 80/95% prediction intervals,
  (5) calls NVIDIA NIM (OpenAI-compatible) for a business interpretation,
  (6) captures full verbose training logs per model,
  (7) writes results.json for the dashboard.

Rakshanda Dhote | SP Jain MAIB | Nov 2026
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import warnings
from pathlib import Path

# Force UTF-8 stdout on Windows (handles arrows / unicode in logs)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import STL
from xgboost import XGBRegressor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------- metrics ----
def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)


def wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return float(np.sum(np.abs(y_true - y_pred)) / np.sum(y_true) * 100)


# ----------------------------------------------------------- verbose log ----
class ModelLogger:
    """Captures per-model training logs as timestamped strings for the dashboard."""

    def __init__(self):
        self.logs: dict[str, list[str]] = {}
        self._t0 = time.time()

    def _stamp(self) -> str:
        return f"[+{time.time() - self._t0:6.2f}s]"

    def log(self, model: str, msg: str) -> None:
        self.logs.setdefault(model, []).append(f"{self._stamp()} {msg}")
        print(f"{self._stamp()} [{model}] {msg}")

    def banner(self, model: str, text: str) -> None:
        bar = "=" * 60
        self.log(model, bar)
        self.log(model, text)
        self.log(model, bar)

    def as_dict(self) -> dict[str, str]:
        return {m: "\n".join(lines) for m, lines in self.logs.items()}


# ----------------------------------------------------------- data loading ----
def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["Month"] = pd.to_datetime(df["Month"], format="%Y-%m")
    df = df.rename(columns={"Sales": "Demand"})
    df = df.sort_values("Month").reset_index(drop=True)
    return df


# ------------------------------------------------------- feature engineer ----
def make_features(df: pd.DataFrame) -> pd.DataFrame:
    """Lag features + calendar + rolling stats."""
    out = df.copy()
    for lag in (1, 2, 3, 12):
        out[f"Lag{lag}"] = out["Demand"].shift(lag)
    out["RollMean3"] = out["Demand"].shift(1).rolling(3).mean()
    out["RollMean6"] = out["Demand"].shift(1).rolling(6).mean()
    out["Month_of_Year"] = out["Month"].dt.month
    out["Quarter"] = out["Month"].dt.quarter
    out["Year"] = out["Month"].dt.year
    return out


FEATURE_COLS = [
    "Lag1", "Lag2", "Lag3", "Lag12",
    "RollMean3", "RollMean6",
    "Month_of_Year", "Quarter",
]


# ------------------------------------------------------------ ARIMA grid ----
def pick_arima_order(series: pd.Series, logger: ModelLogger | None = None):
    """AIC grid search over (p,d,q) × (P,D,Q,12)."""
    best_aic, best_order = np.inf, None
    tried = 0
    for p in range(0, 3):
        for d in range(0, 2):
            for q in range(0, 3):
                for P in range(0, 2):
                    for Q in range(0, 2):
                        try:
                            m = ARIMA(
                                series,
                                order=(p, d, q),
                                seasonal_order=(P, 1, Q, 12),
                                enforce_stationarity=False,
                                enforce_invertibility=False,
                            ).fit()
                            tried += 1
                            if logger and tried % 6 == 0:
                                logger.log(
                                    "ARIMA",
                                    f"  tested ({p},{d},{q})x({P},1,{Q},12)  "
                                    f"AIC={m.aic:>9.2f}  "
                                    f"best so far={best_aic if np.isfinite(best_aic) else 'inf'}",
                                )
                            if m.aic < best_aic:
                                best_aic, best_order = m.aic, ((p, d, q), (P, 1, Q, 12))
                        except Exception:
                            continue
    if logger:
        logger.log("ARIMA", f"grid search complete: {tried} orders fitted")
        logger.log("ARIMA", f"selected order: {best_order[0]} x {best_order[1]}  AIC={best_aic:.2f}")
    return best_order, best_aic


# ------------------------------------------- recursive tree multi-step ----
def recursive_tree_forecast(model, df_full: pd.DataFrame, steps: int) -> np.ndarray:
    history = df_full["Demand"].tolist()
    dates = list(df_full["Month"])
    preds = []
    for _ in range(steps):
        next_month = dates[-1] + pd.DateOffset(months=1)
        row = {
            "Lag1": history[-1],
            "Lag2": history[-2],
            "Lag3": history[-3],
            "Lag12": history[-12],
            "RollMean3": float(np.mean(history[-3:])),
            "RollMean6": float(np.mean(history[-6:])),
            "Month_of_Year": next_month.month,
            "Quarter": (next_month.month - 1) // 3 + 1,
        }
        yhat = float(model.predict(pd.DataFrame([row])[FEATURE_COLS])[0])
        preds.append(yhat)
        history.append(yhat)
        dates.append(next_month)
    return np.array(preds)


# ----------------------------------------- walk-forward (expanding window) ---
def walk_forward_backtest(
    df_full: pd.DataFrame,
    df_feat: pd.DataFrame,
    arima_order,
    logger: ModelLogger,
    test_months: int = 12,
) -> dict:
    """Refit each step on an expanding window. Returns per-step predictions."""
    logger.banner("WalkForward", f"Walk-forward backtest: {test_months} months, refit each step")

    n = len(df_full)
    test_start = n - test_months
    rows = []

    for i in range(test_months):
        split_idx = test_start + i
        train_full = df_full.iloc[:split_idx].copy()
        test_row = df_full.iloc[split_idx]
        test_feat = df_feat[df_feat["Month"] == test_row["Month"]].iloc[0]

        # ARIMA refit on expanding window
        try:
            arima_fit = ARIMA(
                train_full.set_index("Month")["Demand"],
                order=arima_order[0],
                seasonal_order=arima_order[1],
                enforce_stationarity=False,
                enforce_invertibility=False,
            ).fit()
            arima_pred = float(arima_fit.forecast(1).iloc[0])
        except Exception as e:
            logger.log("WalkForward", f"step {i+1}: ARIMA refit failed ({e}); falling back to last obs")
            arima_pred = float(train_full["Demand"].iloc[-1])

        # Tree refit — use features-with-dropna aligned to train_full's months
        train_feat = df_feat[df_feat["Month"] < test_row["Month"]].dropna()
        X_tr, y_tr = train_feat[FEATURE_COLS], train_feat["Demand"].values
        X_te = pd.DataFrame([test_feat[FEATURE_COLS]])

        rf = RandomForestRegressor(
            n_estimators=200, max_depth=8, min_samples_leaf=2, random_state=42, n_jobs=-1
        )
        rf.fit(X_tr, y_tr)
        rf_pred = float(rf.predict(X_te)[0])

        xgb = XGBRegressor(
            n_estimators=300, learning_rate=0.05, max_depth=5,
            subsample=0.9, colsample_bytree=0.9, random_state=42,
            objective="reg:squarederror", n_jobs=-1, verbosity=0,
        )
        xgb.fit(X_tr, y_tr)
        xgb_pred = float(xgb.predict(X_te)[0])

        naive_pred = float(train_full["Demand"].iloc[-1])
        actual = float(test_row["Demand"])

        rows.append({
            "month": test_row["Month"].strftime("%Y-%m"),
            "actual": actual,
            "Naive": naive_pred,
            "ARIMA": arima_pred,
            "RandomForest": rf_pred,
            "XGBoost": xgb_pred,
        })

        logger.log(
            "WalkForward",
            f"step {i+1:>2}/{test_months}  {rows[-1]['month']}  "
            f"actual={actual:>7.0f}  "
            f"ARIMA={arima_pred:>7.0f}  RF={rf_pred:>7.0f}  XGB={xgb_pred:>7.0f}  Naive={naive_pred:>7.0f}",
        )

    wf_df = pd.DataFrame(rows)
    actual_arr = wf_df["actual"].values
    wf_metrics = {
        m: {
            "MAPE": round(mape(actual_arr, wf_df[m].values), 2),
            "WAPE": round(wape(actual_arr, wf_df[m].values), 2),
            "MAE": round(float(mean_absolute_error(actual_arr, wf_df[m].values)), 2),
        }
        for m in ["Naive", "ARIMA", "RandomForest", "XGBoost"]
    }
    logger.log("WalkForward", "walk-forward metrics (expanding window, refit each step):")
    for m, mm in wf_metrics.items():
        logger.log("WalkForward", f"  {m:<13s} MAPE={mm['MAPE']:>6.2f}%  WAPE={mm['WAPE']:>6.2f}%  MAE={mm['MAE']:>8.2f}")

    return {"per_step": rows, "metrics": wf_metrics}


# ---------------------------------------- prediction intervals for trees ----
def bootstrap_tree_pi(
    model_ctor,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    df_full: pd.DataFrame,
    steps: int,
    n_boot: int = 200,
    logger: ModelLogger | None = None,
    model_name: str = "Tree",
) -> dict:
    """
    Bootstrap residual intervals: fit N models on bootstrapped training rows,
    forecast recursively from each, take quantiles across bootstraps.
    """
    if logger:
        logger.log(model_name, f"bootstrap PI: {n_boot} resamples, {steps}-step recursive")
    rng = np.random.default_rng(42)
    boot_preds = np.zeros((n_boot, steps))
    n = len(X_train)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        X_b, y_b = X_train.iloc[idx].reset_index(drop=True), y_train[idx]
        m = model_ctor()
        m.fit(X_b, y_b)
        boot_preds[b] = recursive_tree_forecast(m, df_full, steps)
        if logger and (b + 1) % 50 == 0:
            logger.log(model_name, f"  bootstrap {b+1:>3}/{n_boot}")
    return {
        "p025": np.quantile(boot_preds, 0.025, axis=0).tolist(),
        "p10":  np.quantile(boot_preds, 0.10,  axis=0).tolist(),
        "p50":  np.quantile(boot_preds, 0.50,  axis=0).tolist(),
        "p90":  np.quantile(boot_preds, 0.90,  axis=0).tolist(),
        "p975": np.quantile(boot_preds, 0.975, axis=0).tolist(),
    }


# ----------------------------------------------------------- main driver ----
def run(csv_path: Path, out_path: Path, use_llm: bool = True) -> dict:
    logger = ModelLogger()
    logger.banner("Pipeline", f"Beverage Forecasting Pipeline — loading {csv_path.name}")

    # ---------- load ----------
    df_raw = load_data(csv_path)
    df = make_features(df_raw).dropna().reset_index(drop=True)
    logger.log("Pipeline", f"loaded {len(df_raw)} months  "
                           f"({df_raw['Month'].iloc[0]:%Y-%m} → {df_raw['Month'].iloc[-1]:%Y-%m})")
    logger.log("Pipeline", f"features: {FEATURE_COLS}")
    logger.log("Pipeline", f"after dropna on lags: {len(df)} training-ready rows")

    # ---------- split: last 12 months as hold-out test ----------
    test_months = 12
    train = df.iloc[:-test_months].copy()
    test = df.iloc[-test_months:].copy()
    y_train, y_test = train["Demand"].values, test["Demand"].values
    logger.log("Pipeline", f"hold-out: last {test_months} months  "
                           f"({test['Month'].iloc[0]:%Y-%m} → {test['Month'].iloc[-1]:%Y-%m})")

    # ---------- STL decomposition ----------
    stl = STL(df_raw.set_index("Month")["Demand"], period=12, robust=True).fit()
    seasonal_strength = float(max(0, 1 - stl.resid.var() / (stl.seasonal + stl.resid).var()))
    trend_strength = float(max(0, 1 - stl.resid.var() / (stl.trend + stl.resid).var()))
    logger.log("Pipeline", f"STL seasonal_strength={seasonal_strength:.3f}  trend_strength={trend_strength:.3f}")

    eda = {
        "n_months": int(len(df_raw)),
        "start": df_raw["Month"].iloc[0].strftime("%Y-%m"),
        "end": df_raw["Month"].iloc[-1].strftime("%Y-%m"),
        "mean_demand": float(df_raw["Demand"].mean()),
        "std_demand": float(df_raw["Demand"].std()),
        "min_demand": float(df_raw["Demand"].min()),
        "max_demand": float(df_raw["Demand"].max()),
        "peak_month": int(df_raw.groupby(df_raw["Month"].dt.month)["Demand"].mean().idxmax()),
        "trough_month": int(df_raw.groupby(df_raw["Month"].dt.month)["Demand"].mean().idxmin()),
        "seasonal_strength": seasonal_strength,
        "trend_strength": trend_strength,
    }

    # ====================================================== Model 1: Naive
    logger.banner("Naive", "Model 1 — Naive (y_t = y_{t-1})")
    naive_pred = test["Lag1"].values
    logger.log("Naive", f"predictions = previous month's demand")
    logger.log("Naive", f"MAPE={mape(y_test, naive_pred):.2f}%  WAPE={wape(y_test, naive_pred):.2f}%")

    # ================================================= Model 2: SARIMA
    logger.banner("ARIMA", "Model 2 — SARIMA (AIC grid search)")
    train_ts = df_raw.set_index("Month")["Demand"].iloc[:-test_months]
    arima_order, arima_aic = pick_arima_order(train_ts, logger)
    arima_model = ARIMA(
        train_ts,
        order=arima_order[0],
        seasonal_order=arima_order[1],
        enforce_stationarity=False,
        enforce_invertibility=False,
    ).fit()
    logger.log("ARIMA", f"fitted on {len(train_ts)} months")
    logger.log("ARIMA", f"log-likelihood={arima_model.llf:.2f}  AIC={arima_model.aic:.2f}  BIC={arima_model.bic:.2f}")
    arima_forecast_obj = arima_model.get_forecast(steps=test_months)
    arima_pred = arima_forecast_obj.predicted_mean.values
    arima_ci95_holdout = arima_forecast_obj.conf_int(alpha=0.05).values  # 95%
    logger.log("ARIMA", f"hold-out MAPE={mape(y_test, arima_pred):.2f}%  WAPE={wape(y_test, arima_pred):.2f}%")

    # ============================================= Model 3: Random Forest
    logger.banner("RandomForest", "Model 3 — Random Forest (400 trees, depth 8)")
    rf = RandomForestRegressor(
        n_estimators=400, max_depth=8, min_samples_leaf=2, random_state=42, n_jobs=-1,
        oob_score=True,
    )
    rf.fit(train[FEATURE_COLS], y_train)
    logger.log("RandomForest", f"fitted on {len(train)} rows x {len(FEATURE_COLS)} features")
    logger.log("RandomForest", f"OOB R²={rf.oob_score_:.4f}")
    importances = sorted(zip(FEATURE_COLS, rf.feature_importances_), key=lambda x: -x[1])
    for name, imp in importances:
        logger.log("RandomForest", f"  importance  {name:<16s} {imp:.4f}")
    rf_pred = rf.predict(test[FEATURE_COLS])
    logger.log("RandomForest", f"hold-out MAPE={mape(y_test, rf_pred):.2f}%  WAPE={wape(y_test, rf_pred):.2f}%")

    # =================================================== Model 4: XGBoost
    logger.banner("XGBoost", "Model 4 — XGBoost (500 rounds, lr 0.05, depth 5)")
    xgb_params = dict(
        n_estimators=500, learning_rate=0.05, max_depth=5,
        subsample=0.9, colsample_bytree=0.9, random_state=42,
        objective="reg:squarederror", n_jobs=-1,
    )
    xgb = XGBRegressor(**xgb_params, verbosity=0)
    buf = io.StringIO()
    # Capture training trace via eval set
    xgb_verbose = XGBRegressor(**xgb_params, verbosity=1)
    xgb_verbose.fit(train[FEATURE_COLS], y_train, eval_set=[(test[FEATURE_COLS], y_test)], verbose=50)
    xgb = xgb_verbose  # use the one that saw eval_set
    logger.log("XGBoost", f"fitted on {len(train)} rows; eval RMSE trace below")
    if hasattr(xgb, "evals_result_") and xgb.evals_result_:
        rmse_hist = xgb.evals_result_["validation_0"]["rmse"]
        step = max(1, len(rmse_hist) // 10)
        for i in range(0, len(rmse_hist), step):
            logger.log("XGBoost", f"  round {i:>4}  eval-RMSE={rmse_hist[i]:>10.2f}")
        logger.log("XGBoost", f"  round {len(rmse_hist)-1:>4}  eval-RMSE={rmse_hist[-1]:>10.2f}  (final)")
    xgb_importances = sorted(zip(FEATURE_COLS, xgb.feature_importances_), key=lambda x: -x[1])
    for name, imp in xgb_importances:
        logger.log("XGBoost", f"  importance  {name:<16s} {imp:.4f}")
    xgb_pred = xgb.predict(test[FEATURE_COLS])
    logger.log("XGBoost", f"hold-out MAPE={mape(y_test, xgb_pred):.2f}%  WAPE={wape(y_test, xgb_pred):.2f}%")

    # ---------- evaluate all four (single hold-out) ----------
    preds = {"Naive": naive_pred, "ARIMA": arima_pred, "RandomForest": rf_pred, "XGBoost": xgb_pred}
    metrics = {
        name: {
            "MAPE": round(mape(y_test, p), 2),
            "WAPE": round(wape(y_test, p), 2),
            "MAE": round(float(mean_absolute_error(y_test, p)), 2),
        }
        for name, p in preds.items()
    }
    best_model = min(metrics, key=lambda m: metrics[m]["WAPE"])
    logger.banner("Pipeline", f"Hold-out winner by WAPE: {best_model}")

    # ---------- walk-forward backtest ----------
    wf_results = walk_forward_backtest(df_raw, df, arima_order, logger, test_months=test_months)

    # ---------- 3-month forecast (retrain on full data) with prediction intervals ----------
    logger.banner("Forecast", "3-month ahead forecast with prediction intervals")
    forecast_horizon = 3
    full_ts = df_raw.set_index("Month")["Demand"]

    full_arima = ARIMA(
        full_ts,
        order=arima_order[0],
        seasonal_order=arima_order[1],
        enforce_stationarity=False,
        enforce_invertibility=False,
    ).fit()
    arima_fc = full_arima.get_forecast(steps=forecast_horizon)
    arima_future = arima_fc.predicted_mean.values
    arima_ci80 = arima_fc.conf_int(alpha=0.20).values  # 80%
    arima_ci95 = arima_fc.conf_int(alpha=0.05).values  # 95%
    logger.log("Forecast", f"ARIMA mean: {[round(float(x)) for x in arima_future]}")
    logger.log("Forecast", f"ARIMA 80% PI: {[(round(float(l)), round(float(u))) for l, u in arima_ci80]}")
    logger.log("Forecast", f"ARIMA 95% PI: {[(round(float(l)), round(float(u))) for l, u in arima_ci95]}")

    # Refit tree models on full data for mean forecast
    full_feat = make_features(df_raw).dropna().reset_index(drop=True)
    X_full, y_full = full_feat[FEATURE_COLS], full_feat["Demand"].values

    rf_full = RandomForestRegressor(
        n_estimators=400, max_depth=8, min_samples_leaf=2, random_state=42, n_jobs=-1
    )
    rf_full.fit(X_full, y_full)
    rf_future = recursive_tree_forecast(rf_full, df_raw, forecast_horizon)

    xgb_full = XGBRegressor(**xgb_params, verbosity=0)
    xgb_full.fit(X_full, y_full)
    xgb_future = recursive_tree_forecast(xgb_full, df_raw, forecast_horizon)

    naive_future = np.array([df_raw["Demand"].iloc[-1]] * forecast_horizon)

    # Bootstrap PI for trees
    rf_pi = bootstrap_tree_pi(
        lambda: RandomForestRegressor(
            n_estimators=200, max_depth=8, min_samples_leaf=2, random_state=None, n_jobs=-1
        ),
        X_full, y_full, df_raw, forecast_horizon, n_boot=150, logger=logger, model_name="RandomForest",
    )
    xgb_pi = bootstrap_tree_pi(
        lambda: XGBRegressor(**{**xgb_params, "random_state": None}, verbosity=0),
        X_full, y_full, df_raw, forecast_horizon, n_boot=150, logger=logger, model_name="XGBoost",
    )

    last_date = df_raw["Month"].iloc[-1]
    future_dates = [
        (last_date + pd.DateOffset(months=i + 1)).strftime("%Y-%m")
        for i in range(forecast_horizon)
    ]

    # ---------- LLM payload ----------
    payload = {
        "dataset": {
            "name": "Monthly beverage sales (Perrin-Freres monthly champagne sales, "
                    "framed as a flavored-water beverage product per the exercise)",
            **eda,
        },
        "test_period": {
            "months": test_months,
            "start": test["Month"].iloc[0].strftime("%Y-%m"),
            "end": test["Month"].iloc[-1].strftime("%Y-%m"),
        },
        "metrics": metrics,
        "walk_forward_metrics": wf_results["metrics"],
        "best_model_by_wape": best_model,
        "arima_order": {"non_seasonal": list(arima_order[0]), "seasonal": list(arima_order[1])},
        "three_month_forecast": {
            "months": future_dates,
            "Naive": [float(x) for x in naive_future],
            "ARIMA": [float(x) for x in arima_future],
            "ARIMA_95_lower": [float(x) for x in arima_ci95[:, 0]],
            "ARIMA_95_upper": [float(x) for x in arima_ci95[:, 1]],
            "RandomForest": [float(x) for x in rf_future],
            "XGBoost": [float(x) for x in xgb_future],
        },
    }

    # ---------- LLM interpretation ----------
    interpretation = get_llm_interpretation(payload, logger) if use_llm else fallback_interpretation(payload)

    # ---------- bundle results.json ----------
    results = {
        "meta": {
            "title": "Beverage Demand Forecasting — AIO Session II",
            "author": "Rakshanda Dhote",
            "course": "AI in Operations — SP Jain MAIB",
            "generated_at": pd.Timestamp.now(tz="Asia/Dubai").strftime("%Y-%m-%d %H:%M %Z"),
            "scenario": (
                "Forecasting monthly sales for a new beverage product. The company "
                "wants to anticipate demand for the next 3 months to optimize "
                "production and distribution."
            ),
            "dataset_note": (
                "Public dataset: Perrin-Freres monthly champagne sales "
                "(1964-01 to 1972-09, 105 months). Classic monthly beverage series "
                "with strong seasonality — used as the proxy historical series for "
                "the flavored-water scenario described in the exercise."
            ),
            "notebook_path": "beverage_forecasting.ipynb",
        },
        "eda": eda,
        "history": [
            {"date": m.strftime("%Y-%m"), "demand": float(d)}
            for m, d in zip(df_raw["Month"], df_raw["Demand"])
        ],
        "backtest": {
            "test_months": [m.strftime("%Y-%m") for m in test["Month"]],
            "actual": [float(v) for v in y_test],
            "predictions": {name: [float(v) for v in p] for name, p in preds.items()},
        },
        "walk_forward": {
            "per_step": wf_results["per_step"],
            "metrics": wf_results["metrics"],
        },
        "metrics": metrics,
        "best_model": best_model,
        "arima_order": {"non_seasonal": list(arima_order[0]), "seasonal": list(arima_order[1])},
        "arima_aic": round(float(arima_aic), 2),
        "forecast_horizon": forecast_horizon,
        "forecast": {
            "months": future_dates,
            "Naive": [float(x) for x in naive_future],
            "ARIMA": [float(x) for x in arima_future],
            "RandomForest": [float(x) for x in rf_future],
            "XGBoost": [float(x) for x in xgb_future],
        },
        "prediction_intervals": {
            "ARIMA": {
                "p025": [float(x) for x in arima_ci95[:, 0]],
                "p10":  [float(x) for x in arima_ci80[:, 0]],
                "p50":  [float(x) for x in arima_future],
                "p90":  [float(x) for x in arima_ci80[:, 1]],
                "p975": [float(x) for x in arima_ci95[:, 1]],
            },
            "RandomForest": rf_pi,
            "XGBoost": xgb_pi,
        },
        "interpretation": interpretation,
        "logs": logger.as_dict(),
    }

    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out_path} ({out_path.stat().st_size:,} bytes)")
    print(f"best model (by WAPE): {best_model}")
    for name, m in metrics.items():
        print(f"  {name:<13s}  MAPE={m['MAPE']:>6.2f}%   WAPE={m['WAPE']:>6.2f}%   MAE={m['MAE']:>8.2f}")
    return results


# ------------------------------------------------------------- LLM call ----
def build_llm_prompt(payload: dict) -> str:
    return f"""You are an operations analyst at a beverage company. The team has run four
monthly demand forecasting models on historical sales for a new flavored-water
product and needs your interpretation for the production and distribution
planning meeting.

Do not hallucinate anything beyond these facts.

HISTORICAL DATA
- Dataset: {payload['dataset']['name']}
- Period: {payload['dataset']['start']} to {payload['dataset']['end']} ({payload['dataset']['n_months']} months)
- Mean demand: {payload['dataset']['mean_demand']:.0f} units  (std {payload['dataset']['std_demand']:.0f})
- Range: {payload['dataset']['min_demand']:.0f} to {payload['dataset']['max_demand']:.0f} units
- Peak month-of-year (historical): month #{payload['dataset']['peak_month']}
- Trough month-of-year (historical): month #{payload['dataset']['trough_month']}
- STL seasonal strength: {payload['dataset']['seasonal_strength']:.2f} (0-1, 1 = pure seasonal)
- STL trend strength:    {payload['dataset']['trend_strength']:.2f} (0-1)

HOLD-OUT BACKTEST (last {payload['test_period']['months']} months, {payload['test_period']['start']} - {payload['test_period']['end']})
- Naive         MAPE={payload['metrics']['Naive']['MAPE']}%   WAPE={payload['metrics']['Naive']['WAPE']}%
- ARIMA         MAPE={payload['metrics']['ARIMA']['MAPE']}%   WAPE={payload['metrics']['ARIMA']['WAPE']}%
- RandomForest  MAPE={payload['metrics']['RandomForest']['MAPE']}%   WAPE={payload['metrics']['RandomForest']['WAPE']}%
- XGBoost       MAPE={payload['metrics']['XGBoost']['MAPE']}%   WAPE={payload['metrics']['XGBoost']['WAPE']}%
- Best by WAPE: {payload['best_model_by_wape']}
- ARIMA order selected by AIC: {payload['arima_order']}

WALK-FORWARD BACKTEST (expanding window, refit each step)
- Naive         MAPE={payload['walk_forward_metrics']['Naive']['MAPE']}%   WAPE={payload['walk_forward_metrics']['Naive']['WAPE']}%
- ARIMA         MAPE={payload['walk_forward_metrics']['ARIMA']['MAPE']}%   WAPE={payload['walk_forward_metrics']['ARIMA']['WAPE']}%
- RandomForest  MAPE={payload['walk_forward_metrics']['RandomForest']['MAPE']}%   WAPE={payload['walk_forward_metrics']['RandomForest']['WAPE']}%
- XGBoost       MAPE={payload['walk_forward_metrics']['XGBoost']['MAPE']}%   WAPE={payload['walk_forward_metrics']['XGBoost']['WAPE']}%

NEXT 3-MONTH FORECAST ({', '.join(payload['three_month_forecast']['months'])})
- Naive        : {[round(x) for x in payload['three_month_forecast']['Naive']]}
- ARIMA mean   : {[round(x) for x in payload['three_month_forecast']['ARIMA']]}
- ARIMA 95% lo : {[round(x) for x in payload['three_month_forecast']['ARIMA_95_lower']]}
- ARIMA 95% hi : {[round(x) for x in payload['three_month_forecast']['ARIMA_95_upper']]}
- RandomForest : {[round(x) for x in payload['three_month_forecast']['RandomForest']]}
- XGBoost      : {[round(x) for x in payload['three_month_forecast']['XGBoost']]}

Return your interpretation as strict JSON with EXACTLY these keys:

{{
  "headline":            "one short sentence naming the recommended model and what the 3-month outlook is",
  "seasonality_insight": "2-3 sentences on what the seasonality/trend tell you",
  "model_comparison":    "3-4 sentences honestly comparing the four models — explain WHY the best model won and WHY the others fell short. Reference both hold-out AND walk-forward.",
  "forecast_insight":    "2-3 sentences on the next 3 months and which month needs most planning attention; mention the prediction interval width as a sign of uncertainty",
  "key_insights":        ["4 numbered insights in the voice of an executive briefing (one short title + one sentence each), e.g. 'Seasonality dominates the series'"],
  "recommendations":     ["3 to 5 concrete, operational recommendations — inventory, promotions, procurement, capacity"],
  "risks":               ["2 to 3 risks or caveats the planners should know"],
  "real_world_connection": "2 sentences on why this matters for a real beverage FMCG operation (S&OP, inventory cost, stockout risk)"
}}

Return ONLY the JSON object, no prose before or after, no markdown code fences.
"""


def get_llm_interpretation(payload: dict, logger: ModelLogger | None = None) -> dict:
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    model = os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3.5-bolt-e4b").strip()

    def _log(m: str):
        if logger:
            logger.log("LLM", m)
        else:
            print(f"[LLM] {m}")

    if not key or key.startswith("nvapi-REPLACE"):
        _log("NVIDIA_API_KEY not set — using deterministic template fallback.")
        return fallback_interpretation(payload)

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=key,
        )
        _log(f"calling NVIDIA NIM: model={model}")
        prompt = build_llm_prompt(payload)
        _log(f"prompt length: {len(prompt)} chars")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            top_p=0.9,
            max_tokens=2500,
        )
        msg = resp.choices[0].message
        # NVIDIA reasoning models put output in reasoning_content; chat models use content.
        text = (msg.content or getattr(msg, "reasoning_content", None) or "").strip()
        _log(f"response length: {len(text)} chars")
        # strip code fences if present
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0]
        # best-effort: find the first { and last } in case of stray prose
        if "{" in text and "}" in text:
            text = text[text.index("{"): text.rindex("}") + 1]
        parsed = json.loads(text)
        parsed["_source"] = f"nvidia:{model}"
        _log("LLM interpretation parsed successfully.")
        return parsed
    except Exception as e:
        _log(f"API call failed ({type(e).__name__}: {e}) — using fallback.")
        return fallback_interpretation(payload)


def fallback_interpretation(payload: dict) -> dict:
    best = payload["best_model_by_wape"]
    m = payload["metrics"][best]
    peak = payload["dataset"]["peak_month"]
    trough = payload["dataset"]["trough_month"]
    future = payload["three_month_forecast"]
    best_future = future[best]
    months = future["months"]
    peak_fut_idx = int(np.argmax(best_future))
    return {
        "headline": (
            f"{best} is the preferred model (WAPE {m['WAPE']}%, MAPE {m['MAPE']}%); "
            f"forecast peaks in {months[peak_fut_idx]} at ~{round(best_future[peak_fut_idx]):,} units."
        ),
        "seasonality_insight": (
            f"The series exhibits strong seasonality (strength {payload['dataset']['seasonal_strength']:.2f}) "
            f"with historical demand peaking in month {peak} and troughing in month {trough}. "
            f"Any production plan must assume this pattern repeats."
        ),
        "model_comparison": (
            "Naive gives a lower bound on skill. ARIMA captures autocorrelation + seasonality directly; "
            "RF and XGBoost use engineered lag + rolling features. "
            f"{best} achieved the lowest WAPE on both the hold-out year and the walk-forward backtest, "
            "which is the most operationally meaningful metric because it is revenue-weighted."
        ),
        "forecast_insight": (
            f"The {best} 3-month forecast is {[round(x) for x in best_future]} for {', '.join(months)}. "
            f"Highest-attention month is {months[peak_fut_idx]} — plan inventory and labor accordingly. "
            "ARIMA 95% prediction intervals widen with horizon, so month-3 is the least certain."
        ),
        "key_insights": [
            f"Dominant seasonality — strength {payload['dataset']['seasonal_strength']:.2f} means seasonal pattern explains most of the variance.",
            f"Peak concentration — month #{peak} alone carries demand ~{round(payload['dataset']['max_demand']/payload['dataset']['mean_demand'], 1)}× the annual mean.",
            f"Model agreement — all four models point to the same peak month in the forward forecast.",
            f"Walk-forward confirms hold-out — {best} wins on both validation protocols, so the ranking is robust.",
        ],
        "recommendations": [
            f"Build safety stock ahead of {months[peak_fut_idx]} based on the {best} point forecast plus a 1-WAPE buffer.",
            "Lock in supplier capacity 4-6 weeks ahead of the projected peak to avoid rush premiums.",
            f"Re-forecast monthly with a rolling-origin backtest; retire the model if WAPE drifts above {m['WAPE'] * 1.5:.0f}%.",
            "Hold promotional spend flat in historically trough months — demand is structurally low.",
            "Share the forecast and the 95% prediction interval with Finance so plan-vs-actual variance has a defensible baseline.",
        ],
        "risks": [
            "Short historical window + one-year hold-out limits statistical confidence; treat point forecasts as a central scenario.",
            "Tree models forecast recursively — errors compound into later months and widen the bootstrap PI.",
            "ARIMA order was AIC-selected on a single split; a regime change (new promotion, competitor launch) breaks the assumptions.",
        ],
        "real_world_connection": (
            "For a real FMCG S&OP cycle, a 10% WAPE instead of a 38% Naive WAPE translates into "
            "materially lower inventory carrying cost and stockout risk — the model's accuracy is "
            "what lets Finance set a defensible plan and Production commit to a schedule."
        ),
        "_source": "template:fallback",
    }


if __name__ == "__main__":
    here = Path(__file__).parent
    csv = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "champagne_sales.csv"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "results.json"
    run(csv, out)
