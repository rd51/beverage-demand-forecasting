# Push to GitHub from VS Code

The local repo is already initialized and the first commit (`84c37d0`) is in place. Only the push to a remote is left. Three ways to do it — pick whichever is easiest.

---

## Option A — VS Code UI (fully graphical, easiest)

1. Open this folder in VS Code (**File → Open Folder** → `Problems & Exercises 2`).
2. Click the **Source Control** icon in the left sidebar (looks like a branching tree) or press **Ctrl+Shift+G**.
3. You should see "1 commit ahead of origin" or similar — but no remote yet.
4. In the Source Control panel, click the **three-dot menu (⋯)** at the top → **Remote → Add Remote**.
5. VS Code asks:
   - **URL of the remote:** paste your GitHub repo URL, e.g.
     ```
     https://github.com/rakshanda0501/beverage-forecasting.git
     ```
   - **Remote name:** type `origin`
6. Click the **⋯** menu again → **Push to…** → pick `origin` → `main`.
7. If prompted, sign in to GitHub (browser popup). Done — refresh your GitHub repo page.

---

## Option B — VS Code "Publish to GitHub" (creates the repo for you)

Useful if you haven't created the GitHub repo yet.

1. Open this folder in VS Code.
2. Open **Source Control** (Ctrl+Shift+G).
3. Click the big blue **"Publish to GitHub"** button at the top.
4. VS Code asks:
   - Choose **public** or **private**
   - Repo name (defaults to folder name)
5. It creates the repo and pushes in one step. Done.

---

## Option C — Terminal (3 commands)

If you prefer the terminal (VS Code's integrated terminal works):

```bash
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git branch -M main
git push -u origin main
```

Replace `YOUR-USERNAME/YOUR-REPO` with yours. If GitHub asks for auth, use a Personal Access Token (not your password) — create one at https://github.com/settings/tokens with "repo" scope.

---

## Verify before pushing

Before any push, the terminal command:

```bash
git log --stat -1
```

should show **14 files** in the commit, and `.env` and `chatbot_log.jsonl` should **not** be in the list. If they are, stop and ping me.

---

## If you need to change the commit message / author later

```bash
git -c user.email="rakshanda0501@gmail.com" -c user.name="Rakshanda Dhote" commit --amend
```

---

## After the first push

For any later change (add a new feature, update the dashboard, etc.):

```bash
git add -A
git commit -m "describe what changed"
git push
```

Or just use the VS Code Source Control panel — stage files with `+`, type a message, click the ✓ checkmark, then click the sync button.

---

## Current repo state

- **Branch:** `main`
- **Commits:** 1 (`84c37d0`)
- **Tracked files:** 14 (all project code + docs)
- **Ignored:** `.env`, `chatbot_log.jsonl`, `__pycache__/`, editor/OS noise — see `.gitignore`
- **Remote:** not set yet (that's step 1 of Option A or C)

Suggested repo names:
- `beverage-demand-forecasting`
- `aio-session2-beverage-forecasting`
- `spjain-aio-beverage-forecast`
