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
