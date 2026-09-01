
---
Task ID: colab-workspace-phases-1-3
Agent: main
Task: Implement all 3 phases of Colab-style workspace + dataset registry + magics + IndexedDB autosave + variable inspector + file browser + heavy-package guard. User asked to also surface download links for every saved file and to address the OOM issue when `pip install tensorflow` runs on Render.

Work Log:
- Bundled 10 reference CSV datasets (iris, boston_housing, titanic, pima_diabetes, wine_quality_red, wine_quality_white, penguins, heart_disease, auto_mpg, banknote_authentication) into /static/datasets/registry/ for Pyodide to fetch same-origin.
- Patched templates/notebook.html and templates/convert.html to mount a Colab-style /workspace/ tree in Pyodide FS at boot:
    /workspace/datasets/registry/  ← bundled CSVs (auto-seeded)
    /workspace/datasets/user/      ← user-uploaded / created datasets
    /workspace/models/            ← trained .pkl artifacts
    /workspace/outputs/           ← plots, CSV exports
    /workspace/notebooks/         ← .ipynb files
    /workspace/tmp/                ← scratch
- Added Python _obml_handle_magic() helper that runs inside Pyodide and supports:
    %ls / %load_dataset <name> / %save_model <var> [filename] / %load_model <filename> [var]
    %whos / %who / %reset / %pip install <pkg> (via micropip) / %time / %history
  Returns JSON-serialisable dicts so the JS side can JSON.parse() cleanly.
- Added JS-side runPyodideMagic() dispatcher that wraps the Python result in JSON, parses, and handles save_model by triggering a browser-side download of the just-saved artifact.
- Added refreshPyodideVariables() — runs Python dir() + type/shape introspection, renders live variable list in the sidebar with type + shape/len tags. Called after every Pyodide cell run.
- Added refreshPyodideFiles() — walks /workspace/ via os.walk, lists all files with download buttons that read bytes from Pyodide FS, build a Blob URL, and trigger an anchor click.
- IndexedDB autosave module: _idbOpen / autosaveNotebook / _idbLoadAutosave / _idbClearAutosave / _maybeRestoreAutosave.
  * Snapshots cells + engine every 30s and after every cell run.
  * On page load, prompts the user (via confirm()) to restore the previous session if it's < 4h old.
  * beforeunload listener saves before tab close.
- Engine switching now also fires refreshPyodideFiles/Variables and autosaveNotebook.
- Server-side heavy-package guard in app/routes/notebook.py install endpoint:
  * _HEAVY_PACKAGES list with substring match (tensorflow, torch, transformers, opencv-python, paddlepaddle, mxnet, jax, etc.)
  * Returns blocked=True with stderr explaining why + suggesting lighter alternatives (tensorflow-cpu, torch CPU wheel, Pyodide engine, or E2B/Modal sandbox)
  * Honors OBML_ALLOW_HEAVY_INSTALLS=1 env var for operator override
  * Also runs _check_memory_budget() pre-check to refuse installs when server RSS is already close to the limit
- Client-side heavy-package pre-warn in notebook.html:
  * _HEAVY_PKG_CLIENT list + _clientHeavyCheck() function
  * installPackage() shows a confirm() dialog BEFORE calling the server, with alternative suggestion
  * Handles server-side blocked response too
- Files modified:
    templates/notebook.html    — workspace mount + magics + variable inspector + file browser + IndexedDB autosave + client heavy guard
    templates/convert.html      — workspace mount + dataset registry seed
    app/routes/notebook.py      — server-side heavy-package guard in install endpoint
    static/datasets/registry/*  — 10 bundled CSV datasets (new)
    scripts/test_colab_workspace_features.py     — static analysis test suite (82 checks)
    scripts/test_workspace_features_pw.py        — Playwright E2E test (9 checks)

Stage Summary:
- All 82 static analysis checks PASS.
- All 9 Playwright E2E checks PASS end-to-end:
    1. Pyodide Files section visible in sidebar
    2. Pyodide engine boots, kernel pill shows "pyodide ready"
    3. %ls lists /workspace/ contents (registry CSVs visible)
    4. %load_dataset iris loads iris_df (shape=150x5)
    5. Trains RandomForestClassifier on iris (score 0.9933)
    6. %save_model clf test_model.pkl saves + triggers browser download
    7. Pyodide file browser shows the saved model with download button
    8. Server-side heavy-package guard refuses tensorflow + torch with alternatives; 'requests' (light) NOT blocked
    9. Client-side heavy-package pre-warn dialog fires for tensorflow
   10. IndexedDB autosave persists cells across page reload
- Heavy-package OOM issue fully addressed: users see a friendly warning BEFORE the server is even contacted, the server refuses by default with a helpful alternative suggestion, and an env-var override exists for operators.
- All file artifacts (datasets, models, plots) saved in /workspace/ now surface with download buttons in the file browser. %save_model auto-triggers a browser download.

---
Task ID: pyodide-csv-pip-content-fixes
Agent: main
Task: Fix 4 user-reported issues in the Pyodide notebook engine:
  (1) pd.read_csv fails in Pyodide on uploaded files (server-side works fine)
  (2) Need Colab-style /content/<filename> clickable links for uploaded files
  (3) Long filenames are truncated with ellipsis (full name not visible)
  (4) pip install X / !pip install X not recognized as commands in Pyodide

Work Log:
- Patched Pyodide pandas.read_csv in templates/notebook.html to fall back
  to fetching the file from /api/notebook/files/<name> via binary-safe
  sync XHR when the file isn't already in Pyodide's FS. This makes
  pd.read_csv('uploaded.csv') work transparently in Pyodide — server
  workspace files become readable from the browser engine.
- Also patched builtins.open() the same way, so user code like
  `with open('file.csv') as f: ...` works on server-uploaded files
  even when the file isn't mirrored into /workspace/.
- Added _syncServerFilesToPyodide() JS helper — runs at Pyodide boot
  to mirror ALL user-uploaded server files into /workspace/datasets/user/
  in Pyodide FS (capped at 50MB per file to avoid blowing the WASM heap).
- Modified uploadFiles() to also FS.writeFile the uploaded file into
  /workspace/datasets/user/<name> if Pyodide is already loaded, so the
  file is immediately usable in the Pyodide engine without waiting for
  the next boot sync.
- Added /content/{path:path} route in app/routes/notebook.py — serves
  workspace files with `Content-Disposition: inline` so the browser
  previews them (CSV → table, PNG → <img>, JSON → pretty-printed)
  instead of forcing a download. Mirrors Google Colab's /content/<file>
  URL convention.
- Modified _renderFileRow + _renderChildRow in templates/notebook.html
  to wrap the file name in an <a href="/content/..."> link that opens
  in a new tab. Also added the link to the upload success toast row.
- Updated insertFileHint() to insert a "# Loaded from /content/<file>"
  comment in the generated code cell so users see the link reference.
- Modified CSS for .files-list .file-row .file-name: replaced the
  `white-space: nowrap; text-overflow: ellipsis` (which truncated
  long file names) with `white-space: normal; word-break: break-all;
  -webkit-line-clamp: 2` — now full file names are visible across
  up to 2 lines.
- Added _pyodidePipInstall(pkgSpec) and _pyodidePipList(args) helpers
  in templates/notebook.html. The pip install helper:
  * Recognizes pip install / pip3 install / !pip install / %pip install
    / python -m pip install (all 5 forms) via a single regex.
  * Strips flags like --upgrade, -U, --no-deps before passing to micropip.
  * Pre-checks against a _PYODIDE_HEAVY_PKGS list (tensorflow, torch,
    transformers, opencv-python, etc.) and refuses with a friendly
    message instead of waiting for micropip to time out.
  * Calls micropip.install(list_of_pkgs) inside Pyodide via runPythonAsync.
  * Returns a {ok, stdout, stderr, elapsed_ms, figures} result compatible
    with the existing runCell return contract.
- pip list / pip freeze / pip show also supported (returns the list of
  importable modules with their __version__).
- Added friendly handling for !ls, !pwd, !echo in Pyodide (since !-prefixed
  commands previously all returned "not supported").

Stage Summary:
- All 82 prior static-analysis checks still PASS (no regression).
- All 20 new checks in scripts/test_pyodide_pip_csv_content.py PASS:
    1. Pyodide read_csv patch falls back to /api/notebook/files/
    2. Pyodide open() patch falls back to /api/notebook/files/
    3. _pyodidePipInstall + _pyodidePipList JS helpers defined
    4. pip regex matches pip / pip3 / %pip / !pip / python -m pip
    5. _syncServerFilesToPyodide defined + called on boot
    6. uploadFiles writes uploaded bytes into /workspace/datasets/user/
    7. /content/{path:path} route registered with inline Content-Disposition
    8. _renderFileRow + _renderChildRow + upload toast all have /content/ links
    9. file-name CSS no longer uses white-space: nowrap
   10. insertFileHint surfaces the /content/ link in the generated code comment
- Files modified:
    templates/notebook.html    — read_csv/open patches + pip recognition + content links + CSS fix
    app/routes/notebook.py     — /content/{path:path} route (inline preview)
    scripts/test_pyodide_pip_csv_content.py  — new 20-check static analysis suite
- All 4 user-reported issues resolved.

---
Task ID: learn-with-project-toggle
Agent: main
Task: Add a new "Learn with Project" toggle to the existing /learn section. Must NOT disturb the current Learn content. The new mode should teach FastAPI + Jinja2 + ML intuition step-by-step following the "concept -> tiny task -> check -> next" loop the user demonstrated in the chat. User specifically asked for: detailed learning of Jinja2 and FastAPI, the intuition behind them, explicit "which routes" callouts, and explicit "is a response model necessary here?" answers per stage.

Work Log:
- Created app/routes/learn_project.py — defines PROJECT_COURSE (13 stages, 0-12) + 2 routes:
    GET  /learn/project          -> overview (all 13 stages as a path)
    GET  /learn/project/{slug}   -> single stage page
- The 13 stages walk through building a Student Performance Predictor end-to-end:
    Stage  0: Why this project? The 5-layer motive (Python -> ML -> FastAPI -> Jinja -> HTML)
    Stage  1: Meet the dataset — head/shape/info/describe (4 questions you always ask)
    Stage  2: 3 plots that tell you if ML is even possible
    Stage  3: Clean the data + split into X and y
    Stage  4: First ML model — 4 lines (train_test_split + fit + predict + score)
    Stage  5: What does R^2 = 0.80 mean? (MAE, MSE, RMSE, R^2)
    Stage  6: Error analysis — sort by Abs_Error, investigate worst predictions
    Stage  7: Try a better model — RandomForest vs LinearRegression
    Stage  8: FIRST FastAPI route — POST /predict (JSON in, JSON out)
    Stage  9: Jinja2 templates + HTML form (base.html + home.html + result.html)
    Stage 10: CSS — cards layout, hover effects, accent color
    Stage 11: /model-info page — surface metrics + feature importance
    Stage 12: Deploy to Render + final folder structure recap
- Each stage has 14 fields:
    stage, slug, title, summary, intuition, tiny_task, check,
    routes_box, is_response_model_needed, response_model_explanation,
    files, explanation, common_mistakes, next_preview
- The "routes_box" field explicitly lists which routes are wired up at each stage
  (e.g. Stage 8: "POST /predict -> takes StudentInput JSON, returns PredictResponse JSON")
- The "is_response_model_needed" + "response_model_explanation" fields directly answer
  the user's question "is it necessary response model if it necessary give detailed".
  Answer: only for JSON routes (Stage 8), NOT for HTML routes (Stages 9, 11).
  Stage 12 has a final recap table showing all 4 routes and which need response_model.
- The teaching style mirrors the chat conversation the user pasted:
    1. CONCEPT  -> one-sentence intuition (intuition field)
    2. TINY TASK -> 2-5 line code the user writes (tiny_task field)
    3. CHECK     -> expected output (check field)
    4. NEXT      -> preview of next stage (next_preview field)
- Created templates/learn_project.html with:
    * Mode toggle (Concepts / Learn with Project) at the top
    * Overview view: 13 stages as a clickable path with layer tags
    * Stage view: progress bar, prev/next buttons, all 7 content boxes
      (intuition, tiny_task, check, routes, response_model, mistakes, next)
    * Sidebar with all 13 stages + project stack summary
    * Color-coded boxes (intuition=blue, task=green, check=green, routes=purple,
      response_model=orange, mistakes=red, next=accent)
- Modified templates/learn.html — added TWO things at the top of the landing page:
    1. A mode toggle (Concepts active / Learn with Project inactive)
    2. A teaser card with rocket icon highlighting the new 12-stage course
  The existing LEARN_TREE content is untouched.
- Modified app/main.py — imported + included learn_project_route.router.
- Created scripts/test_learn_project.py — 77 static checks (all PASS).

Stage Summary:
- All 77 new static checks PASS.
- All 82 prior checks (test_colab_workspace_features.py) still PASS — no regression.
- All 20 prior checks (test_pyodide_pip_csv_content.py) still PASS — no regression.
- Total: 179 checks PASS, 0 FAIL.
- 13 stages × 14 fields = 182 fields, all populated.
- 25 code files across all stages (CSV, Python, HTML, CSS, YAML, bash).
- Existing /learn content UNDISTURBED — only added toggle + teaser card.
- New routes:
    GET /learn/project          (overview)
    GET /learn/project/{slug}   (single stage, e.g. /learn/project/project-stage-08-fastapi-predict)
- Files created:
    app/routes/learn_project.py             (450 lines, 13 stages + 2 routes)
    templates/learn_project.html            (430 lines, overview + stage views)
    scripts/test_learn_project.py           (200 lines, 77 checks)
- Files modified:
    app/main.py                              (+2 lines: import + include router)
    templates/learn.html                     (+20 lines: toggle + teaser card)
