# Beverage Demand Forecasting — AIO Session II, Problems & Exercises 2

**Rakshanda Dhote** | SP Jain MAIB | AI in Operations (Dr. Sandip Kumar Roy) | Nov 2026

End-to-end monthly demand forecasting pipeline with **four models** (Naive, ARIMA, Random Forest, XGBoost), **MAPE + WAPE** evaluation, a **3-month-ahead forecast**, and an **LLM-generated business interpretation** — surfaced as a standalone HTML dashboard.

Addresses PPT pages 65–66 (Session II lab exercise) and implements the LLM-interpretation requirement referenced to Day 10 of RDMU.

---

## What's in this folder

| File | What it is |
|---|---|
| `beverage_forecasting.ipynb` | Fully-executed Jupyter notebook — every chart and output baked in. Open it to read the analysis as a story. |
| `dashboard.html` | Standalone interactive dashboard. **Just double-click to open it in a browser** — no server needed, Plotly.js is inlined. |
| `pipeline.py` | The forecasting + LLM pipeline as reusable Python. Importable from the notebook; also runnable from the CLI (`python pipeline.py`). |
| `results.json` | The notebook's output, consumed by the dashboard. Regenerated on every notebook run. |
| `champagne_sales.csv` | Public dataset — Perrin-Freres monthly champagne sales (1964-01 → 1972-09). See "Dataset" below. |
| `requirements.txt` | Pinned Python dependencies. |
| `Dockerfile` | One-command reproducibility. |

---

## Quick start — three options

### Option A — just see the dashboard (zero setup)
Double-click `dashboard.html`. It opens in your browser with all charts, metrics, and the LLM interpretation already rendered. No server, no Python, no network.

### Option B — rerun the notebook locally
```bash
pip install -r requirements.txt
jupyter notebook beverage_forecasting.ipynb
```
Run all cells. The last cell writes a fresh `results.json`; refresh `dashboard.html` to see it.

To get a **real Claude-generated** interpretation instead of the template fallback:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
jupyter notebook beverage_forecasting.ipynb
```
The pipeline detects the env var and calls Anthropic's API (model: `claude-sonnet-4-5`). Without the key it falls back to a deterministic template that still reads cleanly — the dashboard works either way.

### Option C — Docker (fully reproducible)
```bash
docker build -t beverage-forecast .
docker run -p 8888:8888 -p 8000:8000 \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  beverage-forecast
```
Then:
- Jupyter at **http://localhost:8888**
- Dashboard at **http://localhost:8000/dashboard.html**

---

## Dataset

The exercise frames this as a new flavored-water product with its first year of monthly sales. For a proper multi-cycle backtest the pipeline uses the **Perrin-Freres monthly champagne sales** dataset — a classic public monthly beverage series (105 months, strong seasonality, Jan 1964 → Sep 1972) — as the stand-in historical series.

The pipeline is dataset-agnostic: swap `champagne_sales.csv` for any `Month,Sales` CSV (monthly frequency) and everything downstream re-runs unchanged.

---

## Models

| Model | What it does |
|---|---|
| **Naive** | Last-month shift — the required baseline from the PPT demo (page 61). |
| **ARIMA** | SARIMA with order picked by AIC grid search over (p,d,q)×(P,1,Q,12). |
| **Random Forest** | 400 trees, depth 8 — classic ML with lag features (Lag1, Lag2, Lag3, Lag12, rolling means, calendar). |
| **XGBoost** | 500 rounds, lr 0.05, depth 5 — gradient-boosted alternative on the same features. |

Each is evaluated on a **12-month hold-out** with **MAPE** and **WAPE**, then retrained on the full history to forecast 3 months ahead.

---

## Results summary (on this dataset)

| Model | MAPE | WAPE | MAE |
|---|---:|---:|---:|
| Naive | 52.21% | 38.47% | 2,190 |
| **ARIMA ★** | **10.71%** | **8.44%** | **481** |
| Random Forest | 10.40% | 8.83% | 503 |
| XGBoost | 12.76% | 9.80% | 558 |

Best model by WAPE: **ARIMA** — see the dashboard's LLM Interpretation card for the "why".

---

## Design choices

1. **Dashboard, not Streamlit.** `dashboard.html` is a single self-contained HTML file with Plotly.js inlined. No server to run, no port to open, no Python at view time. Same file works from `file://`, from `python -m http.server`, or from Docker.
2. **LLM = real API call + safe fallback.** The pipeline builds a structured JSON-schema prompt from the live metrics and calls Anthropic's Claude API when `ANTHROPIC_API_KEY` is set. When it isn't, a deterministic template using the same numbers runs — so the dashboard never has an empty "Interpretation" section during grading.
3. **Recursive tree forecasting.** For multi-step ahead, RF and XGBoost feed their own predictions back into Lag1/Lag2/Lag3 for the next step. Honestly flagged in the LLM's "risks" output.
4. **WAPE first.** The dashboard highlights WAPE as the primary selection metric because it's revenue-weighted — operationally the right choice when a 10% error on the December peak costs the same as a 70% error on a quiet month.

---

## File flow

```
champagne_sales.csv ──► beverage_forecasting.ipynb ──► results.json ──► dashboard.html
                                   │
                                   └── pipeline.py (shared code, LLM call)
```

Edit the notebook, run all cells, refresh the dashboard. That's the loop.
