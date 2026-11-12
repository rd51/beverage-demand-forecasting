# Beverage Demand Forecasting — AIO Session II, Problems & Exercises 2

**Rakshanda Dhote** | SP Jain MAIB | AI in Operations (Dr. Sandip Kumar Roy) | Nov 2026

End-to-end monthly demand forecasting with **four models** (Naive, SARIMA, Random Forest, XGBoost), **MAPE + WAPE** on both hold-out and walk-forward validation, a **3-month-ahead forecast with 80 / 95% prediction intervals**, an **LLM-authored executive interpretation**, and a live **AI chatbot** grounded in the real metrics — all surfaced in a single-page interactive HTML dashboard with a vertical-tab layout.

Addresses PPT pages 65–66 (Session II lab exercise) and implements the LLM-interpretation requirement referenced to Day 10 of RDMU.

---

## What's in this folder

| File | What it is |
|---|---|
| `dashboard.html` | The deliverable — single-file interactive dashboard (Plotly.js inlined, ~4.9 MB). 8 tabs + AI Chatbot panel. |
| `beverage_forecasting.ipynb` | Fully-executed Jupyter notebook — every chart and output baked in. Open it to read the analysis as a story. |
| `pipeline.py` | Forecasting + LLM pipeline. Importable and runnable (`python pipeline.py`). |
| `build_dashboard.py` | Splices the Plotly bundle + inlined `results.json` into `dashboard.html`. |
| `serve.py` | Local server that hosts the dashboard **and** proxies the chatbot to NVIDIA NIM (keeps the API key off the client). |
| `results.json` | Pipeline output — EDA, metrics, predictions, intervals, logs, LLM output. Consumed by the dashboard. |
| `champagne_sales.csv` | Public dataset — Perrin-Freres monthly champagne sales (1964-01 → 1972-09). See "Dataset" below. |
| `requirements.txt` | Pinned Python dependencies. |
| `.env.example` | Template for the NVIDIA API key — copy to `.env` and paste your key. |
| `CHATBOT_GUIDE.md` | Setup + troubleshooting for the AI Chatbot panel. |
| `PUSH_GUIDE.md` | How to push updates to GitHub from VS Code. |
| `DATASET_SOURCE.md` | Dataset provenance + license note. |
| `Dockerfile` | Optional reproducibility artefact (not needed to use the dashboard). |

---

## Quick start

### Fastest — just view the dashboard

Open `dashboard.html` directly in any browser (double-click, or drag into a browser window). All 8 content tabs work from `file://` — charts, logs, LLM Interpretation, forecast table with PI — everything is self-contained.

The **AI Chatbot** tab will show "server offline" in this mode (it needs `serve.py`); every other tab is fully functional.

### Full experience — including the AI Chatbot

```bash
pip install -r requirements.txt
# Copy .env.example to .env, then paste your free NVIDIA key from build.nvidia.com
python serve.py
```

Then open **http://127.0.0.1:8765/dashboard.html** in a browser. The AI Chatbot panel is now live.

Step-by-step instructions, including where to get a free NVIDIA key, are in [`CHATBOT_GUIDE.md`](CHATBOT_GUIDE.md).

### Rerunning the pipeline from scratch

Needed only if you want to regenerate `results.json` (e.g. after changing the dataset or the LLM model).

```bash
python pipeline.py        # retrains, re-evaluates, re-calls the LLM
python build_dashboard.py # rebuilds dashboard.html from the new results.json
```

Takes ~3 minutes (bootstrap prediction intervals do most of the work).

---

## Dataset

The exercise frames this as a new flavored-water product with its first year of monthly sales. For a proper seasonal backtest the pipeline uses the **Perrin-Freres monthly champagne sales** dataset — a classic public monthly beverage series (105 months, strong seasonality, Jan 1964 → Sep 1972) — as the stand-in historical series.

The pipeline is dataset-agnostic: swap `champagne_sales.csv` for any `Month,Sales` CSV (monthly frequency) and everything downstream re-runs unchanged. See [`DATASET_SOURCE.md`](DATASET_SOURCE.md) for provenance.

---

## Models

| Model | What it does |
|---|---|
| **Naive** | Last-month shift — the required baseline from the PPT demo (page 61). |
| **SARIMA** | Order chosen by AIC grid search over (p,d,q)×(P,1,Q,12). Selected: **(0,1,2)(1,1,1,12)**. |
| **Random Forest** | 400 trees, depth 8, with Lag1/2/3/12, rolling-mean 3 & 6, month, quarter. |
| **XGBoost** | 500 rounds, lr 0.05, depth 5, same feature set. |

Each is evaluated under **two protocols**:
- **Static hold-out** — last 12 months, single train/test split (what the PPT demo uses).
- **Walk-forward** — expanding window, refit each step. This is the honest test for a real forecasting cycle.

The model with the lowest **WAPE** wins (WAPE is revenue-weighted — operationally the right choice when a 10% miss on the December peak costs as much as a 70% miss on a quiet month).

---

## Results

### Hold-out (last 12 months)

| Model | MAPE | WAPE | MAE |
|---|---:|---:|---:|
| Naive | 52.21% | 38.47% | 2,190 |
| **ARIMA ★** | **10.71%** | **8.44%** | **481** |
| Random Forest | 10.40% | 8.83% | 503 |
| XGBoost | 11.37% | 8.92% | 508 |

### Walk-forward (expanding window, refit each step)

| Model | MAPE | WAPE | MAE |
|---|---:|---:|---:|
| Naive | 52.21% | 38.47% | 2,190 |
| **ARIMA ★** | **8.32%** | **6.85%** | **390** |
| Random Forest | 10.32% | 8.53% | 486 |
| XGBoost | 12.66% | 9.54% | 543 |

ARIMA wins on both protocols. Walk-forward gives lower errors across the board — that's the honest view of what to expect in production.

### 3-month forecast (ARIMA, with 95% PI)

| Month | Point | 95% lower | 95% upper |
|---|---:|---:|---:|
| 1972-10 | 7,045 | 5,565 | 8,524 |
| 1972-11 | 10,084 | 8,517 | 11,650 |
| 1972-12 | 13,032 | 11,460 | 14,604 |

---

## LLM integration

Two independent LLM touchpoints, both using NVIDIA NIM's OpenAI-compatible endpoint (free tier at build.nvidia.com), both **grounded** in the real metrics via a structured prompt:

1. **LLM Interpretation card** (static, built at pipeline run time)
   `pipeline.get_llm_interpretation()` builds a JSON-schema prompt from the live payload (EDA + hold-out + walk-forward + forecast + PI + ARIMA order) and calls the model. Output is baked into `results.json` with keys `headline`, `seasonality_insight`, `model_comparison`, `forecast_insight`, `key_insights[]`, `recommendations[]`, `risks[]`, `real_world_connection`. A deterministic template fallback runs when no key is configured, so the card is never empty.

2. **AI Chatbot panel** (live, called per message)
   `serve.py` proxies the browser's `/chat` requests to NVIDIA NIM with the same grounding system prompt. Every answer is forced to cite real numbers only; the model will refuse rather than invent. Conversations are logged to `chatbot_log.jsonl` server-side and surfaced in the dashboard's **Training Logs → Chatbot** sub-tab.

Default model: **`nvidia/nemotron-3.5-bolt-e4b`** — fast, clean JSON output, works on the free tier. Confirmed alternatives, plus the ones NVIDIA has deprecated, are documented in [`CHATBOT_GUIDE.md`](CHATBOT_GUIDE.md) section 6.

---

## Dashboard tour

Vertical-tab layout (left sidebar) — click any tab, or deep-link via `#hash`:

| # | Tab | What's in it |
|---|---|---|
| 01 | Overview | Dataset banner · 4 KPIs · scenario + dataset note |
| 02 | LLM Interpretation | Headline · 4 insight cards · seasonality / model / forecast paragraphs · recommendations · risks · real-world connection |
| 03 | Forecast + PI | History + 3-month forecast chart with 80 / 95% shaded bands · forecast table with PI columns |
| 04 | Hold-out backtest | Last-12-months chart with chip toggles |
| 05 | Walk-forward | Per-step chart, 12 refits |
| 06 | Model comparison | Hold-out + walk-forward tables · MAPE/WAPE bars · feature importance |
| 07 | Training logs | 9 sub-tabs (Pipeline / Naive / ARIMA / RF / XGB / WalkForward / Forecast / LLM / Chatbot) with regex search, copy, download |
| 08 | Methodology | Models · features · validation · PI · LLM details · ARIMA order |
| 💬 | AI Chatbot | Live chat grounded in `results.json` · 5 suggested queries · server-online status · persistent history |

---

## Design choices

1. **Single-file HTML dashboard.** `dashboard.html` inlines Plotly.js and `results.json`. Works from `file://` or a local server; nothing to install at view time.
2. **Two validation protocols.** Hold-out matches the PPT demo; walk-forward is what you'd actually monitor in production. Both are shown so the reader can see the model's ranking is robust.
3. **Prediction intervals, not just point forecasts.** ARIMA uses the Kalman filter forecast covariance (80% and 95%). Tree models use bootstrap resampling (150 resamples, recursive multi-step). Finance can use these for variance planning.
4. **LLM = real API call + safe fallback + chat.** Static interpretation at build time, live chatbot at runtime. Both ground the model with the actual numbers; the fallback template uses the same shape so the UI never breaks.
5. **Server-side API key.** The NVIDIA key lives in `.env` and never reaches the browser. `serve.py` binds to `127.0.0.1` only.
6. **WAPE first.** Highlighted as the primary selection metric because it's revenue-weighted.
7. **Recursive tree forecasting.** For multi-step ahead, RF and XGBoost feed their own predictions back into Lag1/Lag2/Lag3 for the next step. Flagged honestly in the LLM's "risks" output.

---

## File flow

```
champagne_sales.csv
        │
        ▼
   pipeline.py ──────► results.json
   (train + eval          │
    + call LLM)           │
                          ▼
                 build_dashboard.py
                          │
                          ▼
                    dashboard.html  ◄──── serve.py  ◄──── browser (chat)
                    (static view)          (/chat proxy
                                            to NVIDIA)
```

Edit the pipeline, rerun `python pipeline.py && python build_dashboard.py`, refresh the dashboard. That's the loop.
