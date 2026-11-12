# Pushing updates to GitHub

The repo is already live at **https://github.com/rd51/beverage-demand-forecasting** and the local folder is already configured to push there (`origin` remote, `main` branch tracking).

This guide covers (1) how to push any future changes, and (2) how to verify a commit is safe before pushing.

---

## Push a new change — VS Code (easiest)

1. Open this folder in VS Code (**File → Open Folder** → `Problems & Exercises 2`).
2. Make your edits, save files.
3. Click the **Source Control** icon in the left sidebar (branching-tree icon) or press **Ctrl+Shift+G**.
4. Your changed files appear under "Changes". Hover over each → click the **+** to stage, or click the **+** next to "Changes" to stage all.
5. Type a commit message in the box at the top (one line, imperative — e.g. `Add new chart for Q4 outlook`).
6. Click the **✓ Commit** button above the message.
7. Click the **"Sync Changes"** button that appears (or the ⋯ menu → **Push**).

Done. Refresh the GitHub page to see it live.

---

## Push a new change — Terminal (3 commands)

```bash
git add -A
git commit -m "describe what changed"
git push
```

That's it — the remote and branch are already set, no `-u origin main` needed.

---

## Before pushing — sanity check

Before any push, run:

```bash
git status
git diff --stat HEAD
```

**Red flags to watch for:**
- `.env` appearing in the diff → stop. `.gitignore` should catch this but double-check.
- `chatbot_log.jsonl` appearing → stop. Same reason.
- A single huge file (> 50 MB) → GitHub will warn or reject. If it's a Plotly rebuild of `dashboard.html`, that's expected (~5 MB).

If you see a secret, don't push:

```bash
git reset HEAD .env               # unstage it
echo ".env" >> .gitignore         # make sure it stays ignored (it already is)
```

---

## If you accidentally commit a secret

**Treat the key as compromised** — rotate it immediately:

1. Go to https://build.nvidia.com/ → **Get API Key** → click **"Revoke"** on the old one → generate a new one.
2. Paste the new key into `.env`.
3. Undo the bad commit:
   ```bash
   git reset --soft HEAD~1   # keep the file changes but undo the commit
   git restore --staged .env # unstage
   git commit -m "redo without secret"
   git push --force-with-lease
   ```
4. If the bad commit is already on GitHub, the key is in git history — a `force-push` removes it from the tip but NOT from the history. You must rotate the key regardless. Use `git filter-repo` or GitHub's secret-scanning workflow to purge the history (ask me when it happens).

---

## Fix the author on a commit

If VS Code committed under a different account:

```bash
git -c user.email="rakshanda0501@gmail.com" -c user.name="Rakshanda Dhote" commit --amend
git push --force-with-lease   # only if the bad commit is already pushed
```

---

## Current repo state

- **Remote:** `origin` → `https://github.com/rd51/beverage-demand-forecasting.git`
- **Branch:** `main` (tracking `origin/main`)
- **Last commit:** run `git log --oneline -1` to see
- **Ignored files:** `.env`, `chatbot_log.jsonl`, `__pycache__/`, editor/OS noise — see `.gitignore`

---

## Check what's in the repo without cloning

```bash
git ls-tree -r origin/main --name-only
```

Or just open https://github.com/rd51/beverage-demand-forecasting in a browser.

---

## Running the AI Chatbot after cloning

If you (or anyone else) clones this repo and wants the live chatbot panel in the dashboard, here's the short path. For troubleshooting and model options see [`CHATBOT_GUIDE.md`](CHATBOT_GUIDE.md).

### 1. Install Python deps

```bash
pip install -r requirements.txt
```

### 2. Get a free NVIDIA API key

- Go to https://build.nvidia.com/
- Sign in (Google / GitHub / email — all free)
- Click any model card → **"Get API Key"** → copy it (starts with `nvapi-`)

### 3. Create `.env` in the project root

Copy `.env.example` to `.env` and paste the key:

```
NVIDIA_API_KEY=nvapi-your-actual-key-here
```

`.env` is already in `.gitignore` — it will never be committed.

### 4. Start the server

```bash
python serve.py
```

You should see:
```
serving ... on http://127.0.0.1:8765  (chatbot: ON)
```

### 5. Open the dashboard and use the chatbot

Open http://127.0.0.1:8765/dashboard.html in a browser → click the **AI Chatbot** tab (bottom of the left sidebar, 💬 icon). The status dot should be green ("server online"). Type a question or click a suggestion chip.

### What if the server isn't running?

The dashboard still works — all 8 analytical tabs render from the baked-in `results.json` (including the static LLM Interpretation card in tab 02, which was authored by Llama at pipeline-run time). Only the live Chatbot panel needs the server. The sidebar will show a red dot and the panel will say "server offline — run: python serve.py".

### Logs

- Server-side: `chatbot_log.jsonl` (append-only, one JSON per line — timestamp, model, query, answer, latency, tokens)
- Dashboard view: **Training Logs** tab → **Chatbot** sub-tab (chronological, searchable, downloadable)
- Browser-side: last 40 messages persisted in `localStorage` so the chat window survives page reloads
