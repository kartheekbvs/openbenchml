# How to deploy the v2.5 fix to Render

The fix for the notebook output bug + the new Files tab + git clone + VS Code-style upload
was committed locally but **never pushed to GitHub** (the sandbox has no git credentials).

Render rebuilds automatically when `main` on GitHub changes — so once these commits are
pushed, your live site at https://openbenchml.onrender.com will pick them up in ~2–3 minutes.

## Option A — Push from your own machine (easiest)

If you have the repo cloned locally on your laptop:

```bash
# 1. Pull the patch file from this session
#    (it's at /home/z/my-project/download/v25-unpushed-commits.patch)

# 2. In your local clone of kartheekbvs/openbenchml:
cd openbenchml
git checkout main
git pull origin main

# 3. Apply the patch
git am < /path/to/v25-unpushed-commits.patch

# 4. Push to GitHub — Render will auto-rebuild
git push origin main
```

## Option B — Give me a GitHub Personal Access Token

If you'd rather I push for you:

1. Go to https://github.com/settings/tokens → "Generate new token (classic)"
2. Tick the `repo` scope only
3. Copy the token (starts with `ghp_`)
4. Paste it back to me here

I'll then run `git push` with the token and the live site will rebuild in ~2–3 minutes.

## Option C — Just copy the changed files

If neither of the above works, the only files that actually changed in v2.5 are:

- `templates/notebook.html`  (frontend: Files tab, upload UI, git-clone hint)
- `app/routes/notebook.py`   (backend: /api/notebook/files/* endpoints)
- `app/services/code_runner_service.py` (chroot-ish file access for cells)

You can copy these three files into your local clone, `git add` + `git commit` + `git push`,
and Render will rebuild.

## After the push

1. Wait ~2–3 minutes for Render to finish building
2. Visit https://openbenchml.onrender.com/notebook
3. **Hard refresh** with Ctrl+Shift+R (or Cmd+Shift+R on Mac) — your browser has
   the old JS cached
4. You should see a "v2.5 files + git clone" badge in the page header
5. Three tabs should appear: **Notebook · Files · Terminal**
6. Run a cell — output should now appear below it as expected

## What was fixed

- The JS error `Cannot read properties of undefined (reading 'location')` at notebook:68
  was from the OLD cached version of the page. The current code has no `.location` access
  outside of `location.protocol` / `location.host` in the WebSocket URL builder, both of
  which are safe.
- Cell output visibility is controlled by the `has-content` CSS class on `.cell-output`.
  The `renderOutput()` function adds this class after setting innerHTML, so output is
  visible by default after a successful run.
- If you still don't see output after the push + hard refresh, open DevTools → Console
  and look for any new errors — paste them back to me and I'll fix them.
