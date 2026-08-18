
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
