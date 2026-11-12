# AI Chatbot — How to Run

Guide for the in-dashboard AI chatbot that answers questions about the beverage demand forecast using NVIDIA NIM (Llama / Nemotron family).

**Course:** AI in Operations · SP Jain MAIB · Dr. Sandip Kumar Roy
**Author:** Rakshanda Dhote

---

## 1. One-time setup

### 1.1 Install Python dependencies

From a terminal in this folder:

```bash
pip install -r requirements.txt
```

This installs `pandas`, `numpy`, `scikit-learn`, `statsmodels`, `xgboost`, `openai`, `python-dotenv`, `requests`, `jupyter`.

### 1.2 Get a free NVIDIA API key

1. Open <https://build.nvidia.com/>
2. Sign in (Google / GitHub / email — all free)
3. Click any model card (e.g., Nemotron)
4. Click **"Get API Key"** in the right panel
5. Copy the key — it starts with `nvapi-`

### 1.3 Paste the key into `.env`

Open `.env` in this folder (create if missing) and paste:

```
NVIDIA_API_KEY=nvapi-your-actual-key-here
```

Optional — override the default model:
```
NVIDIA_MODEL=nvidia/nemotron-3.5-bolt-e4b
```

**Never commit `.env` to git.** It's already in `.gitignore`.

---

## 2. Start the chatbot server

```bash
python serve.py
```

You should see:
```
serving D:\...\Problems & Exercises 2 on http://127.0.0.1:8765  (chatbot: ON)
Open: http://127.0.0.1:8765/dashboard.html
```

If it says `chatbot: OFF`, your `.env` is missing or the key is empty — go back to 1.3.

Leave this terminal running. Everything below assumes the server is alive.

---

## 3. Open the dashboard

Open <http://127.0.0.1:8765/dashboard.html> in Chrome / Edge / Firefox.

Click **AI Chatbot** in the left sidebar (bottom entry, 💬 icon). You should see:

- A green dot next to "AI Chatbot" in the sidebar → server is online
- The chat panel header shows: `nvidia/nemotron-3.5-bolt-e4b · live` and a green "server online" badge
- Five suggested-query chips you can click, or an input box at the bottom

---

## 4. Ask the chatbot anything

Type a question and hit **Send** (or press Enter). You can also click one of the suggestion chips:

| Chip | What it asks |
|---|---|
| Why ARIMA wins | Why ARIMA beat Random Forest and XGBoost |
| December inventory plan | What ops should plan for the peak month |
| PI width & safety stock | How to size safety stock from the 95% PI |
| Retraining trigger | When to retrain the model |
| Top planner risks | Three risks a planner must know |

**The chatbot is grounded** — every answer is produced from a server-side system prompt that contains the real metrics from `results.json`:

- Historical EDA (mean demand, peak / trough months, STL seasonal strength)
- Hold-out WAPE for all 4 models
- Walk-forward WAPE for all 4 models
- Best model by WAPE
- ARIMA order selected by AIC
- 3-month forecast with 95% prediction intervals

If you ask something the numbers don't support (e.g. "what's the exact date of the December peak?"), the model will say it doesn't have that information rather than guess.

---

## 5. Where chats are logged

**Server-side (persistent, authoritative):**
```
chatbot_log.jsonl
```
One JSON object per line — timestamp, model, query, answer, latency, token usage. Append-only.

**Dashboard view:**
Open **Training Logs** tab → click the **Chatbot** sub-tab. All queries show up chronologically with search / copy / download, same as the other training-log tabs.

**Browser-side (per-device UX only):**
`localStorage["bev-chat-history"]` — last 40 messages so the chat window survives page reloads. Clear with the **Clear** button in the chat input row.

---

## 6. Changing the model

Edit `.env`:
```
NVIDIA_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b
```

Restart the server (`Ctrl+C` then `python serve.py` again). No dashboard rebuild needed — new queries use the new model.

**Confirmed working models on the free tier:**
- `nvidia/nemotron-3.5-bolt-e4b` — fast, clean JSON (current default)
- `nvidia/nemotron-3.5-super-vl-120b-a12b` — 120B reasoning model, slower
- `nvidia/nemotron-3-ultra-550b-a55b` — 550B, slowest

**Models that look available but aren't served via `/v1/chat/completions`:**
- `meta/llama-3.3-70b-instruct` (returns HTTP 410 Gone)
- `nvidia/llama-3.1-nemotron-70b-instruct` (HTTP 404)
- `mistralai/mistral-large-2-instruct` (HTTP 404)

NVIDIA deprecates endpoints without warning — if a model stops working, pick another from <https://build.nvidia.com/>.

---

## 7. Regenerating the LLM interpretation card

The LLM Interpretation tab shows a static JSON built at pipeline-run time (not per-chat). To refresh it:

```bash
python pipeline.py        # re-trains everything + calls LLM (~3 min)
python build_dashboard.py # rebuilds dashboard.html from the new results.json
```

Or if you only want to re-run the LLM without re-training:

```bash
python -c "import json; from pathlib import Path; from pipeline import get_llm_interpretation, ModelLogger; r=json.loads(Path('results.json').read_text()); p={'dataset':{**r['eda'],'name':'beverage'},'test_period':{'months':12,'start':r['backtest']['test_months'][0],'end':r['backtest']['test_months'][-1]},'metrics':r['metrics'],'walk_forward_metrics':r['walk_forward']['metrics'],'best_model_by_wape':r['best_model'],'arima_order':r['arima_order'],'three_month_forecast':{'months':r['forecast']['months'],'Naive':r['forecast']['Naive'],'ARIMA':r['forecast']['ARIMA'],'ARIMA_95_lower':r['prediction_intervals']['ARIMA']['p025'],'ARIMA_95_upper':r['prediction_intervals']['ARIMA']['p975'],'RandomForest':r['forecast']['RandomForest'],'XGBoost':r['forecast']['XGBoost']}}; r['interpretation']=get_llm_interpretation(p, ModelLogger()); Path('results.json').write_text(json.dumps(r, indent=2))"
python build_dashboard.py
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| Sidebar dot is red, chat says "server offline" | `python serve.py` isn't running. Start it. |
| Server starts but says `chatbot: OFF` | Your `NVIDIA_API_KEY` is empty or still the placeholder. Check `.env`. |
| HTTP 401 / 403 from NVIDIA | API key is invalid or expired. Generate a new one at build.nvidia.com. |
| HTTP 410 Gone | The model was deprecated. Change `NVIDIA_MODEL` in `.env` and restart. |
| HTTP 429 | Rate-limited. Wait a minute, or switch to a smaller model like `bolt-e4b`. |
| Answers feel generic / don't cite numbers | `results.json` is missing or stale. Run `python pipeline.py`. |
| Port 8765 already in use | Set `DASHBOARD_PORT=8766` (or any free port) before running serve.py |

### Check server logs

The terminal running `serve.py` prints every request:
```
[21:48:33] 127.0.0.1 - "POST /chat HTTP/1.1" 200 -
```
HTTP 200 = success, 502 = NVIDIA upstream error, 503 = no API key.

---

## 9. Security notes

- The API key lives **only** in `.env` on your laptop — it's never baked into `dashboard.html`, never sent to the browser, never logged in `chatbot_log.jsonl`.
- `serve.py` only binds to `127.0.0.1` (localhost), so nothing on your network can hit the `/chat` endpoint.
- If you ever share `dashboard.html` alone (no server), the chatbot panel will just show "server offline" — the dashboard itself is still fully functional with charts, logs, and the pre-generated LLM Interpretation card.

---

## 10. File map

```
Problems & Exercises 2/
├── .env                        # API key (DO NOT COMMIT)
├── .env.example                # safe template
├── champagne_sales.csv         # input dataset
├── pipeline.py                 # feature engineering + 4 models + LLM
├── build_dashboard.py          # builds dashboard.html from results.json
├── serve.py                    # static server + /chat proxy  ← needed for chatbot
├── results.json                # pipeline output, inlined into dashboard
├── dashboard.html              # the actual dashboard (Plotly inlined, ~4.9 MB)
├── beverage_forecasting.ipynb  # executed notebook
├── chatbot_log.jsonl           # chat history (auto-created on first query)
├── requirements.txt
├── Dockerfile                  # reproducibility artefact, not needed to run
├── README.md
└── CHATBOT_GUIDE.md            # this file
```
