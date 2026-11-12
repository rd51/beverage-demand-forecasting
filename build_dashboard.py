"""
Builder: splices Plotly.js (from existing dashboard.html) + fresh HTML shell
       + inlined results.json into a new dashboard.html.

Run:  python build_dashboard.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
EXISTING = HERE / "dashboard.html"
RESULTS = HERE / "results.json"
OUT = HERE / "dashboard.html"


def extract_plotly_blob(html: str) -> str:
    """Pull the <script>..</script> that holds the inlined Plotly.js bundle.
    Convention: it is the FIRST <script> in the document (before </head>)."""
    m = re.search(r"(<script>.*?</script>)", html, re.DOTALL)
    if not m:
        raise RuntimeError("Could not find Plotly.js <script> block in existing dashboard.html")
    blob = m.group(1)
    if "plotly" not in blob.lower() or len(blob) < 500_000:
        raise RuntimeError(
            f"First <script> block does not look like the Plotly.js bundle "
            f"(length {len(blob):,} chars). Aborting to avoid breaking the page."
        )
    return blob


SHELL_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Beverage Demand Forecasting Dashboard</title>
__PLOTLY_BLOB__
<style>
  :root {
    --bg: #f6f8fc;
    --panel: #ffffff;
    --panel-2: #f1f5f9;
    --ink: #0f172a;
    --ink-2: #334155;
    --ink-3: #64748b;
    --ink-4: #94a3b8;
    --accent: #2563eb;
    --accent-2: #1d4ed8;
    --accent-soft: rgba(37, 99, 235, 0.12);
    --success: #059669;
    --warn: #d97706;
    --danger: #dc2626;
    --border: #e2e8f0;
    --border-strong: #cbd5e1;
    --shadow: 0 1px 2px rgba(15,23,42,.04), 0 2px 10px rgba(15,23,42,.06);
    --shadow-lg: 0 4px 12px rgba(15,23,42,.08), 0 2px 4px rgba(15,23,42,.04);
    --radius: 14px;
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    --log-bg: #0b1220;
    --log-ink: #cbd5e1;
    --log-dim: #64748b;
    --log-hl: #60a5fa;
  }
  :root:not([data-theme="light"]) {
    @media (prefers-color-scheme: dark) {
      --bg: #0b1220;
      --panel: #111a2e;
      --panel-2: #0f172a;
      --ink: #e2e8f0;
      --ink-2: #cbd5e1;
      --ink-3: #94a3b8;
      --ink-4: #64748b;
      --accent: #60a5fa;
      --accent-2: #3b82f6;
      --accent-soft: rgba(96, 165, 250, 0.16);
      --success: #34d399;
      --warn: #fbbf24;
      --danger: #f87171;
      --border: #1e293b;
      --border-strong: #334155;
      --shadow: 0 1px 2px rgba(0,0,0,.4), 0 2px 10px rgba(0,0,0,.3);
      --shadow-lg: 0 6px 20px rgba(0,0,0,.5);
    }
  }
  :root[data-theme="dark"] {
    --bg: #0b1220; --panel: #111a2e; --panel-2: #0f172a;
    --ink: #e2e8f0; --ink-2: #cbd5e1; --ink-3: #94a3b8; --ink-4: #64748b;
    --accent: #60a5fa; --accent-2: #3b82f6; --accent-soft: rgba(96, 165, 250, 0.16);
    --success: #34d399; --warn: #fbbf24; --danger: #f87171;
    --border: #1e293b; --border-strong: #334155;
    --shadow: 0 1px 2px rgba(0,0,0,.4), 0 2px 10px rgba(0,0,0,.3);
    --shadow-lg: 0 6px 20px rgba(0,0,0,.5);
  }

  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif;
    font-size: 15px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1320px; margin: 0 auto; padding: 32px 20px 80px; }
  @media (max-width: 640px) { .wrap { padding: 20px 14px 60px; } }

  /* ---- Vertical tabs layout ---- */
  .tab-layout {
    display: grid;
    grid-template-columns: 230px 1fr;
    gap: 20px;
    align-items: flex-start;
  }
  @media (max-width: 900px) { .tab-layout { grid-template-columns: 1fr; } }

  .tab-nav {
    position: sticky; top: 20px;
    display: flex; flex-direction: column; gap: 4px;
    background: var(--panel); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 10px; box-shadow: var(--shadow);
  }
  .tab-nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; border-radius: 10px;
    font-size: 13px; color: var(--ink-2); cursor: pointer;
    background: transparent; border: 1px solid transparent;
    user-select: none; transition: all 0.15s ease;
    text-align: left; font-family: inherit;
  }
  .tab-nav-item:hover { background: var(--panel-2); color: var(--ink); }
  .tab-nav-item.active {
    background: var(--accent-soft); color: var(--accent);
    font-weight: 600; border-color: color-mix(in srgb, var(--accent) 25%, transparent);
  }
  .tab-nav-item .ico {
    width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center;
    font-size: 14px;
  }
  .tab-nav-item .num {
    margin-left: auto; font-family: var(--mono); font-size: 10px; color: var(--ink-4);
    letter-spacing: 0.05em;
  }
  .tab-nav-item.active .num { color: var(--accent); }

  .tab-content > section { display: none; animation: fadeIn 0.2s ease; }
  .tab-content > section.active { display: block; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

  @media (max-width: 900px) {
    .tab-nav { position: static; flex-direction: row; overflow-x: auto; padding: 8px; }
    .tab-nav-item { flex-shrink: 0; }
    .tab-nav-item .num { display: none; }
  }

  /* ---- Header ---- */
  header {
    display: flex; justify-content: space-between; align-items: flex-start;
    gap: 16px; margin-bottom: 24px; flex-wrap: wrap;
  }
  header .title-wrap { min-width: 0; }
  header .eyebrow {
    font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--ink-3); font-weight: 600; margin: 0 0 6px;
  }
  header .title { font-size: 28px; font-weight: 700; letter-spacing: -0.02em; margin: 0 0 6px; }
  header .subtitle { font-size: 14px; color: var(--ink-3); margin: 0; }
  .header-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .btn {
    display: inline-flex; align-items: center; gap: 7px;
    background: var(--panel); border: 1px solid var(--border); color: var(--ink-2);
    padding: 7px 13px; border-radius: 10px; font-size: 13px;
    text-decoration: none; cursor: pointer; font-weight: 500;
    transition: all 0.15s ease;
  }
  .btn:hover { color: var(--ink); border-color: var(--accent); box-shadow: var(--shadow); }
  .btn.primary { background: var(--accent); color: white; border-color: var(--accent); }
  .btn.primary:hover { background: var(--accent-2); color: white; }

  /* ---- Card ---- */
  .card {
    background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 22px 24px; margin-bottom: 18px; box-shadow: var(--shadow);
  }
  .card h2 {
    font-size: 17px; margin: 0 0 14px; letter-spacing: -0.01em; font-weight: 650;
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  }
  .card h2 .tag {
    font-size: 11px; font-weight: 500; color: var(--ink-3);
    background: var(--panel-2); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 999px; letter-spacing: 0.02em;
  }
  .card h3 { font-size: 13px; margin: 18px 0 8px; color: var(--ink-3); font-weight: 600;
             text-transform: uppercase; letter-spacing: 0.06em; }
  .card p { margin: 0 0 10px; color: var(--ink-2); }
  .card p:last-child { margin-bottom: 0; }

  /* ---- KPIs ---- */
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }
  @media (max-width: 860px) { .kpis { grid-template-columns: repeat(2, 1fr); } }
  .kpi {
    background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px 18px; box-shadow: var(--shadow); position: relative; overflow: hidden;
  }
  .kpi.best::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: var(--success);
  }
  .kpi .label { font-size: 11px; color: var(--ink-3); text-transform: uppercase;
                letter-spacing: 0.07em; margin: 0 0 6px; font-weight: 600; }
  .kpi .value { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; margin: 0;
                font-variant-numeric: tabular-nums; }
  .kpi .delta { font-size: 12px; color: var(--ink-3); margin-top: 4px; }
  .kpi.best .value { color: var(--success); }

  /* ---- LLM Interpretation card ---- */
  .llm-card { background: linear-gradient(135deg, var(--panel) 0%, color-mix(in srgb, var(--accent-soft) 40%, var(--panel)) 100%); }
  .llm-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .headline {
    font-size: 18px; font-weight: 600; color: var(--ink);
    border-left: 3px solid var(--accent); padding: 6px 0 6px 16px;
    margin: 6px 0 20px; line-height: 1.5;
  }
  .interp-grid { display: grid; grid-template-columns: 1.1fr 1fr; gap: 24px; }
  @media (max-width: 920px) { .interp-grid { grid-template-columns: 1fr; } }
  .recs { padding-left: 20px; margin: 6px 0 0; }
  .recs li, .risks li { margin-bottom: 8px; color: var(--ink-2); }
  .risks { padding-left: 20px; margin: 6px 0 0; }
  .src-badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-family: var(--mono); font-size: 11px; color: var(--ink-3);
    background: var(--panel-2); border: 1px solid var(--border);
    padding: 3px 10px; border-radius: 999px;
  }
  .src-badge .dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--success); display: inline-block;
  }

  /* ---- Day-10 style insights (numbered cards) ---- */
  .insights { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 8px; }
  @media (max-width: 760px) { .insights { grid-template-columns: 1fr; } }
  .insight {
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px; position: relative;
  }
  .insight .num {
    font-family: var(--mono); font-size: 11px; font-weight: 700;
    color: var(--accent); letter-spacing: 0.1em;
  }
  .insight .ttl { font-weight: 600; color: var(--ink); margin: 2px 0 4px; font-size: 14px; }
  .insight .body { font-size: 13.5px; color: var(--ink-2); line-height: 1.5; }

  .realworld {
    margin-top: 18px; padding: 14px 16px;
    background: color-mix(in srgb, var(--accent-soft) 60%, transparent);
    border-left: 3px solid var(--accent); border-radius: 0 10px 10px 0;
    font-size: 13.5px; color: var(--ink-2); line-height: 1.5;
  }
  .realworld .lbl { display: block; font-size: 11px; font-weight: 700;
                    color: var(--accent); letter-spacing: 0.1em; margin-bottom: 4px; }

  /* ---- Table ---- */
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  thead th {
    text-align: left; font-weight: 600; color: var(--ink-3);
    border-bottom: 1px solid var(--border);
    padding: 8px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  }
  tbody td { padding: 10px; border-bottom: 1px solid var(--border); color: var(--ink-2);
             font-variant-numeric: tabular-nums; }
  tbody tr:last-child td { border-bottom: 0; }
  tbody tr.best td {
    background: color-mix(in srgb, var(--success) 10%, transparent);
    color: var(--ink); font-weight: 600;
  }
  .num { font-family: var(--mono); text-align: right; }

  /* ---- Charts ---- */
  .chart { width: 100%; height: 360px; }

  /* ---- Model chip toggles ---- */
  .chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .chip {
    padding: 5px 11px; border-radius: 999px; font-size: 12px; cursor: pointer;
    background: var(--panel-2); border: 1px solid var(--border); color: var(--ink-2);
    user-select: none; transition: all 0.15s;
  }
  .chip:hover { border-color: var(--accent); }
  .chip.active { background: var(--accent); color: white; border-color: var(--accent); }
  .chip .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
               margin-right: 6px; vertical-align: middle; }

  /* ---- Logs panel ---- */
  .log-tabs { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; }
  .log-tab {
    padding: 6px 12px; border-radius: 8px 8px 0 0; font-size: 12px;
    cursor: pointer; background: transparent;
    border: 1px solid transparent; color: var(--ink-3);
    font-family: var(--mono); user-select: none;
  }
  .log-tab:hover { color: var(--ink); }
  .log-tab.active {
    color: var(--accent); background: var(--log-bg);
    border-color: var(--border-strong); border-bottom-color: var(--log-bg);
  }
  .log-pane {
    background: var(--log-bg); color: var(--log-ink);
    font-family: var(--mono); font-size: 12px; line-height: 1.55;
    padding: 14px 16px; border-radius: 0 10px 10px 10px;
    border: 1px solid var(--border-strong);
    max-height: 420px; overflow: auto;
    white-space: pre-wrap; word-break: break-word;
  }
  .log-pane::-webkit-scrollbar { width: 10px; height: 10px; }
  .log-pane::-webkit-scrollbar-track { background: transparent; }
  .log-pane::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
  .log-controls { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
  .log-controls .search {
    flex: 1; min-width: 160px;
    background: var(--panel-2); border: 1px solid var(--border);
    color: var(--ink); padding: 5px 10px; border-radius: 8px;
    font-family: var(--mono); font-size: 12px;
  }

  /* highlight for search matches inside the log */
  .log-pane mark { background: var(--log-hl); color: #0b1220; border-radius: 2px; padding: 0 2px; }

  /* ---- Chatbot ---- */
  .chat-window {
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px; margin: 14px 0;
    min-height: 320px; max-height: 480px; overflow-y: auto;
    display: flex; flex-direction: column; gap: 10px;
  }
  .chat-empty {
    color: var(--ink-3); font-size: 13px; text-align: center; padding: 60px 20px;
    font-style: italic;
  }
  .chat-msg { display: flex; gap: 10px; align-items: flex-start; max-width: 85%; }
  .chat-msg.user { align-self: flex-end; flex-direction: row-reverse; }
  .chat-msg .avatar {
    width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
  }
  .chat-msg.user .avatar { background: var(--accent); color: white; }
  .chat-msg.assistant .avatar { background: var(--success); color: white; }
  .chat-msg.error .avatar { background: var(--danger); color: white; }
  .chat-msg .bubble {
    background: var(--panel); border: 1px solid var(--border);
    padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.55;
    color: var(--ink-2); white-space: pre-wrap; word-break: break-word;
  }
  .chat-msg.user .bubble { background: var(--accent-soft); border-color: color-mix(in srgb, var(--accent) 25%, var(--border)); color: var(--ink); }
  .chat-msg.error .bubble { color: var(--danger); border-color: color-mix(in srgb, var(--danger) 30%, var(--border)); }
  .chat-msg .meta {
    font-size: 11px; color: var(--ink-4); font-family: var(--mono);
    margin-top: 6px;
  }
  .chat-typing .bubble::after {
    content: '▌'; animation: blink 1s steps(1) infinite; color: var(--accent);
  }
  @keyframes blink { 50% { opacity: 0; } }
  .chat-suggestions { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .chat-suggestions .chip { font-size: 12px; cursor: pointer; }
  .chat-input-row { display: flex; gap: 8px; align-items: center; }
  .chat-input-row #chatInput {
    flex: 1; min-width: 0;
    background: var(--panel-2); border: 1px solid var(--border-strong);
    color: var(--ink); padding: 10px 14px; border-radius: 10px;
    font-family: inherit; font-size: 14px;
  }
  .chat-input-row #chatInput:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
  #chatStatusDot { color: var(--success); font-size: 12px; animation: pulse 2s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity: 0.6; } 50% { opacity: 1; } }

  /* ---- Forecast table with PI ---- */
  .forecast-table th { text-align: right; }
  .forecast-table th:first-child, .forecast-table td:first-child { text-align: left; }
  .pi-cell { color: var(--ink-3); font-size: 12px; }

  /* ---- Dataset banner ---- */
  .banner {
    padding: 12px 16px; border-radius: 10px;
    background: color-mix(in srgb, var(--warn) 10%, var(--panel));
    border: 1px solid color-mix(in srgb, var(--warn) 35%, var(--border));
    font-size: 13px; color: var(--ink-2); margin-bottom: 18px;
  }
  .banner strong { color: var(--warn); font-weight: 700; }

  footer { margin-top: 32px; padding-top: 18px; border-top: 1px solid var(--border);
           color: var(--ink-3); font-size: 12px; text-align: center; }
  footer a { color: var(--accent); text-decoration: none; }

  /* Hide element helper */
  .hidden { display: none !important; }
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div class="title-wrap">
      <p class="eyebrow">AI in Operations · Session II · Problems &amp; Exercises 2</p>
      <h1 class="title" id="title">Beverage Demand Forecasting</h1>
      <p class="subtitle" id="subtitle">Dr. Sandip Kumar Roy · SP Jain MAIB · Rakshanda Dhote</p>
    </div>
    <div class="header-actions">
      <button class="btn" id="themeToggle">Theme</button>
    </div>
  </header>

  <div class="tab-layout">

    <!-- ============ LEFT SIDEBAR: VERTICAL TABS ============ -->
    <nav class="tab-nav" id="tabNav">
      <button class="tab-nav-item active" data-tab="overview">
        <span class="ico">◆</span>Overview<span class="num">01</span>
      </button>
      <button class="tab-nav-item" data-tab="llm">
        <span class="ico">★</span>LLM Interpretation<span class="num">02</span>
      </button>
      <button class="tab-nav-item" data-tab="forecast">
        <span class="ico">▲</span>Forecast + PI<span class="num">03</span>
      </button>
      <button class="tab-nav-item" data-tab="backtest">
        <span class="ico">◇</span>Hold-out backtest<span class="num">04</span>
      </button>
      <button class="tab-nav-item" data-tab="walkforward">
        <span class="ico">▶</span>Walk-forward<span class="num">05</span>
      </button>
      <button class="tab-nav-item" data-tab="models">
        <span class="ico">≡</span>Model comparison<span class="num">06</span>
      </button>
      <button class="tab-nav-item" data-tab="logs">
        <span class="ico">&gt;_</span>Training logs<span class="num">07</span>
      </button>
      <button class="tab-nav-item" data-tab="methodology">
        <span class="ico">ⓘ</span>Methodology<span class="num">08</span>
      </button>
      <div style="height:1px; background:var(--border); margin:6px 4px;"></div>
      <button class="tab-nav-item" data-tab="chatbot">
        <span class="ico">💬</span>AI Chatbot
        <span class="num" id="chatStatusDot">●</span>
      </button>
    </nav>

    <!-- ============ RIGHT: TAB CONTENT ============ -->
    <div class="tab-content" id="tabContent">

      <!-- 01 Overview -->
      <section data-tab="overview" class="active">
        <div class="banner" id="datasetBanner"></div>
        <div class="kpis" id="kpis"></div>
        <div class="card">
          <h2>Scenario &amp; task <span class="tag">AIO Session II · page 65–66</span></h2>
          <p id="scenario"></p>
          <p id="datasetNote"></p>
        </div>
      </section>

      <!-- 02 LLM Interpretation -->
      <section data-tab="llm">
        <div class="card llm-card">
          <div class="llm-head">
            <h2>LLM Interpretation
              <span class="tag" id="llmTag">Executive briefing</span>
            </h2>
            <span class="src-badge" id="llmSource"><span class="dot"></span><span id="llmSourceLabel">—</span></span>
          </div>
          <div class="headline" id="headline"></div>
          <div class="interp-grid">
            <div>
              <h3>Seasonality &amp; trend</h3>
              <p id="seasonality"></p>
              <h3>Model comparison</h3>
              <p id="modelCompare"></p>
              <h3>3-month forecast insight</h3>
              <p id="forecastInsight"></p>
            </div>
            <div>
              <h3>Key insights</h3>
              <div class="insights" id="keyInsights"></div>
              <h3 style="margin-top:20px;">Recommendations</h3>
              <ol class="recs" id="recs"></ol>
              <h3>Risks &amp; caveats</h3>
              <ul class="risks" id="risks"></ul>
            </div>
          </div>
          <div class="realworld" id="realworld"></div>
        </div>
      </section>

      <!-- 03 Forecast + PI -->
      <section data-tab="forecast">
        <div class="card">
          <h2>History &amp; 3-month forecast <span class="tag">with 80 / 95% prediction intervals</span></h2>
          <p id="chartDesc"></p>
          <div id="historyChart" class="chart" style="height:420px"></div>
        </div>
        <div class="card">
          <h2>3-month forecast table <span class="tag">all models + ARIMA prediction intervals</span></h2>
          <p id="forecastDesc"></p>
          <div style="overflow-x:auto;"><table id="forecastTable" class="forecast-table"></table></div>
        </div>
      </section>

      <!-- 04 Hold-out backtest -->
      <section data-tab="backtest">
        <div class="card">
          <h2>Hold-out backtest <span class="tag">last 12 months, static split</span></h2>
          <p>Click a chip to toggle any model on the chart.</p>
          <div class="chips" id="modelChips"></div>
          <div id="backtestChart" class="chart"></div>
        </div>
      </section>

      <!-- 05 Walk-forward -->
      <section data-tab="walkforward">
        <div class="card">
          <h2>Walk-forward validation <span class="tag">expanding window, refit each step</span></h2>
          <p>Each point is a one-step-ahead forecast after refitting on all data up to that month.
             This is the honest test for a production forecasting cycle.</p>
          <div id="walkforwardChart" class="chart" style="height:380px"></div>
        </div>
      </section>

      <!-- 06 Model comparison -->
      <section data-tab="models">
        <div class="card">
          <h2>Model comparison <span class="tag">MAPE / WAPE / MAE</span></h2>
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 24px;" id="metricsGrid">
            <div>
              <h3>Hold-out metrics</h3>
              <table id="metricsTable"></table>
              <h3 style="margin-top:22px;">Walk-forward metrics</h3>
              <table id="walkforwardMetricsTable"></table>
            </div>
            <div>
              <div id="metricsBar" class="chart" style="height:320px"></div>
              <div id="featureImportanceChart" class="chart" style="height:280px; margin-top:16px;"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- 07 Training logs -->
      <section data-tab="logs">
        <div class="card">
          <h2>Training logs <span class="tag">verbose, per-model</span></h2>
          <p>Full per-model training trace captured from the pipeline run — grid search, fit metrics,
             feature importance, bootstrap progress. Use the search box to filter lines.</p>
          <div class="log-tabs" id="logTabs"></div>
          <div class="log-controls">
            <input id="logSearch" class="search" placeholder="filter log lines (regex, e.g. ^\[.+XGB)">
            <button class="btn" id="logCopy">Copy</button>
            <button class="btn" id="logDownload">Download .log</button>
          </div>
          <pre class="log-pane" id="logPane"></pre>
        </div>
      </section>

      <!-- Chatbot -->
      <section data-tab="chatbot">
        <div class="card">
          <h2>AI Chatbot <span class="tag" id="chatModelTag">nvidia/nemotron-3.5-bolt-e4b · live</span>
            <span class="src-badge" id="chatHealthBadge" style="margin-left:auto;">
              <span class="dot" id="chatHealthDot"></span><span id="chatHealthLabel">checking…</span>
            </span>
          </h2>
          <p>Ask anything about the forecast — the model has the full set of live metrics,
             prediction intervals, walk-forward results and ARIMA order as grounding context.
             Answers cite real numbers only.</p>

          <div class="chat-window" id="chatWindow"></div>

          <div class="chat-suggestions" id="chatSuggestions">
            <button class="chip" data-q="Why did ARIMA win over Random Forest and XGBoost?">Why ARIMA wins</button>
            <button class="chip" data-q="What inventory should Operations build for December?">December inventory plan</button>
            <button class="chip" data-q="How wide are the 95% prediction intervals and what does that mean for safety stock?">PI width & safety stock</button>
            <button class="chip" data-q="If the model's WAPE drifts above 13%, what should trigger a retraining cycle?">Retraining trigger</button>
            <button class="chip" data-q="What are the top 3 risks a planner must know about this forecast?">Top planner risks</button>
          </div>

          <form class="chat-input-row" id="chatForm">
            <input type="text" id="chatInput" placeholder="Ask the forecast model something…" autocomplete="off">
            <button type="submit" class="btn primary" id="chatSend">Send</button>
            <button type="button" class="btn" id="chatClear" title="Clear local chat history">Clear</button>
          </form>
        </div>
      </section>

      <!-- 08 Methodology -->
      <section data-tab="methodology">
        <div class="card">
          <h2>Methodology</h2>
          <p>
            <strong>Models.</strong> Naive (previous month), SARIMA (AIC-selected order via grid search),
            Random Forest (400 trees, depth 8), XGBoost (500 rounds, lr 0.05, depth 5).
          </p>
          <p>
            <strong>Features (tree models).</strong> Lag1, Lag2, Lag3, Lag12, rolling mean 3 &amp; 6, month-of-year, quarter.
          </p>
          <p>
            <strong>Validation.</strong> Two protocols — (a) last 12 months as a static hold-out, (b) walk-forward with
            expanding window and refit each step. Metric for model selection: WAPE (revenue-weighted).
          </p>
          <p>
            <strong>Prediction intervals.</strong> ARIMA 80% &amp; 95% from the Kalman filter forecast
            covariance. Trees use bootstrap resampling of the training window (150 resamples, recursive forecast).
          </p>
          <p>
            <strong>LLM integration.</strong> NVIDIA NIM (OpenAI-compatible endpoint), model
            <code id="llmModelName">nvidia/nemotron-3.5-bolt-e4b</code>, called with a structured JSON-schema
            prompt built from the live metrics. Deterministic template fallback when no key is configured.
          </p>
          <p style="font-family: var(--mono); font-size:12px; color: var(--ink-3); margin-top:14px;">
            ARIMA order (AIC-selected): <span id="arimaOrder"></span> · AIC = <span id="arimaAic"></span>
          </p>
        </div>
      </section>

    </div>
  </div>

  <footer>
    Generated <span id="genAt"></span> · <span id="footerAuthor"></span>
  </footer>
</div>

<script>
  // ========== DATA IS INLINED AT BUILD TIME ==========
  const DATA = __DATA_JSON__;

  // ---------- Theme ----------
  const themeBtn = document.getElementById('themeToggle');
  const setTheme = (t) => {
    document.documentElement.setAttribute('data-theme', t);
    try { localStorage.setItem('bev-theme', t); } catch (e) {}
    renderPlotly(); // re-render charts with new theme colors
  };
  const curTheme = () => document.documentElement.getAttribute('data-theme') || 'auto';
  themeBtn.addEventListener('click', () => {
    const t = curTheme();
    setTheme(t === 'dark' ? 'light' : t === 'light' ? 'auto' : 'dark');
  });
  try {
    const saved = localStorage.getItem('bev-theme');
    if (saved) document.documentElement.setAttribute('data-theme', saved);
  } catch (e) {}

  // ---------- helpers ----------
  const fmt = (n) => (n == null || isNaN(n)) ? '—' :
      Math.round(Number(n)).toLocaleString('en-IN');
  const pct = (n) => (n == null) ? '—' : Number(n).toFixed(2) + '%';
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const escapeHTML = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // model colours (consistent across every chart)
  const MODEL_COLOR = {
    Naive:        '#94a3b8',
    ARIMA:        '#2563eb',
    RandomForest: '#059669',
    XGBoost:      '#d97706',
    Actual:       '#0f172a',
  };
  const MODEL_LABEL = {
    Naive: 'Naive', ARIMA: 'ARIMA', RandomForest: 'Random Forest', XGBoost: 'XGBoost',
  };

  // ---------- Dataset banner ----------
  const scenarioEl = document.getElementById('scenario');
  const datasetNoteEl = document.getElementById('datasetNote');
  const bannerEl = document.getElementById('datasetBanner');
  scenarioEl.textContent = DATA.meta.scenario;
  datasetNoteEl.textContent = DATA.meta.dataset_note;
  bannerEl.innerHTML = `<strong>Dataset note:</strong> The exercise brief specifies
    "monthly sales for the first year" (12 points) — too few to fit ARIMA or XGBoost.
    We use the public <em>Perrin-Freres monthly champagne sales</em> series
    (${DATA.eda.n_months} months, ${DATA.eda.start} → ${DATA.eda.end}) as a proxy for a
    seasonal beverage product. The pipeline is dataset-agnostic — any
    <code>Month,Sales</code> CSV plugs in.`;

  // ---------- KPIs ----------
  const best = DATA.best_model;
  const bestMetrics = DATA.metrics[best];
  const kpis = [
    { label: 'Best model (by WAPE)', value: MODEL_LABEL[best], delta: `MAPE ${pct(bestMetrics.MAPE)} · WAPE ${pct(bestMetrics.WAPE)}`, best: true },
    { label: 'Mean demand', value: fmt(DATA.eda.mean_demand), delta: `std ${fmt(DATA.eda.std_demand)} · ${DATA.eda.n_months} months` },
    { label: 'Seasonal strength', value: DATA.eda.seasonal_strength.toFixed(2), delta: `peak month #${DATA.eda.peak_month} · trough #${DATA.eda.trough_month}` },
    { label: 'Walk-forward WAPE', value: pct(DATA.walk_forward.metrics[best].WAPE), delta: `MAPE ${pct(DATA.walk_forward.metrics[best].MAPE)} · ${MODEL_LABEL[best]}` },
  ];
  document.getElementById('kpis').innerHTML = kpis.map(k =>
    `<div class="kpi ${k.best ? 'best' : ''}">
       <p class="label">${k.label}</p>
       <p class="value">${k.value}</p>
       <p class="delta">${k.delta}</p>
     </div>`).join('');

  // ---------- LLM interpretation ----------
  const interp = DATA.interpretation;
  document.getElementById('headline').textContent = interp.headline || '';
  document.getElementById('seasonality').textContent = interp.seasonality_insight || '';
  document.getElementById('modelCompare').textContent = interp.model_comparison || '';
  document.getElementById('forecastInsight').textContent = interp.forecast_insight || '';

  // key insights -> numbered cards (Day-10 style)
  const insights = Array.isArray(interp.key_insights) ? interp.key_insights : [];
  document.getElementById('keyInsights').innerHTML = insights.map((it, i) => {
    // allow either "Title — body" or plain body
    const m = typeof it === 'string' ? it.match(/^(.+?)\s*[—:-]\s*(.+)$/) : null;
    const title = m ? m[1] : (typeof it === 'object' && it.title ? it.title : `Insight ${i+1}`);
    const body = m ? m[2] : (typeof it === 'object' && it.body ? it.body : it);
    const n = String(i + 1).padStart(2, '0');
    return `<div class="insight">
      <div class="num">${n}</div>
      <div class="ttl">${title}</div>
      <div class="body">${body}</div>
    </div>`;
  }).join('');

  document.getElementById('recs').innerHTML =
    (interp.recommendations || []).map(r => `<li>${r}</li>`).join('');
  document.getElementById('risks').innerHTML =
    (interp.risks || []).map(r => `<li>${r}</li>`).join('');

  if (interp.real_world_connection) {
    document.getElementById('realworld').innerHTML =
      `<span class="lbl">Why this matters for AI in Operations</span>${interp.real_world_connection}`;
  } else {
    document.getElementById('realworld').classList.add('hidden');
  }

  const src = interp._source || 'unknown';
  document.getElementById('llmSourceLabel').textContent = src;
  if (src.startsWith('template')) {
    document.querySelector('#llmSource .dot').style.background = 'var(--warn)';
    document.getElementById('llmSourceLabel').textContent = src + ' (set NVIDIA_API_KEY in .env + re-run pipeline for live LLM)';
  }

  // ---------- Metrics tables ----------
  const renderMetricsTable = (metricsObj, tableId) => {
    const rows = Object.entries(metricsObj)
      .sort(([, a], [, b]) => a.WAPE - b.WAPE);
    const html = `
      <thead><tr><th>Model</th><th>MAPE</th><th>WAPE</th><th>MAE</th></tr></thead>
      <tbody>${rows.map(([name, m], i) =>
        `<tr class="${i === 0 ? 'best' : ''}">
          <td>${MODEL_LABEL[name]}</td>
          <td class="num">${pct(m.MAPE)}</td>
          <td class="num">${pct(m.WAPE)}</td>
          <td class="num">${fmt(m.MAE)}</td>
        </tr>`).join('')}</tbody>`;
    document.getElementById(tableId).innerHTML = html;
  };
  renderMetricsTable(DATA.metrics, 'metricsTable');
  renderMetricsTable(DATA.walk_forward.metrics, 'walkforwardMetricsTable');

  // ---------- Forecast table with PI ----------
  const fc = DATA.forecast;
  const pi = DATA.prediction_intervals;
  const makeRow = (label, vals, piLo, piHi) => {
    const cells = vals.map((v, i) => {
      const piCell = (piLo && piHi) ?
        `<br><span class="pi-cell">[${fmt(piLo[i])} – ${fmt(piHi[i])}]</span>` : '';
      return `<td class="num">${fmt(v)}${piCell}</td>`;
    }).join('');
    return `<tr><td>${label}</td>${cells}</tr>`;
  };
  document.getElementById('forecastTable').innerHTML = `
    <thead><tr><th>Model</th>${fc.months.map(m => `<th>${m}</th>`).join('')}</tr></thead>
    <tbody>
      ${makeRow('Naive', fc.Naive)}
      ${makeRow(`ARIMA <span class="pi-cell">(95% PI)</span>`, fc.ARIMA, pi.ARIMA.p025, pi.ARIMA.p975)}
      ${makeRow(`Random Forest <span class="pi-cell">(95% PI)</span>`, fc.RandomForest, pi.RandomForest.p025, pi.RandomForest.p975)}
      ${makeRow(`XGBoost <span class="pi-cell">(95% PI)</span>`, fc.XGBoost, pi.XGBoost.p025, pi.XGBoost.p975)}
    </tbody>`;
  document.getElementById('forecastDesc').textContent =
    `Retrained on full history (${DATA.eda.n_months} months). ARIMA intervals from Kalman forecast covariance; tree-model intervals from bootstrap resampling (150 resamples, recursive multi-step).`;

  // ---------- ARIMA order + misc ----------
  document.getElementById('arimaOrder').textContent =
    `(${DATA.arima_order.non_seasonal.join(',')}) × (${DATA.arima_order.seasonal.join(',')})`;
  document.getElementById('arimaAic').textContent = DATA.arima_aic;
  document.getElementById('genAt').textContent = DATA.meta.generated_at;
  document.getElementById('footerAuthor').textContent = DATA.meta.author;
  document.getElementById('chartDesc').textContent =
    `Historical demand (${DATA.eda.start} → ${DATA.eda.end}) with the next 3 months forecast. Shaded bands show ARIMA 80% and 95% prediction intervals.`;

  // ---------- Model chips (backtest) ----------
  const CHIP_MODELS = ['Naive', 'ARIMA', 'RandomForest', 'XGBoost'];
  let activeChips = new Set(['ARIMA', 'RandomForest', 'XGBoost']);
  const chipsEl = document.getElementById('modelChips');
  chipsEl.innerHTML = CHIP_MODELS.map(m =>
    `<span class="chip ${activeChips.has(m) ? 'active' : ''}" data-m="${m}">
       <span class="dot" style="background:${MODEL_COLOR[m]}"></span>${MODEL_LABEL[m]}
     </span>`).join('');
  chipsEl.addEventListener('click', e => {
    const chip = e.target.closest('.chip'); if (!chip) return;
    const m = chip.dataset.m;
    if (activeChips.has(m)) activeChips.delete(m); else activeChips.add(m);
    chip.classList.toggle('active');
    renderBacktest();
  });

  // ---------- Plotly rendering ----------
  const PLOT_CONFIG = { responsive: true, displayModeBar: false };
  const plotLayout = (extra = {}) => {
    const isDark = curTheme() === 'dark' ||
      (curTheme() === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    return Object.assign({
      margin: { t: 20, r: 20, b: 44, l: 56 },
      font: { family: '-apple-system, "Segoe UI", sans-serif', color: css('--ink-2'), size: 12 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      xaxis: { gridcolor: css('--border'), linecolor: css('--border-strong'), zerolinecolor: css('--border') },
      yaxis: { gridcolor: css('--border'), linecolor: css('--border-strong'), zerolinecolor: css('--border'),
               tickformat: ',.0f' },
      legend: { orientation: 'h', y: -0.18, x: 0 },
      hovermode: 'x unified',
    }, extra);
  };

  function renderHistoryChart() {
    const hist = DATA.history;
    const fcMonths = DATA.forecast.months;
    const connectX = [hist[hist.length - 1].date, ...fcMonths];
    const connectYMean = [hist[hist.length - 1].demand, ...DATA.forecast.ARIMA];
    const connectY025 = [hist[hist.length - 1].demand, ...pi.ARIMA.p025];
    const connectY975 = [hist[hist.length - 1].demand, ...pi.ARIMA.p975];
    const connectY10 = [hist[hist.length - 1].demand, ...pi.ARIMA.p10];
    const connectY90 = [hist[hist.length - 1].demand, ...pi.ARIMA.p90];

    const traces = [
      // 95% band
      { x: connectX, y: connectY975, name: '95% PI upper', mode: 'lines',
        line: { width: 0 }, hoverinfo: 'skip', showlegend: false },
      { x: connectX, y: connectY025, name: '95% prediction interval', mode: 'lines',
        line: { width: 0 }, fill: 'tonexty',
        fillcolor: 'rgba(37, 99, 235, 0.10)', hoverinfo: 'skip' },
      // 80% band
      { x: connectX, y: connectY90, name: '80% PI upper', mode: 'lines',
        line: { width: 0 }, hoverinfo: 'skip', showlegend: false },
      { x: connectX, y: connectY10, name: '80% prediction interval', mode: 'lines',
        line: { width: 0 }, fill: 'tonexty',
        fillcolor: 'rgba(37, 99, 235, 0.20)', hoverinfo: 'skip' },
      // history
      { x: hist.map(h => h.date), y: hist.map(h => h.demand),
        name: 'Historical', mode: 'lines', line: { color: css('--ink'), width: 2 } },
      // ARIMA mean forecast
      { x: connectX, y: connectYMean, name: 'ARIMA forecast',
        mode: 'lines+markers', line: { color: MODEL_COLOR.ARIMA, width: 2.5, dash: 'dot' },
        marker: { size: 8 } },
      // RF + XGB forecast lines (dotted)
      { x: [hist[hist.length - 1].date, ...fcMonths],
        y: [hist[hist.length - 1].demand, ...DATA.forecast.RandomForest],
        name: 'Random Forest', mode: 'lines+markers',
        line: { color: MODEL_COLOR.RandomForest, width: 1.5, dash: 'dash' },
        marker: { size: 6 } },
      { x: [hist[hist.length - 1].date, ...fcMonths],
        y: [hist[hist.length - 1].demand, ...DATA.forecast.XGBoost],
        name: 'XGBoost', mode: 'lines+markers',
        line: { color: MODEL_COLOR.XGBoost, width: 1.5, dash: 'dash' },
        marker: { size: 6 } },
    ];
    Plotly.react('historyChart', traces, plotLayout({ yaxis: { title: 'Units' } }), PLOT_CONFIG);
  }

  function renderBacktest() {
    const months = DATA.backtest.test_months;
    const actual = DATA.backtest.actual;
    const traces = [
      { x: months, y: actual, name: 'Actual', mode: 'lines+markers',
        line: { color: MODEL_COLOR.Actual, width: 2.5 }, marker: { size: 8 } },
    ];
    CHIP_MODELS.forEach(m => {
      if (!activeChips.has(m)) return;
      traces.push({
        x: months, y: DATA.backtest.predictions[m],
        name: MODEL_LABEL[m], mode: 'lines+markers',
        line: { color: MODEL_COLOR[m], width: 1.8, dash: m === 'Naive' ? 'dot' : 'solid' },
        marker: { size: 6 },
      });
    });
    Plotly.react('backtestChart', traces, plotLayout({ yaxis: { title: 'Units' } }), PLOT_CONFIG);
  }

  function renderWalkForward() {
    const steps = DATA.walk_forward.per_step;
    const months = steps.map(s => s.month);
    const traces = [
      { x: months, y: steps.map(s => s.actual), name: 'Actual', mode: 'lines+markers',
        line: { color: MODEL_COLOR.Actual, width: 2.5 }, marker: { size: 8 } },
    ];
    ['Naive', 'ARIMA', 'RandomForest', 'XGBoost'].forEach(m => {
      traces.push({
        x: months, y: steps.map(s => s[m]),
        name: MODEL_LABEL[m], mode: 'lines+markers',
        line: { color: MODEL_COLOR[m], width: 1.8, dash: m === 'Naive' ? 'dot' : 'solid' },
        marker: { size: 6 },
      });
    });
    Plotly.react('walkforwardChart', traces,
      plotLayout({ yaxis: { title: 'Units' } }), PLOT_CONFIG);
  }

  function renderMetricsBar() {
    const models = ['Naive', 'ARIMA', 'RandomForest', 'XGBoost'];
    const mapes = models.map(m => DATA.metrics[m].MAPE);
    const wapes = models.map(m => DATA.metrics[m].WAPE);
    const traces = [
      { x: models.map(m => MODEL_LABEL[m]), y: mapes, name: 'MAPE (%)', type: 'bar',
        marker: { color: css('--accent') } },
      { x: models.map(m => MODEL_LABEL[m]), y: wapes, name: 'WAPE (%)', type: 'bar',
        marker: { color: css('--success') } },
    ];
    Plotly.react('metricsBar', traces,
      plotLayout({ barmode: 'group', yaxis: { title: 'Error %', ticksuffix: '%' } }),
      PLOT_CONFIG);
  }

  function renderFeatureImportance() {
    // Pulled from logs by regex — build import. map from each tree model
    const parse = (logText) => {
      const out = {};
      const re = /importance\s+(\w+)\s+([0-9.]+)/g;
      let m;
      while ((m = re.exec(logText))) out[m[1]] = parseFloat(m[2]);
      return out;
    };
    const rf = parse(DATA.logs.RandomForest || '');
    const xgb = parse(DATA.logs.XGBoost || '');
    const feats = Object.keys(rf).length ? Object.keys(rf) :
                  (Object.keys(xgb).length ? Object.keys(xgb) : []);
    if (!feats.length) {
      document.getElementById('featureImportanceChart').classList.add('hidden');
      return;
    }
    feats.sort((a, b) => (rf[b] || 0) + (xgb[b] || 0) - (rf[a] || 0) - (xgb[a] || 0));
    const traces = [
      { y: feats, x: feats.map(f => rf[f] || 0), name: 'Random Forest',
        type: 'bar', orientation: 'h', marker: { color: MODEL_COLOR.RandomForest } },
      { y: feats, x: feats.map(f => xgb[f] || 0), name: 'XGBoost',
        type: 'bar', orientation: 'h', marker: { color: MODEL_COLOR.XGBoost } },
    ];
    Plotly.react('featureImportanceChart', traces,
      plotLayout({ barmode: 'group',
                   xaxis: { title: 'Feature importance' },
                   yaxis: { automargin: true, tickformat: '' },
                   margin: { t: 20, r: 20, b: 44, l: 110 } }),
      PLOT_CONFIG);
  }

  // Chart renderers indexed by the tab they live in
  const TAB_CHARTS = {
    forecast:    [renderHistoryChart],
    backtest:    [renderBacktest],
    walkforward: [renderWalkForward],
    models:      [renderMetricsBar, renderFeatureImportance],
  };
  function renderPlotly() {
    // re-render every chart (needed after theme switch)
    Object.values(TAB_CHARTS).flat().forEach(fn => {
      try { fn(); } catch (e) { /* container may be hidden */ }
    });
  }
  function renderTab(tab) {
    const fns = TAB_CHARTS[tab] || [];
    requestAnimationFrame(() => fns.forEach(fn => { try { fn(); } catch (e) {} }));
  }
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', renderPlotly);

  // ---------- Tab switching ----------
  const tabNav = document.getElementById('tabNav');
  const tabContent = document.getElementById('tabContent');
  function activateTab(tabId) {
    tabNav.querySelectorAll('.tab-nav-item').forEach(el =>
      el.classList.toggle('active', el.dataset.tab === tabId));
    tabContent.querySelectorAll('section').forEach(el =>
      el.classList.toggle('active', el.dataset.tab === tabId));
    try { localStorage.setItem('bev-active-tab', tabId); } catch (e) {}
    try { history.replaceState(null, '', '#' + tabId); } catch (e) {}
    renderTab(tabId);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
  tabNav.addEventListener('click', e => {
    const btn = e.target.closest('.tab-nav-item'); if (!btn) return;
    activateTab(btn.dataset.tab);
  });
  // Restore last tab (or from URL hash)
  let initial = (location.hash || '').replace('#', '');
  if (!initial) { try { initial = localStorage.getItem('bev-active-tab') || ''; } catch (e) {} }
  if (initial && tabNav.querySelector(`[data-tab="${initial}"]`)) activateTab(initial);
  else renderTab('overview');

  // Also respond to manual hash edits / browser back-forward within the same page
  window.addEventListener('hashchange', () => {
    const h = (location.hash || '').replace('#', '');
    if (h && tabNav.querySelector(`[data-tab="${h}"]`)) activateTab(h);
  });

  // ============================================================================
  //  AI Chatbot
  // ============================================================================
  const chatWindow   = document.getElementById('chatWindow');
  const chatForm     = document.getElementById('chatForm');
  const chatInput    = document.getElementById('chatInput');
  const chatClear    = document.getElementById('chatClear');
  const chatSuggests = document.getElementById('chatSuggestions');
  const chatHealthDot   = document.getElementById('chatHealthDot');
  const chatHealthLabel = document.getElementById('chatHealthLabel');
  const chatModelTag    = document.getElementById('chatModelTag');
  const chatStatusDot   = document.getElementById('chatStatusDot');

  const CHAT_STORE = 'bev-chat-history';
  let chatHistory = [];
  try { chatHistory = JSON.parse(localStorage.getItem(CHAT_STORE) || '[]'); } catch (e) {}

  const persistChat = () => {
    try { localStorage.setItem(CHAT_STORE, JSON.stringify(chatHistory.slice(-40))); } catch (e) {}
  };

  const renderChat = () => {
    if (chatHistory.length === 0) {
      chatWindow.innerHTML = '<div class="chat-empty">No conversation yet. Ask a question below or click a suggestion.</div>';
      return;
    }
    chatWindow.innerHTML = chatHistory.map(m => {
      const avatar = m.role === 'user' ? 'U' : (m.role === 'error' ? '!' : 'AI');
      const meta = m.meta ? `<div class="meta">${m.meta}</div>` : '';
      return `<div class="chat-msg ${m.role}${m.typing ? ' chat-typing' : ''}">
        <div class="avatar">${avatar}</div>
        <div><div class="bubble">${escapeHTML(m.content || '')}</div>${meta}</div>
      </div>`;
    }).join('');
    chatWindow.scrollTop = chatWindow.scrollHeight;
  };

  const health = async () => {
    try {
      const r = await fetch('/chat/logs', { method: 'GET' });
      if (!r.ok) throw new Error('bad status');
      chatHealthDot.style.background = 'var(--success)';
      chatHealthLabel.textContent = 'server online';
      chatStatusDot.style.color = 'var(--success)';
    } catch (e) {
      chatHealthDot.style.background = 'var(--danger)';
      chatHealthLabel.textContent = 'server offline (run: python serve.py)';
      chatStatusDot.style.color = 'var(--danger)';
      chatModelTag.textContent = 'offline';
    }
  };
  health();

  const sendChat = async (text) => {
    if (!text || !text.trim()) return;
    chatHistory.push({ role: 'user', content: text });
    const typingIdx = chatHistory.push({ role: 'assistant', content: '', typing: true }) - 1;
    renderChat(); persistChat();

    const sendStart = performance.now();
    try {
      const historyForServer = chatHistory
        .filter(m => !m.typing && (m.role === 'user' || m.role === 'assistant'))
        .slice(-6);
      const r = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: historyForServer }),
      });
      const payload = await r.json();
      const dt = ((performance.now() - sendStart) / 1000).toFixed(2);
      if (!r.ok) {
        chatHistory[typingIdx] = {
          role: 'error',
          content: `${payload.error || 'request failed'}${payload.detail ? ' — ' + payload.detail : ''}`,
          meta: `HTTP ${r.status} · ${dt}s`,
        };
      } else {
        const u = payload.usage || {};
        const tokMeta = u.total_tokens ? `${u.prompt_tokens}→${u.completion_tokens} tok` : '';
        chatHistory[typingIdx] = {
          role: 'assistant',
          content: payload.answer || '(empty response)',
          meta: `${payload.model || ''} · ${payload.latency_s || dt}s${tokMeta ? ' · ' + tokMeta : ''}`,
        };
        if (payload.model) chatModelTag.textContent = `${payload.model} · live`;
      }
    } catch (e) {
      chatHistory[typingIdx] = {
        role: 'error',
        content: `network error: ${e.message}`,
        meta: 'is serve.py running on :8765?',
      };
    }
    renderChat(); persistChat();
    // nudge the logs tab to refresh its chatbot subsection next time it is opened
    if (typeof refreshChatbotLog === 'function') refreshChatbotLog();
  };

  chatForm.addEventListener('submit', e => {
    e.preventDefault();
    const t = chatInput.value.trim();
    if (!t) return;
    chatInput.value = '';
    sendChat(t);
  });
  chatSuggests.addEventListener('click', e => {
    const chip = e.target.closest('.chip'); if (!chip) return;
    sendChat(chip.dataset.q);
  });
  chatClear.addEventListener('click', () => {
    if (!confirm('Clear the chat window? (Server-side log stays.)')) return;
    chatHistory = []; persistChat(); renderChat();
  });

  renderChat();

  // ============================================================================
  //  Chatbot sub-tab inside Training Logs (reads from /chat/logs)
  // ============================================================================
  function refreshChatbotLog() {
    fetch('/chat/logs').then(r => r.json()).then(data => {
      const lines = (data.log || '').trim().split('\n').filter(Boolean);
      const parsed = lines.map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean);
      // Format: timestamp + Q/A pair
      const text = parsed.map(e => {
        const ts = e.ts || '';
        if (!e.ok) {
          return `[${ts}] FAILED ${e.model || ''}\n  > ${e.query}\n  ! ${e.error}\n  (${e.latency_s}s)`;
        }
        const u = (e.prompt_tokens && e.completion_tokens) ? ` (${e.prompt_tokens}→${e.completion_tokens} tok)` : '';
        return `[${ts}] ${e.model}  ${e.latency_s}s${u}\n  USER: ${e.query}\n  AI:   ${(e.answer || '').replace(/\n/g, '\n        ')}`;
      }).join('\n\n');
      // Inject or update the Chatbot entry in DATA.logs so the log pane picks it up.
      logs.Chatbot = text || '(no chatbot queries logged yet)';
      if (!logModels.includes('Chatbot')) {
        logModels.push('Chatbot');
      }
      paintTabs();
      if (activeLog === 'Chatbot') paintPane();
    }).catch(e => {
      logs.Chatbot = `(could not load /chat/logs: ${e.message})`;
      if (!logModels.includes('Chatbot')) { logModels.push('Chatbot'); paintTabs(); }
      if (activeLog === 'Chatbot') paintPane();
    });
  }
  refreshChatbotLog();

  // ---------- Logs panel ----------
  const logs = DATA.logs || {};
  const logModels = Object.keys(logs);
  // Preferred order
  const ORDER = ['Pipeline', 'Naive', 'ARIMA', 'RandomForest', 'XGBoost', 'WalkForward', 'Forecast', 'LLM'];
  logModels.sort((a, b) => {
    const ia = ORDER.indexOf(a), ib = ORDER.indexOf(b);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  let activeLog = logModels[0] || null;

  const tabsEl = document.getElementById('logTabs');
  const paneEl = document.getElementById('logPane');
  const searchEl = document.getElementById('logSearch');

  const paintTabs = () => {
    tabsEl.innerHTML = logModels.map(m =>
      `<div class="log-tab ${m === activeLog ? 'active' : ''}" data-m="${m}">${m}</div>`
    ).join('');
  };
  const paintPane = () => {
    if (!activeLog) { paneEl.textContent = '(no logs captured)'; return; }
    const raw = logs[activeLog] || '';
    const q = searchEl.value.trim();
    let lines = raw.split('\n');
    if (q) {
      try {
        const re = new RegExp(q, 'i');
        lines = lines.filter(l => re.test(l));
      } catch (e) {
        lines = lines.filter(l => l.toLowerCase().includes(q.toLowerCase()));
      }
    }
    let html = lines.map(escapeHTML).join('\n');
    if (q) {
      try {
        const re = new RegExp('(' + q + ')', 'gi');
        html = html.replace(re, '<mark>$1</mark>');
      } catch (e) {}
    }
    paneEl.innerHTML = html || '(no lines match)';
  };
  paintTabs(); paintPane();
  tabsEl.addEventListener('click', e => {
    const t = e.target.closest('.log-tab'); if (!t) return;
    activeLog = t.dataset.m; paintTabs(); paintPane();
  });
  searchEl.addEventListener('input', paintPane);

  document.getElementById('logCopy').addEventListener('click', () => {
    navigator.clipboard.writeText(logs[activeLog] || '').then(
      () => { const b = document.getElementById('logCopy'); const o = b.textContent;
              b.textContent = 'Copied'; setTimeout(() => b.textContent = o, 1200); },
      () => alert('Copy failed'));
  });
  document.getElementById('logDownload').addEventListener('click', () => {
    const blob = new Blob([logs[activeLog] || ''], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${activeLog}.log`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  });

  // LLM model name from source badge
  const srcMatch = (interp._source || '').match(/^nvidia:(.+)$/);
  if (srcMatch) document.getElementById('llmModelName').textContent = srcMatch[1];
</script>
</body>
</html>
"""


def main():
    if not RESULTS.exists():
        print(f"ERROR: {RESULTS} not found — run `python pipeline.py` first.")
        sys.exit(1)

    # Read Plotly blob from existing dashboard.html (if present); otherwise we
    # cannot proceed without a Plotly bundle on disk.
    if not EXISTING.exists():
        print(f"ERROR: {EXISTING} not found — need an existing dashboard.html "
              f"to extract the inlined Plotly.js bundle.")
        sys.exit(1)
    html = EXISTING.read_text(encoding="utf-8")
    plotly_blob = extract_plotly_blob(html)
    print(f"Extracted Plotly bundle: {len(plotly_blob):,} chars")

    # Load results
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    data_json = json.dumps(results, ensure_ascii=False)
    print(f"Inlined results.json: {len(data_json):,} chars")

    # Splice
    out_html = (
        SHELL_TEMPLATE
        .replace("__PLOTLY_BLOB__", plotly_blob)
        .replace("__DATA_JSON__", data_json)
    )
    OUT.write_text(out_html, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
