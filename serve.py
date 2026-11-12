"""
Combined static-file server + NVIDIA NIM chat proxy for the dashboard.

- GET /                    -> serves dashboard.html
- GET /<any-file>          -> serves static files from this directory
- POST /chat               -> proxies to NVIDIA NIM (keeps the API key off the client)
- GET /chat/logs           -> returns the persisted chatbot log (newline JSON)
- POST /chat/logs/clear    -> wipes the server-side log

The proxy injects a grounding system prompt with the current results.json
metrics so the chatbot answers from real numbers.

Run:  python serve.py           (default port 8765)
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import requests

HERE = Path(__file__).parent
RESULTS = HERE / "results.json"
LOG_FILE = HERE / "chatbot_log.jsonl"

PORT = int(os.environ.get("DASHBOARD_PORT", 8765))
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3.5-bolt-e4b")


def build_system_prompt() -> str:
    """Grounding context from the live results.json so the chatbot speaks from numbers."""
    try:
        r = json.loads(RESULTS.read_text(encoding="utf-8"))
    except Exception:
        return ("You are an operations analyst for a beverage demand forecasting dashboard. "
                "Be concise, under 200 words, and never hallucinate numbers.")

    eda = r.get("eda", {})
    metrics = r.get("metrics", {})
    wf = r.get("walk_forward", {}).get("metrics", {})
    fc = r.get("forecast", {})
    pi = r.get("prediction_intervals", {}).get("ARIMA", {})
    best = r.get("best_model", "?")
    arima_order = r.get("arima_order", {})

    return f"""You are the on-dashboard AI analyst for a beverage demand forecasting project
submitted to Dr. Sandip Kumar Roy's AI in Operations course at SP Jain MAIB.
Answer the user's question in 2-6 sentences. Be specific. Use the numbers below.
Never invent numbers that are not here. If the question needs a number you don't have,
say you don't have it.

PROJECT FACTS
- Dataset: Perrin-Freres monthly champagne sales, {eda.get('n_months')} months
  ({eda.get('start')} to {eda.get('end')}), proxy for a new flavored-water beverage.
- Mean demand {eda.get('mean_demand', 0):.0f} units, std {eda.get('std_demand', 0):.0f}.
- Peak month-of-year #{eda.get('peak_month')}, trough #{eda.get('trough_month')}.
- STL seasonal strength {eda.get('seasonal_strength', 0):.2f}, trend {eda.get('trend_strength', 0):.2f}.

HOLD-OUT (last 12 months): Naive WAPE {metrics.get('Naive', {}).get('WAPE')}% /
ARIMA {metrics.get('ARIMA', {}).get('WAPE')}% / RF {metrics.get('RandomForest', {}).get('WAPE')}% /
XGB {metrics.get('XGBoost', {}).get('WAPE')}%.
WALK-FORWARD (refit each step): Naive {wf.get('Naive', {}).get('WAPE')}% /
ARIMA {wf.get('ARIMA', {}).get('WAPE')}% / RF {wf.get('RandomForest', {}).get('WAPE')}% /
XGB {wf.get('XGBoost', {}).get('WAPE')}%.
Best model by WAPE: {best}.
ARIMA order (AIC-selected): {arima_order}.

3-MONTH FORECAST ({', '.join(fc.get('months', []))}):
- ARIMA mean: {[round(x) for x in fc.get('ARIMA', [])]}
- ARIMA 95% PI low:  {[round(x) for x in pi.get('p025', [])]}
- ARIMA 95% PI high: {[round(x) for x in pi.get('p975', [])]}
- RF: {[round(x) for x in fc.get('RandomForest', [])]}
- XGB: {[round(x) for x in fc.get('XGBoost', [])]}

Style: direct, no fluff, use concrete numbers, speak like an operations lead briefing the plant."""


def append_log(entry: dict) -> None:
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[log] failed to append: {e}", file=sys.stderr)


def read_log() -> str:
    if not LOG_FILE.exists():
        return ""
    return LOG_FILE.read_text(encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter default logging
        sys.stderr.write(f"[{datetime.now():%H:%M:%S}] {self.address_string()} - {fmt%args}\n")

    def _send_json(self, status: int, payload: dict | str):
        body = json.dumps(payload).encode("utf-8") if not isinstance(payload, (bytes, str)) else \
               (payload.encode("utf-8") if isinstance(payload, str) else payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/chat/logs":
            return self._send_json(200, {"log": read_log()})
        return super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            return self._send_json(400, {"error": "bad JSON body"})

        if p == "/chat/logs/clear":
            try:
                LOG_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            return self._send_json(200, {"ok": True})

        if p != "/chat":
            return self._send_json(404, {"error": "not found"})

        # ---- /chat: proxy to NVIDIA NIM ----
        key = os.environ.get("NVIDIA_API_KEY", "").strip()
        if not key or key.startswith("nvapi-REPLACE"):
            return self._send_json(503, {"error": "NVIDIA_API_KEY not set in .env"})

        user_message = (data.get("message") or "").strip()
        if not user_message:
            return self._send_json(400, {"error": "empty message"})
        model = (data.get("model") or DEFAULT_MODEL).strip()
        history = data.get("history") or []  # [{role, content}, ...]

        messages = [{"role": "system", "content": build_system_prompt()}]
        for h in history[-6:]:  # last 3 turns of context
            if h.get("role") in ("user", "assistant") and h.get("content"):
                messages.append({"role": h["role"], "content": str(h["content"])[:2000]})
        messages.append({"role": "user", "content": user_message})

        t0 = time.time()
        try:
            resp = requests.post(
                NVIDIA_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 800,
                    "temperature": 0.3,
                    "top_p": 0.9,
                },
                timeout=60,
            )
            dt = time.time() - t0
            if resp.status_code != 200:
                append_log({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "model": model, "ok": False,
                    "query": user_message,
                    "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                    "latency_s": round(dt, 2),
                })
                return self._send_json(502, {
                    "error": f"NVIDIA returned HTTP {resp.status_code}",
                    "detail": resp.text[:500],
                })
            payload = resp.json()
            msg = payload["choices"][0]["message"]
            answer = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            usage = payload.get("usage", {})
            append_log({
                "ts": datetime.now(timezone.utc).isoformat(),
                "model": model, "ok": True,
                "query": user_message,
                "answer": answer,
                "latency_s": round(dt, 2),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            })
            return self._send_json(200, {
                "answer": answer,
                "model": model,
                "latency_s": round(dt, 2),
                "usage": usage,
            })
        except Exception as e:
            dt = time.time() - t0
            err = f"{type(e).__name__}: {e}"
            append_log({
                "ts": datetime.now(timezone.utc).isoformat(),
                "model": model, "ok": False,
                "query": user_message,
                "error": err, "latency_s": round(dt, 2),
            })
            traceback.print_exc()
            return self._send_json(500, {"error": err})


def main():
    os.chdir(HERE)
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    key_set = bool(os.environ.get("NVIDIA_API_KEY", "").strip())
    print(f"serving {HERE} on http://127.0.0.1:{PORT}  (chatbot: {'ON' if key_set else 'OFF — set NVIDIA_API_KEY in .env'})")
    print("Open: http://127.0.0.1:{}/dashboard.html".format(PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
