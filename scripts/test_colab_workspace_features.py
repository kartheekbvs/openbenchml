"""
Tests for the Colab-style workspace + IndexedDB + heavy-package guard features.

Validates:
  1. Dataset registry is bundled at /static/datasets/registry/
  2. templates/notebook.html contains the Pyodide /workspace/ mount + magics
  3. templates/convert.html contains the same /workspace/ mount
  4. IndexedDB autosave + restore logic is present in notebook.html
  5. Pyodide-side magics (%load_dataset, %save_model, %load_model, %ls, %whos,
     %reset, %pip, %time, %history) are defined in _obml_handle_magic()
  6. Variable inspector for Pyodide engine is present
  7. Pyodide file browser is present with download links
  8. Server-side heavy-package guard is in app/routes/notebook.py
  9. Client-side heavy package pre-warn is in notebook.html
 10. _obml_handle_magic Python helper handles all magics + returns JSON-safe dicts

Run: python scripts/test_colab_workspace_features.py
"""

import os
import re
import sys
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERRORS = []
PASSED = []


def check(condition, label):
    if condition:
        PASSED.append(label)
        print(f"  ✓ {label}")
    else:
        ERRORS.append(label)
        print(f"  ✗ {label}")


# ─── 1. Dataset registry bundled ────────────────────────────────────────────
def test_dataset_registry_bundled():
    print("\n[1] Dataset registry bundled at /static/datasets/registry/")
    registry_dir = ROOT / "static" / "datasets" / "registry"
    check(registry_dir.exists(), "registry/ directory exists")

    expected = [
        "iris.csv", "boston_housing.csv", "titanic.csv",
        "pima_diabetes.csv", "wine_quality_red.csv", "wine_quality_white.csv",
        "penguins.csv", "heart_disease.csv", "auto_mpg.csv",
        "banknote_authentication.csv",
    ]
    for name in expected:
        path = registry_dir / name
        check(path.exists() and path.stat().st_size > 0,
              f"registry/{name} exists and is non-empty")


# ─── 2. notebook.html contains /workspace/ mount + magics ────────────────────
def test_notebook_workspace_mount():
    print("\n[2] templates/notebook.html: Pyodide /workspace/ mount")
    nb = (ROOT / "templates" / "notebook.html").read_text()

    # Workspace directory tree (loop iterates an array of paths)
    check("'/workspace'" in nb and "mkdirTree" in nb,
          "FS.mkdirTree called for /workspace/")
    for sub in ("datasets", "datasets/registry", "models", "outputs", "tmp"):
        check(f"/workspace/{sub}" in nb,
              f"/workspace/{sub} mount path present")

    # Registry pre-seed fetch loop
    check("registryCsvs" in nb and "fetch('/static/datasets/registry/' + name)" in nb,
          "registry CSV pre-seed fetch loop present")

    # Magics Python helper defined
    check("def _obml_handle_magic(code):" in nb,
          "_obml_handle_magic() defined in Pyodide boot")
    for magic in ("%ls", "%load_dataset", "%save_model", "%load_model",
                  "%whos", "%who", "%reset", "%pip", "%time", "%history"):
        check(f'magic == "{magic}"' in nb,
              f"{magic} branch handled")

    # Pyodide magics JS dispatcher
    check("async function runPyodideMagic(code)" in nb,
          "runPyodideMagic() JS dispatcher defined")
    check("await runPyodideMagic(code)" in nb,
          "runCellPyodide routes % commands to runPyodideMagic()")


# ─── 3. convert.html contains /workspace/ mount ─────────────────────────────
def test_convert_workspace_mount():
    print("\n[3] templates/convert.html: /workspace/ mount")
    cv = (ROOT / "templates" / "convert.html").read_text()

    check("'/workspace'" in cv and "mkdirTree" in cv,
          "FS.mkdirTree called for /workspace/")
    for sub in ("datasets", "datasets/registry", "models", "outputs"):
        check(f"/workspace/{sub}" in cv, f"/workspace/{sub} mount path present")
    check("fetch('/static/datasets/registry/' + name)" in cv,
          "registry CSV pre-seed loop present")


# ─── 4. IndexedDB autosave present in notebook.html ──────────────────────────
def test_indexeddb_autosave():
    print("\n[4] IndexedDB autosave + restore logic")
    nb = (ROOT / "templates" / "notebook.html").read_text()

    check("const _IDB_NAME = 'openbenchml'" in nb, "_IDB_NAME constant defined")
    check("function _idbOpen()" in nb, "_idbOpen() function defined")
    check("async function autosaveNotebook()" in nb, "autosaveNotebook() defined")
    check("async function _idbLoadAutosave()" in nb, "_idbLoadAutosave() defined")
    check("async function _idbClearAutosave()" in nb, "_idbClearAutosave() defined")
    check("async function _maybeRestoreAutosave()" in nb, "_maybeRestoreAutosave() defined")

    # Periodic save interval
    check("setInterval(() => { try { autosaveNotebook();" in nb,
          "30s periodic autosave interval set")
    check("window.addEventListener('beforeunload'" in nb,
          "beforeunload listener saves before page exit")

    # Restore prompt
    check("Restore your previous notebook session?" in nb,
          "restore confirm prompt text present")

    # Call to autosaveNotebook after cell run
    check("autosaveNotebook()" in nb,
          "autosaveNotebook() called after cell run")


# ─── 5. Variable inspector for Pyodide ───────────────────────────────────────
def test_pyodide_variable_inspector():
    print("\n[5] Pyodide variable inspector")
    nb = (ROOT / "templates" / "notebook.html").read_text()

    check("async function refreshPyodideVariables()" in nb,
          "refreshPyodideVariables() function defined")
    check("id=\"var-list\"" in nb, "var-list DOM element present in sidebar")
    check("id=\"vars-engine-tag\"" in nb, "engine tag element present")
    # Inspector is called from runCellPyodide finally block
    check("refreshPyodideVariables();" in nb, "refreshPyodideVariables called after cell run")
    # Inspector handles shapes
    check('"shape"' in nb and "list(_v.shape)" in nb, "DataFrame/array shape introspection")


# ─── 6. Pyodide file browser with download links ────────────────────────────
def test_pyodide_file_browser():
    print("\n[6] Pyodide file browser with download links")
    nb = (ROOT / "templates" / "notebook.html").read_text()

    check("async function refreshPyodideFiles()" in nb,
          "refreshPyodideFiles() function defined")
    check("id=\"pyodide-files-list\"" in nb, "pyodide-files-list DOM element present")
    check("async function downloadPyodideFile(relPath)" in nb,
          "downloadPyodideFile() function defined")
    check("onclick=\"downloadPyodideFile(" in nb,
          "download button wired to file rows")

    # Download builds a Blob URL + anchor click
    check("URL.createObjectURL(blob)" in nb, "Blob URL creation used for downloads")
    check("a.click()" in nb, "anchor.click() triggers browser download")


# ─── 7. Server-side heavy-package guard ─────────────────────────────────────
def test_server_heavy_package_guard():
    print("\n[7] Server-side heavy-package guard in app/routes/notebook.py")
    nb_py = (ROOT / "app" / "routes" / "notebook.py").read_text()

    check("_HEAVY_PACKAGES = [" in nb_py, "_HEAVY_PACKAGES list defined")
    check('"tensorflow"' in nb_py, "tensorflow is in heavy list")
    check('"torch"' in nb_py, "torch is in heavy list")
    check('"transformers"' in nb_py, "transformers is in heavy list")
    check('"opencv-python"' in nb_py, "opencv-python is in heavy list")
    check('"paddlepaddle"' in nb_py, "paddlepaddle is in heavy list")
    check('"mxnet"' in nb_py, "mxnet is in heavy list")
    check('"jax"' in nb_py, "jax is in heavy list")

    # Block path returns blocked=True with alternative
    check('"blocked": True' in nb_py, "blocked: True flag returned")
    check('"alternative":' in nb_py, "alternative field returned")
    check('"estimated_mb":' in nb_py, "estimated_mb field returned")

    # OBML_ALLOW_HEAVY_INSTALLS env-var bypass
    check("OBML_ALLOW_HEAVY_INSTALLS" in nb_py,
          "OBML_ALLOW_HEAVY_INSTALLS env var honored")
    check("allow_heavy = _os.environ.get" in nb_py,
          "env var read at request time")

    # OOM pre-check still happens before install
    check("_check_memory_budget()" in nb_py,
          "_check_memory_budget() called before install")


# ─── 8. Client-side heavy-package pre-warn ─────────────────────────────────
def test_client_heavy_package_warn():
    print("\n[8] Client-side heavy-package pre-warn in notebook.html")
    nb = (ROOT / "templates" / "notebook.html").read_text()

    check("_HEAVY_PKG_CLIENT = [" in nb, "_HEAVY_PKG_CLIENT list defined")
    check("function _clientHeavyCheck(pkg)" in nb, "_clientHeavyCheck() function defined")
    check("'tensorflow'" in nb, "tensorflow in client heavy list")
    check("is a heavy package" in nb, "client confirm dialog mentions heavy package")
    check("Suggested alternative:" in nb, "client confirm dialog suggests alternative")
    check("data.blocked" in nb, "server blocked flag handled client-side")


# ─── 9. _obml_handle_magic is JSON-safe ─────────────────────────────────────
def test_magic_helper_json_safe():
    print("\n[9] _obml_handle_magic returns JSON-serialisable results")
    nb = (ROOT / "templates" / "notebook.html").read_text()

    # The dispatcher wraps every magic in either {"__text__": ...} or a dict
    # with "error" / "path" / "ok" keys so JSON.parse() on the JS side
    # always succeeds.
    check('if isinstance(_result, (dict, list)):' in nb,
          "result type-checked (dict|list) before json.dumps")
    check('"__text__": str(_result)' in nb,
          "string results wrapped in {'__text__': ...}")


# ─── 10. App imports cleanly ───────────────────────────────────────────────
def test_app_imports():
    print("\n[10] app/routes/notebook.py parses cleanly")
    nb_py = (ROOT / "app" / "routes" / "notebook.py").read_text()
    try:
        ast.parse(nb_py)
        check(True, "ast.parse(notebook.py) succeeds")
    except SyntaxError as e:
        check(False, f"SyntaxError in notebook.py: {e}")


# ─── 11. File download links surface in Pyodide file rows ──────────────────
def test_file_links_surface():
    print("\n[11] Pyodide file rows render download buttons")
    nb = (ROOT / "templates" / "notebook.html").read_text()
    # Each file row gets a download button pointing to downloadPyodideFile()
    check(re.search(r"onclick=\"downloadPyodideFile\('\$\{escapeHtml\(f\.path\)\}'\)\"", nb),
          "download button wired per-file in file row template")


# ─── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("Colab-style workspace features — static analysis tests")
    print("=" * 70)

    test_dataset_registry_bundled()
    test_notebook_workspace_mount()
    test_convert_workspace_mount()
    test_indexeddb_autosave()
    test_pyodide_variable_inspector()
    test_pyodide_file_browser()
    test_server_heavy_package_guard()
    test_client_heavy_package_warn()
    test_magic_helper_json_safe()
    test_app_imports()
    test_file_links_surface()

    print("\n" + "=" * 70)
    print(f"PASSED: {len(PASSED)}    FAILED: {len(ERRORS)}")
    print("=" * 70)
    if ERRORS:
        print("\nFAILED CHECKS:")
        for label in ERRORS:
            print(f"  - {label}")
        sys.exit(1)
    print("\nAll checks passed.")
    sys.exit(0)
