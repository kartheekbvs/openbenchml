"""
OpenBenchML — Learn Benchmark Engine (Line-by-Line Code Walkthrough)
=====================================================================

A fourth learning mode that takes the user's REAL benchmark code
(the FastAPI router they pasted) and explains it LINE BY LINE —
like a tutor sitting next to them.

Routes:
    GET /learn/benchmark             -> overview (all 14 stages)
    GET /learn/benchmark/{slug}      -> single stage with code + explanation

14 STAGES:
    Stage  1: The imports — what each library does
    Stage  2: Router + templates setup
    Stage  3: Configuration constants
    Stage  4: GET /predict — serving the HTML form
    Stage  5: POST /bench — the form handler signature
    Stage  6: Load data + quality check
    Stage  7: Remove duplicates + X/y split
    Stage  8: Identify column types (numerical vs categorical)
    Stage  9: Train/test split
    Stage 10: Preprocessing pipelines (numerical + categorical)
    Stage 11: ColumnTransformer + full Pipeline
    Stage 12: Training + prediction benchmarks (timing)
    Stage 13: Metrics + cross-validation
    Stage 14: Inference benchmark (loading the uploaded model)
    Stage 15: The HTML form — line-by-line
    Stage 16: The CSS — line-by-line

Each stage has:
    - code: the actual lines from the user's code (verbatim)
    - line_by_line: a list of (line, explanation) tuples
    - intuition: why this step matters
    - common_mistakes: what beginners get wrong here
"""

from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional

from app.config import APP_NAME, APP_VERSION, templates
from app.routes.auth import get_current_user_from_cookie
from app.database.db import SessionLocal

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  BENCHMARK ENGINE COURSE — 16 stages
# ═══════════════════════════════════════════════════════════════════════════

BENCHMARK_COURSE = [
    # ─── Stage 1 ─────────────────────────────────────────────────────────
    {
        "stage": 1,
        "slug": "bench-stage-01-imports",
        "title": "The imports — what each library does",
        "summary": "16 import lines. Each one does a specific job. Let's go through them one by one.",
        "code": "from fastapi import APIRouter, File, UploadFile, Form, Request\nfrom fastapi.templating import Jinja2Templates\nfrom fastapi.responses import JSONResponse\nimport joblib\nimport pickle\nimport pandas as pd\nimport numpy as np\nimport time\nfrom sklearn.model_selection import train_test_split, cross_validate, KFold\nfrom sklearn.compose import ColumnTransformer\nfrom sklearn.pipeline import Pipeline\nfrom sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder\nfrom sklearn.impute import SimpleImputer\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score",
        "line_by_line": [
            ("from fastapi import APIRouter, File, UploadFile, Form, Request",
             "APIRouter — groups routes together (so you can do router.get('/path') instead of app.get('/path')). "
             "File + UploadFile — for file uploads (the .pkl model file). "
             "Form — for form-encoded fields (dataset, framework). "
             "Request — gives access to the incoming HTTP request (headers, cookies, etc.)."),
            ("from fastapi.templating import Jinja2Templates",
             "Jinja2Templates — renders HTML templates server-side. "
             "You point it at a directory (templates/) and call templates.TemplateResponse(...) to render a .html file."),
            ("from fastapi.responses import JSONResponse",
             "JSONResponse — returns a JSON body with a specific status code. "
             "Used here for the benchmark result (success) and error response (400)."),
            ("import joblib",
             "joblib — the standard way to save/load scikit-learn models. "
             "Faster than pickle for numpy arrays. Used for saving trained models to .pkl files."),
            ("import pickle",
             "pickle — Python's built-in serializer. Used here to LOAD the user-uploaded .pkl model. "
             "joblib.dump → joblib.load is preferred, but pickle.loads works too (joblib files are pickle-compatible)."),
            ("import pandas as pd",
             "pandas — data manipulation. The 'Excel of Python'. "
             "Used here to load the CSV (pd.read_csv), drop duplicates, split into X and y."),
            ("import numpy as np",
             "numpy — numerical computing. The 'math engine of Python'. "
             "Used here for np.sqrt (square root for RMSE) and array operations."),
            ("import time",
             "time — for timing. time.perf_counter() is a high-resolution timer. "
             "Used to measure training_time and prediction_time in seconds."),
            ("from sklearn.model_selection import train_test_split, cross_validate, KFold",
             "train_test_split — splits data into train + test sets (80/20 here). "
             "cross_validate — runs k-fold cross-validation (5 folds here). "
             "KFold — defines HOW to split (5 folds, shuffled, fixed random_state)."),
            ("from sklearn.compose import ColumnTransformer",
             "ColumnTransformer — applies different preprocessing to different columns. "
             "E.g. scale the numerical columns, one-hot encode the categorical columns — in one step."),
            ("from sklearn.pipeline import Pipeline",
             "Pipeline — chains preprocessing + model into ONE object. "
             "Why? So you can call fit() once and it does: preprocess → train. "
             "And predict() does: preprocess → predict. No data leakage between train and test."),
            ("from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder",
             "StandardScaler — subtracts mean, divides by std. Makes numerical features centered around 0. "
             "OneHotEncoder — turns 'red'/'green'/'blue' into 3 binary columns. "
             "LabelEncoder — turns 'red'/'green'/'blue' into 0/1/2 (used in the inference section)."),
            ("from sklearn.impute import SimpleImputer",
             "SimpleImputer — fills missing values. "
             "strategy='median' → fill NaN with the median. "
             "strategy='most_frequent' → fill NaN with the most common value (for categoricals)."),
            ("from sklearn.linear_model import LinearRegression",
             "LinearRegression — the actual ML model. "
             "Fits a line (or hyperplane) through the data: y = a*x + b. "
             "Simple but powerful baseline."),
            ("from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score",
             "mean_absolute_error — avg of |actual - predicted|. Easy to interpret. "
             "mean_squared_error — avg of (actual - predicted)². Punishes big errors. "
             "r2_score — 0 to 1. How much better than just guessing the mean."),
        ],
        "intuition": (
            "Every import does ONE job. None is redundant. "
            "If you remove any one, the code breaks. "
            "This is a sign of well-structured code — each line earns its place."
        ),
        "common_mistakes": [
            "Importing everything with `from sklearn import *` — pollutes the namespace, makes bugs hard to trace.",
            "Using `import *` from fastapi — same problem. Always import specific names.",
            "Forgetting `import time` and using `time.time()` instead of `time.perf_counter()` — perf_counter is more precise.",
        ],
    },

    # ─── Stage 2 ─────────────────────────────────────────────────────────
    {
        "stage": 2,
        "slug": "bench-stage-02-router-setup",
        "title": "Router + templates setup",
        "summary": "Create the router object + point Jinja2 at the templates folder. Two lines, two jobs.",
        "code": "router = APIRouter()\ntemplates = Jinja2Templates(directory=\"templates\")",
        "line_by_line": [
            ("router = APIRouter()",
             "Creates a router object. Instead of @app.get('/predict') (which clutters main.py), "
             "you do @router.get('/predict') in this file, then main.py includes the router. "
             "This is how FastAPI apps stay organized — one router per feature area."),
            ("templates = Jinja2Templates(directory=\"templates\")",
             "Points Jinja2 at the templates/ folder. Now you can call "
             "templates.TemplateResponse(request, name='benchmark.html') to render HTML. "
             "The directory path is RELATIVE to where you run uvicorn — usually the project root."),
        ],
        "intuition": (
            "These two lines set up the INFRASTRUCTURE. "
            "router handles routing (URLs → functions). "
            "templates handles rendering (HTML files → HTTP responses). "
            "Every FastAPI route file starts with these two objects."
        ),
        "common_mistakes": [
            "Putting templates in the wrong folder — Jinja2Templates won't find them.",
            "Creating the router but forgetting to include it in main.py — routes return 404.",
        ],
    },

    # ─── Stage 3 ─────────────────────────────────────────────────────────
    {
        "stage": 3,
        "slug": "bench-stage-03-config",
        "title": "Configuration constants",
        "summary": "Hardcoded values at the top of the file. Easy to find, easy to change.",
        "code": "# Configuration\nDATA_PATH = \"housing.csv\"\nTARGET = \"price\"\nTEST_SIZE = 0.20\nRANDOM_STATE = 42\nCV_FOLDS = 5",
        "line_by_line": [
            ("DATA_PATH = \"housing.csv\"",
             "Path to the dataset CSV. Hardcoded here — in a real app, this would come from a config file or env var."),
            ("TARGET = \"price\"",
             "The column we're trying to predict. For house data, it's 'price'. "
             "Change this to 'quality' for wine data, 'species' for iris, etc."),
            ("TEST_SIZE = 0.20",
             "20% of the data goes to the test set, 80% to training. "
             "Common splits: 80/20, 70/30, 60/20/20 (train/val/test)."),
            ("RANDOM_STATE = 42",
             "The seed for the random number generator. "
             "Same seed = same split every time. Essential for reproducibility — "
             "without it, every run gives different results and you can't compare models."),
            ("CV_FOLDS = 5",
             "5-fold cross-validation. The data is split into 5 pieces; "
             "the model trains on 4, tests on 1, repeats 5 times. "
             "More folds = more accurate but slower. 5 or 10 is standard."),
        ],
        "intuition": (
            "Constants at the top of the file = single source of truth. "
            "If you want to change the test split from 20% to 30%, you change ONE line. "
            "If you hardcoded 0.20 in 5 places, you'd have to find and change all 5 — bug-prone."
        ),
        "common_mistakes": [
            "Using different random_state values in different places — results aren't comparable.",
            "Hardcoding paths like 'C:/Users/name/data/housing.csv' — breaks on other machines. Use relative paths.",
            "Not using constants at all — magic numbers scattered through the code are hard to maintain.",
        ],
    },

    # ─── Stage 4 ─────────────────────────────────────────────────────────
    {
        "stage": 4,
        "slug": "bench-stage-04-get-predict",
        "title": "GET /predict — serving the HTML form",
        "summary": "When the user visits /predict, serve the benchmark.html page with the form on it.",
        "code": "@router.get(\"\")\n@router.get(\"/\")\ndef predict(request: Request):\n    return templates.TemplateResponse(request=request, name=\"benchmark.html\")",
        "line_by_line": [
            ("@router.get(\"\")",
             "Registers the function below as the handler for GET requests to the router's BASE path. "
             "If the router is mounted at /predict, this handles GET /predict."),
            ("@router.get(\"/\")",
             "Same as above but with a trailing slash. Handles GET /predict/. "
             "Stacking both decorators means BOTH URLs work — good UX (no 404 if user adds a slash)."),
            ("def predict(request: Request):",
             "The function name 'predict' is just for humans — FastAPI doesn't use it. "
             "request: Request — FastAPI sees the type hint and injects the Request object. "
             "You need it to render templates."),
            ("return templates.TemplateResponse(request=request, name=\"benchmark.html\")",
             "Renders templates/benchmark.html and returns it as an HTTP response. "
             "request=request is REQUIRED since FastAPI 0.85 — without it, you get an error. "
             "name= is the template filename (relative to the directory= you set in Jinja2Templates)."),
        ],
        "intuition": (
            "This is the simplest possible route — no logic, no DB, just 'show this HTML page'. "
            "Every web app has dozens of these. They're the 'pages' of your site. "
            "The form on benchmark.html will POST to /predict/bench (the next stage)."
        ),
        "common_mistakes": [
            "Forgetting request=request — Jinja2Templates requires it since FastAPI 0.85.",
            "Using @router.get('/predict') when the router is ALREADY mounted at /predict — you'd get /predict/predict.",
            "Forgetting to include the router in main.py — the route won't exist.",
        ],
    },

    # ─── Stage 5 ─────────────────────────────────────────────────────────
    {
        "stage": 5,
        "slug": "bench-stage-05-post-bench-signature",
        "title": "POST /bench — the form handler signature",
        "summary": "The form on benchmark.html submits to this. Form-encoded fields + a file upload.",
        "code": "@router.post(\"/bench\")\nasync def bench_score(\n    dataset: str = Form(),\n    model_file: UploadFile = File(),\n    framework: str = Form(),\n    request: Request = None\n):",
        "line_by_line": [
            ("@router.post(\"/bench\")",
             "Registers the function as the handler for POST requests to /predict/bench "
             "(because the router is mounted at /predict). "
             "POST is for submissions — the form sends data TO the server."),
            ("async def bench_score(...):",
             "async def — the function can await I/O (reading the uploaded file). "
             "If you have no awaits, regular def works too (FastAPI runs it in a threadpool)."),
            ("dataset: str = Form(),",
             "Tells FastAPI: 'read this from the form-encoded body, field name \"dataset\"'. "
             "The HTML form has <select name=\"dataset\">. The name MUST match. "
             "str — FastAPI validates it's a string. If it's not, returns 422."),
            ("model_file: UploadFile = File(),",
             "Tells FastAPI: 'read this from the multipart file upload, field name \"model_file\"'. "
             "The HTML form has <input type=\"file\" name=\"model_file\">. "
             "UploadFile streams the file — doesn't load it all into RAM at once."),
            ("framework: str = Form(),",
             "Same as dataset — reads the 'framework' field from the form body. "
             "Values: 'tensorflow' or 'pytorch' (from the <select> in the HTML)."),
            ("request: Request = None",
             "Optional Request object. Not used in this function, but useful for logging "
             "or accessing cookies. = None means it's optional — FastAPI won't complain if missing."),
        ],
        "intuition": (
            "Form() and File() are how FastAPI knows WHERE to read each parameter from. "
            "Without Form(), FastAPI would look for a JSON body. "
            "Without File(), FastAPI wouldn't read the uploaded file. "
            "The type hints (str, UploadFile) ALSO validate — wrong type = 422 error."
        ),
        "common_mistakes": [
            "Using dataset: str without Form() — FastAPI tries to read from JSON body, form submission fails.",
            "Mismatched field names — HTML name=\"dataset\" but Python dataset_name: Form() → 422 error.",
            "Forgetting enctype=\"multipart/form-data\" on the HTML <form> — file uploads won't work.",
        ],
    },

    # ─── Stage 6 ─────────────────────────────────────────────────────────
    {
        "stage": 6,
        "slug": "bench-stage-06-load-data",
        "title": "Step 1-2: Load data + quality check",
        "summary": "Read the CSV, check shape, count missing values + duplicates. The 4 questions you ask of ANY dataset.",
        "code": "df = pd.read_csv(\"housing.csv\")\n\nprint(\"=\" * 60)\nprint(\"DATASET INFORMATION\")\nprint(\"=\" * 60)\nprint(f\"Shape: {df.shape}\")\n\nprint(\"\\n\" + \"=\" * 60)\nprint(\"DATA QUALITY CHECK\")\nprint(\"=\" * 60)\n\nmissing_values = df.isnull().sum().to_dict()\nduplicates = df.duplicated().sum()",
        "line_by_line": [
            ("df = pd.read_csv(\"housing.csv\")",
             "Loads the CSV into a pandas DataFrame. "
             "df is now a table — rows × columns. You can do df.head(), df.shape, df.info(), etc."),
            ("print(\"=\" * 60)",
             "Prints a line of 60 = signs. Just for visual separation in the server logs. "
             "* on a string repeats it — 'ab' * 3 = 'ababab'."),
            ("print(f\"Shape: {df.shape}\")",
             "f-string — evaluates {df.shape} and inserts it into the string. "
             "df.shape is a tuple like (1000, 8) — 1000 rows, 8 columns."),
            ("missing_values = df.isnull().sum().to_dict()",
             "df.isnull() — returns a DataFrame of True/False (True where value is NaN). "
             ".sum() — counts True values per column (because True=1, False=0). "
             ".to_dict() — converts the result to a Python dict like {'price': 0, 'area': 5}."),
            ("duplicates = df.duplicated().sum()",
             "df.duplicated() — returns a boolean Series (True for rows that are duplicates of earlier rows). "
             ".sum() — counts the True values = number of duplicate rows."),
        ],
        "intuition": (
            "This is the 'meet the dataset' step. Before any ML, you answer 4 questions: "
            "(1) How big is it? (shape) "
            "(2) Are there missing values? (isnull) "
            "(3) Are there duplicates? (duplicated) "
            "(4) What do the values look like? (head/describe — not shown here). "
            "Skipping this step = surprises later (NaN crashes, duplicates inflate accuracy)."
        ),
        "common_mistakes": [
            "Not checking for nulls — model.fit() crashes with 'Input contains NaN'.",
            "Not checking for duplicates — same row in train AND test = artificially high accuracy.",
            "Using df.isnull().count() instead of .sum() — count() counts ALL rows, not just nulls.",
        ],
    },

    # ─── Stage 7 ─────────────────────────────────────────────────────────
    {
        "stage": 7,
        "slug": "bench-stage-07-dedup-split-xy",
        "title": "Step 3-4: Remove duplicates + X/y split",
        "summary": "Drop duplicate rows, then separate features (X) from target (y).",
        "code": "before = len(df)\ndf = df.drop_duplicates().reset_index(drop=True)\nafter = len(df)\n\nX = df.drop(columns=[TARGET])\ny = df[TARGET]",
        "line_by_line": [
            ("before = len(df)",
             "Saves the row count BEFORE dropping duplicates. "
             "len(df) returns the number of rows (same as df.shape[0])."),
            ("df = df.drop_duplicates().reset_index(drop=True)",
             "drop_duplicates() — removes rows where ALL columns match an earlier row. "
             "Returns a new DataFrame (doesn't modify in place). "
             "reset_index(drop=True) — after dropping rows, the index has gaps (0,1,3,5...). "
             "This resets it to 0,1,2,3... so you can use .loc[5] safely."),
            ("after = len(df)",
             "Saves the row count AFTER dropping duplicates. "
             "before - after = number of duplicates removed (used in the result dict)."),
            ("X = df.drop(columns=[TARGET])",
             "X = all columns EXCEPT 'price'. These are the FEATURES (inputs). "
             "drop(columns=['price']) returns a new DataFrame without that column. "
             "Why uppercase X? Convention — features are a 2D matrix (rows × cols)."),
            ("y = df[TARGET]",
             "y = just the 'price' column. This is the TARGET (what we predict). "
             "Why lowercase y? Convention — target is a 1D vector (one value per row)."),
        ],
        "intuition": (
            "X/y split is the most important step in ML. "
            "X is what the model SEES during training. y is what it tries to PREDICT. "
            "If you accidentally leave 'price' in X, the model just copies it — 100% accuracy, useless. "
            "This is called 'data leakage' and it's the #1 ML bug."
        ),
        "common_mistakes": [
            "Forgetting reset_index — later .loc[i] gives wrong rows.",
            "Leaving the target column in X — model gets 100% accuracy on train, fails on real data.",
            "Using df.drop('price') without columns= — works but deprecated. Always use columns=.",
        ],
    },

    # ─── Stage 8 ─────────────────────────────────────────────────────────
    {
        "stage": 8,
        "slug": "bench-stage-08-column-types",
        "title": "Step 5: Identify column types",
        "summary": "ML models only accept numbers. Categorical columns need encoding. Identify which is which.",
        "code": "numerical_features = X.select_dtypes(include=[\"int64\", \"float64\"]).columns.tolist()\ncategorical_features = X.select_dtypes(include=[\"object\", \"category\", \"bool\"]).columns.tolist()",
        "line_by_line": [
            ("numerical_features = X.select_dtypes(include=[\"int64\", \"float64\"]).columns.tolist()",
             "X.select_dtypes(include=['int64', 'float64']) — returns a DataFrame with only the integer + float columns. "
             ".columns — gets the column names (as an Index object). "
             ".tolist() — converts to a plain Python list like ['area', 'bedrooms', 'bathrooms']."),
            ("categorical_features = X.select_dtypes(include=[\"object\", \"category\", \"bool\"]).columns.tolist()",
             "Same idea but for text columns. "
             "'object' = strings (like 'furnished' / 'unfurnished'). "
             "'category' = pandas categorical type. "
             "'bool' = True/False columns."),
        ],
        "intuition": (
            "Why split them? Because they need DIFFERENT preprocessing: "
            "Numerical: fill NaN with median, then scale (StandardScaler). "
            "Categorical: fill NaN with most-frequent, then one-hot encode (OneHotEncoder). "
            "sklearn's ColumnTransformer (next stages) lets you apply different transformers to different columns."
        ),
        "common_mistakes": [
            "Forgetting 'category' dtype — pandas Categorical columns get missed.",
            "Using include=['number'] — catches int + float but also bool, which you might not want.",
            "Not checking the result — if numerical_features is empty, something's wrong with the CSV.",
        ],
    },

    # ─── Stage 9 ─────────────────────────────────────────────────────────
    {
        "stage": 9,
        "slug": "bench-stage-09-train-test-split",
        "title": "Step 6: Train/test split",
        "summary": "Carve out 20% of the data the model never sees during training. Score on that 20%.",
        "code": "X_train, X_test, y_train, y_test = train_test_split(\n    X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE\n)",
        "line_by_line": [
            ("X_train, X_test, y_train, y_test = train_test_split(...)",
             "Unpacks the 4 return values. X_train + y_train = 80% of the data (for training). "
             "X_test + y_test = 20% (for testing). The split is RANDOM but reproducible because of random_state."),
            ("X, y,",
             "The features (X) and target (y) to split. "
             "train_test_split keeps the row alignment — X_train[i] corresponds to y_train[i]."),
            ("test_size=TEST_SIZE,",
             "TEST_SIZE = 0.20 (from the config). 20% of the data goes to the test set. "
             "Could also be an int (e.g. test_size=100 for exactly 100 test rows)."),
            ("random_state=RANDOM_STATE,",
             "RANDOM_STATE = 42 (from the config). The random seed. "
             "Same seed = same split every run. ESSENTIAL for reproducibility — "
             "without it, you can't compare two models fairly (different test sets)."),
        ],
        "intuition": (
            "Why split? Because training on ALL the data + testing on the SAME data = cheating. "
            "The model just memorizes. Test set = 'data the model has never seen' = honest evaluation. "
            "If train accuracy is 99% but test accuracy is 60%, you've OVERFIT — the model memorized, didn't learn."
        ),
        "common_mistakes": [
            "Forgetting random_state — every run gives a different split, can't compare models.",
            "Splitting BEFORE preprocessing — fit the scaler on train, transform test with the SAME scaler.",
            "Using test_size=0.5 — too much test data, not enough training data. 0.2-0.3 is standard.",
        ],
    },

    # ─── Stage 10 ────────────────────────────────────────────────────────
    {
        "stage": 10,
        "slug": "bench-stage-10-preprocessing-pipelines",
        "title": "Step 7-8: Numerical + categorical preprocessing pipelines",
        "summary": "Two pipelines — one for numbers (impute + scale), one for categories (impute + encode).",
        "code": "numerical_pipeline = Pipeline(steps=[\n    (\"imputer\", SimpleImputer(strategy=\"median\")),\n    (\"scaler\", StandardScaler())\n])\n\ncategorical_pipeline = Pipeline(steps=[\n    (\"imputer\", SimpleImputer(strategy=\"most_frequent\")),\n    (\"encoder\", OneHotEncoder(handle_unknown=\"ignore\", drop=\"first\"))\n])",
        "line_by_line": [
            ("numerical_pipeline = Pipeline(steps=[...])",
             "Creates a pipeline for numerical columns. "
             "Pipeline runs the steps IN ORDER: first imputer, then scaler. "
             "Each step is a (name, transformer) tuple. The name is just for you — sklearn uses it in error messages."),
            ("(\"imputer\", SimpleImputer(strategy=\"median\"))",
             "Fills missing values with the MEDIAN of the column. "
             "Why median not mean? Median is robust to outliers. "
             "If one house costs ₹100 crore, the mean is skewed but the median isn't."),
            ("(\"scaler\", StandardScaler())",
             "Subtracts the mean, divides by std. Result: mean=0, std=1. "
             "Why? Linear regression converges faster when features are on the same scale. "
             "A feature 'area' (0-10000 sqft) and 'bedrooms' (1-5) need scaling or 'area' dominates."),
            ("categorical_pipeline = Pipeline(steps=[...])",
             "Same idea but for text columns. Two steps: imputer + encoder."),
            ("(\"imputer\", SimpleImputer(strategy=\"most_frequent\"))",
             "Fills missing categorical values with the most common value. "
             "Can't use median on text — median is a numerical concept."),
            ("(\"encoder\", OneHotEncoder(handle_unknown=\"ignore\", drop=\"first\"))",
             "Turns 'furnished'/'semi-furnished'/'unfurnished' into 2 binary columns. "
             "handle_unknown='ignore' — if test data has a new category, don't crash (skip it). "
             "drop='first' — drop the first category to avoid multicollinearity (the 'dummy variable trap')."),
        ],
        "intuition": (
            "Pipelines are CRITICAL for ML. Without them: "
            "(1) You fit the scaler on train, forget to transform test the same way → garbage predictions. "
            "(2) You add a new model and have to redo all preprocessing manually. "
            "With a Pipeline: fit() does everything, predict() does everything, no manual steps."
        ),
        "common_mistakes": [
            "Fitting the scaler on the FULL dataset (train + test) — data leakage! Test data leaks into the scaler.",
            "Forgetting handle_unknown='ignore' — model crashes on new categories at prediction time.",
            "Not dropping the first category in OneHotEncoder — multicollinearity breaks linear models.",
        ],
    },

    # ─── Stage 11 ────────────────────────────────────────────────────────
    {
        "stage": 11,
        "slug": "bench-stage-11-columntransformer-pipeline",
        "title": "Step 9-10: ColumnTransformer + full Pipeline",
        "summary": "Combine numerical + categorical preprocessing. Then chain preprocessing + model into one Pipeline.",
        "code": "preprocessor = ColumnTransformer(transformers=[\n    (\"numerical\", numerical_pipeline, numerical_features),\n    (\"categorical\", categorical_pipeline, categorical_features)\n])\n\nmodel = Pipeline(steps=[\n    (\"preprocessing\", preprocessor),\n    (\"model\", LinearRegression())\n])",
        "line_by_line": [
            ("preprocessor = ColumnTransformer(transformers=[...])",
             "ColumnTransformer applies different transformers to different columns. "
             "Each transformer is a (name, transformer, columns) tuple: "
             "  ('numerical', numerical_pipeline, numerical_features) → "
             "  apply numerical_pipeline to the columns in numerical_features."),
            ("(\"numerical\", numerical_pipeline, numerical_features),",
             "Apply the numerical pipeline (impute + scale) to columns like 'area', 'bedrooms', 'bathrooms'."),
            ("(\"categorical\", categorical_pipeline, categorical_features),",
             "Apply the categorical pipeline (impute + encode) to columns like 'furnishingstatus', 'location'."),
            ("model = Pipeline(steps=[\n    (\"preprocessing\", preprocessor),\n    (\"model\", LinearRegression())\n])",
             "The FULL pipeline: preprocessing → model. "
             "Now model.fit(X_train, y_train) does: impute → scale → encode → fit LinearRegression. "
             "And model.predict(X_test) does the same preprocessing, then predicts. "
             "ONE object, ONE fit, ONE predict — no manual steps."),
        ],
        "intuition": (
            "This is the 'single source of truth' pattern in sklearn. "
            "The whole ML workflow — preprocessing + model — is ONE object. "
            "You can save it with joblib.dump(model, 'model.pkl') and load it elsewhere — "
            "the preprocessing is BAKED IN. No need to remember which scaler you used."
        ),
        "common_mistakes": [
            "Calling preprocessor.fit_transform(X_test) separately — bypasses the pipeline, causes mismatch.",
            "Forgetting to include preprocessor in the final Pipeline — model.fit crashes on text columns.",
            "Naming two steps the same thing — sklearn throws 'Steps are not uniquely named'.",
        ],
    },

    # ─── Stage 12 ────────────────────────────────────────────────────────
    {
        "stage": 12,
        "slug": "bench-stage-12-training-prediction-timing",
        "title": "Step 11-12: Training + prediction benchmarks (timing)",
        "summary": "Use time.perf_counter() to measure how long fit() and predict() take. The 'benchmark' part.",
        "code": "train_start = time.perf_counter()\nmodel.fit(X_train, y_train)\ntrain_end = time.perf_counter()\ntraining_time = train_end - train_start\n\nprediction_start = time.perf_counter()\ny_pred = model.predict(X_test)\nprediction_end = time.perf_counter()\nprediction_time = prediction_end - prediction_start",
        "line_by_line": [
            ("train_start = time.perf_counter()",
             "Records the current time (in seconds, high precision). "
             "perf_counter is better than time.time() for measuring durations — "
             "it's monotonic (never goes backwards) and has higher resolution."),
            ("model.fit(X_train, y_train)",
             "THE TRAINING STEP. This is where the 'learning' happens. "
             "For LinearRegression: finds the best-fit line through the data (least squares). "
             "For RandomForest: builds 100 decision trees. "
             "After this, model has coefficients / trees stored internally."),
            ("train_end = time.perf_counter()",
             "Records the time AFTER training. train_end - train_start = training duration in seconds."),
            ("training_time = train_end - train_start",
             "The training time. Usually small for LinearRegression (milliseconds), "
             "large for deep learning (hours). This is what 'benchmarking' measures."),
            ("prediction_start = time.perf_counter()",
             "Records time before prediction."),
            ("y_pred = model.predict(X_test)",
             "THE PREDICTION STEP. Uses the trained model to predict prices for X_test. "
             "y_pred is a numpy array of predicted prices — same length as y_test."),
            ("prediction_end = time.perf_counter()",
             "Records time after prediction."),
            ("prediction_time = prediction_end - prediction_start",
             "How long predict() took. Usually much faster than fit(). "
             "For production: this is the latency users feel (prediction_time / len(X_test) = per-sample latency)."),
        ],
        "intuition": (
            "Benchmarking = measuring TIME. "
            "training_time — how long does it take to train? (matters for iteration speed) "
            "prediction_time — how long does it take to predict? (matters for user experience) "
            "prediction_time / len(X_test) — per-sample latency (matters for real-time APIs). "
            "A model that's 1% more accurate but 10x slower might not be worth it."
        ),
        "common_mistakes": [
            "Using time.time() instead of time.perf_counter() — less precise, can go backwards.",
            "Timing the FIRST predict() call — includes lazy initialization overhead, skews results.",
            "Forgetting to use the SAME X_test for all models — can't compare timings fairly.",
        ],
    },

    # ─── Stage 13 ────────────────────────────────────────────────────────
    {
        "stage": 13,
        "slug": "bench-stage-13-metrics-crossvalidation",
        "title": "Step 13-14: Metrics + cross-validation",
        "summary": "Compute MAE/MSE/RMSE/R² on the test set. Then 5-fold CV for a more honest estimate.",
        "code": "mae = mean_absolute_error(y_test, y_pred)\nmse = mean_squared_error(y_test, y_pred)\nrmse = np.sqrt(mse)\nr2 = r2_score(y_test, y_pred)\n\ncv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)\nscoring = {\"MAE\": \"neg_mean_absolute_error\", \"MSE\": \"neg_mean_squared_error\", \"R2\": \"r2\"}\ncv_results = cross_validate(model, X, y, cv=cv, scoring=scoring, return_train_score=False)\n\ncv_mae = -cv_results[\"test_MAE\"].mean()\ncv_mse = -cv_results[\"test_MSE\"].mean()\ncv_rmse = np.sqrt(cv_mse)\ncv_r2 = cv_results[\"test_R2\"].mean()",
        "line_by_line": [
            ("mae = mean_absolute_error(y_test, y_pred)",
             "MAE = average of |actual - predicted|. "
             "If MAE = 500000, it means 'on average, predictions are off by ₹5 lakh'. "
             "Most interpretable metric — easy to explain to non-technical people."),
            ("mse = mean_squared_error(y_test, y_pred)",
             "MSE = average of (actual - predicted)². "
             "Squared so big errors are punished more. "
             "Hard to interpret (units are price²) — that's why we use RMSE instead."),
            ("rmse = np.sqrt(mse)",
             "RMSE = square root of MSE. Back in the original units (₹). "
             "Like MAE but punishes big errors more. "
             "If RMSE >> MAE, you have a few very bad predictions."),
            ("r2 = r2_score(y_test, y_pred)",
             "R² = 0 to 1. How much better than just guessing the mean. "
             "R²=1 → perfect predictions. R²=0 → no better than mean. R²<0 → WORSE than mean. "
             "Scale-free — you can compare R² across different datasets."),
            ("cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)",
             "Defines 5-fold CV: split data into 5 pieces, train on 4, test on 1, repeat 5 times. "
             "shuffle=True — randomize row order before splitting (important if data is sorted). "
             "random_state=42 — reproducible."),
            ("scoring = {\"MAE\": \"neg_mean_absolute_error\", ...}",
             "Tells cross_validate which metrics to compute. "
             "Why 'neg_'? sklearn's cross_validate MAXIMIZES scores. "
             "For errors (lower=better), it negates them so 'maximizing' = 'minimizing the error'."),
            ("cv_results = cross_validate(model, X, y, cv=cv, scoring=scoring, return_train_score=False)",
             "Runs 5-fold CV. Returns a dict with test_MAE, test_MSE, test_R2 arrays (5 values each). "
             "Uses the FULL X, y (not X_train, y_train) — CV does its own splitting."),
            ("cv_mae = -cv_results[\"test_MAE\"].mean()",
             "Negate (because sklearn negated it) and average across 5 folds. "
             "CV MAE is more honest than single-split MAE — it's the average of 5 different test sets."),
        ],
        "intuition": (
            "Single test set = lucky or unlucky split. "
            "5-fold CV = 5 different test sets, averaged. More honest. "
            "If single-split R² = 0.85 but CV R² = 0.70, your single split was lucky. "
            "Always report CV metrics — they're what reviewers / bosses trust."
        ),
        "common_mistakes": [
            "Reporting only single-split metrics — overestimates model quality.",
            "Forgetting the minus sign on neg_mean_absolute_error — reports negative MAE.",
            "Using CV on the FULL dataset AFTER train_test_split — leaks test data into CV.",
        ],
    },

    # ─── Stage 14 ────────────────────────────────────────────────────────
    {
        "stage": 14,
        "slug": "bench-stage-14-inference-benchmark",
        "title": "Step 16: Inference benchmark (loading the uploaded model)",
        "summary": "The user uploaded a .pkl file. Load it, run predict() on test data, measure latency + throughput.",
        "code": "if dataset == \"house\":\n    try:\n        model_content = await model_file.read()\n        loaded_model = pickle.loads(model_content)\n\n        df_test = pd.read_csv(DATA_PATH).drop_duplicates()\n\n        for column in df_test.columns:\n            if df_test[column].dtype == \"object\":\n                df_test[column] = df_test[column].fillna(df_test[column].mode()[0])\n            else:\n                df_test[column] = df_test[column].fillna(df_test[column].median())\n\n        categorical_cols = df_test.select_dtypes(include=[\"object\"]).columns\n        for column in categorical_cols:\n            encoder = LabelEncoder()\n            df_test[column] = encoder.fit_transform(df_test[column])\n\n        X_infer = df_test.drop(TARGET, axis=1)\n        y_infer = df_test[TARGET]\n\n        _, X_infer_test, _, y_infer_test = train_test_split(\n            X_infer, y_infer, test_size=0.20, random_state=42\n        )\n\n        inference_start = time.perf_counter()\n        y_infer_pred = loaded_model.predict(X_infer_test)\n        inference_end = time.perf_counter()\n\n        inference_time = inference_end - inference_start\n        latency_per_sample = inference_time / samples_infer\n        throughput = samples_infer / inference_time",
        "line_by_line": [
            ("if dataset == \"house\":",
             "Only run inference benchmark for the 'house' dataset. "
             "Other datasets (wine) skip this — the uploaded model might not be compatible."),
            ("model_content = await model_file.read()",
             "Reads the uploaded .pkl file into memory as bytes. "
             "await because UploadFile.read() is async — it streams the file. "
             "For huge files, read in chunks instead: while chunk := await model_file.read(1024): ..."),
            ("loaded_model = pickle.loads(model_content)",
             "Deserializes the bytes back into a Python object (the trained model). "
             "pickle.loads = load from string/bytes. pickle.load = load from file. "
             "WARNING: pickle is unsafe for untrusted files — it can execute arbitrary code."),
            ("df_test = pd.read_csv(DATA_PATH).drop_duplicates()",
             "Load the SAME dataset again for inference testing. "
             "drop_duplicates() — same cleanup as before."),
            ("for column in df_test.columns: ...",
             "Fill missing values PER COLUMN. "
             "object dtype → fill with mode (most frequent). "
             "numeric dtype → fill with median. "
             "NOTE: this is LESS robust than the Pipeline approach above — "
             "the Pipeline does this automatically."),
            ("categorical_cols = df_test.select_dtypes(include=[\"object\"]).columns",
             "Get all text columns. We need to convert them to numbers because "
             "the uploaded model probably expects numbers (not text)."),
            ("for column in categorical_cols:\n    encoder = LabelEncoder()\n    df_test[column] = encoder.fit_transform(df_test[column])",
             "LabelEncoder converts 'red'/'green'/'blue' → 0/1/2. "
             "WARNING: this is DIFFERENT from OneHotEncoder! "
             "LabelEncoder implies order (2 > 1 > 0) which may not be true. "
             "OneHotEncoder is usually better for categorical features."),
            ("X_infer = df_test.drop(TARGET, axis=1)\ny_infer = df_test[TARGET]",
             "Same X/y split as before. axis=1 means 'drop a column' (axis=0 would drop a row)."),
            ("_, X_infer_test, _, y_infer_test = train_test_split(...)",
             "Same 80/20 split. _ is a Python convention for 'I don't need this value'. "
             "We only need X_infer_test and y_infer_test for inference."),
            ("inference_start = time.perf_counter()\ny_infer_pred = loaded_model.predict(X_infer_test)\ninference_end = time.perf_counter()",
             "Time the prediction. This is the INFERENCE benchmark — "
             "how fast can the uploaded model make predictions? "
             "Different from training time — usually much faster."),
            ("latency_per_sample = inference_time / samples_infer",
             "Per-sample latency in seconds. If this is 0.001s, the model can handle 1000 req/sec. "
             "Critical for real-time APIs — users won't wait more than ~200ms."),
            ("throughput = samples_infer / inference_time",
             "Samples per second. Inverse of latency. "
             "If throughput = 5000, the model processes 5000 predictions/sec."),
        ],
        "intuition": (
            "This step answers: 'How fast is the USER'S model?' "
            "Different from the training benchmark (which used LinearRegression). "
            "The user uploaded a .pkl — could be any model (XGBoost, RandomForest, neural net). "
            "We load it, run predict(), measure speed. This is the 'production readiness' check."
        ),
        "common_mistakes": [
            "Using pickle.loads on untrusted files — security risk! Use a sandbox.",
            "Preprocessing the test data DIFFERENTLY than the model was trained on — garbage predictions.",
            "Using LabelEncoder instead of OneHotEncoder — model expects different feature shape.",
        ],
    },

    # ─── Stage 15 ────────────────────────────────────────────────────────
    {
        "stage": 15,
        "slug": "bench-stage-15-html-form",
        "title": "The HTML form — line-by-line",
        "summary": "The form the user sees. Select dataset, upload .pkl, select framework, submit.",
        "code": "<form class=\"b1\" method=\"post\" action=\"http://127.0.0.1:8000/predict/bench\" enctype=\"multipart/form-data\">\n    <label>Select DataSet:</label>\n    <select name=\"dataset\" id=\"dataset\">\n        <option value=\"house\">House</option>\n        <option value=\"wine\">Wine</option>\n    </select><br>\n    <label>Upload Model:</label>\n    <input type=\"file\" name=\"model_file\" id=\"model\"><br>\n    <label>Select FrameWork:</label>\n    <select name=\"framework\" id=\"framework\">\n        <option value=\"tensorflow\">TensorFlow</option>\n        <option value=\"pytorch\">Sklearn</option>\n    </select><br>\n    <button type=\"submit\">Run BenchMark</button>\n</form>",
        "line_by_line": [
            ("<form ... method=\"post\" ...>",
             "method='post' — sends data IN the request body (not in the URL like GET). "
             "Required for file uploads + sensitive data."),
            ("action=\"http://127.0.0.1:8000/predict/bench\"",
             "Where the form submits to. The /predict/bench endpoint we just walked through. "
             "NOTE: hardcoding 127.0.0.1:8000 breaks in production — use relative URL: action=\"/predict/bench\"."),
            ("enctype=\"multipart/form-data\"",
             "CRITICAL for file uploads. Without it, the file isn't sent. "
             "Three enctype values: application/x-www-form-urlencoded (default), multipart/form-data (files), text/plain (rare)."),
            ("<select name=\"dataset\" id=\"dataset\">",
             "name='dataset' — MUST match the Python parameter name (dataset: str = Form()). "
             "If they don't match, FastAPI returns 422."),
            ("<option value=\"house\">House</option>",
             "value='house' — what gets sent to the server. 'House' is just what the user sees. "
             "So the server receives dataset='house' (lowercase), not 'House'."),
            ("<input type=\"file\" name=\"model_file\" id=\"model\">",
             "type='file' — shows a file picker. name='model_file' — MUST match the Python parameter (model_file: UploadFile = File())."),
            ("<button type=\"submit\">Run BenchMark</button>",
             "type='submit' — clicking it submits the form. "
             "type='button' — just a clickable button, doesn't submit (needs JavaScript)."),
        ],
        "intuition": (
            "The form is the USER INTERFACE to your benchmark engine. "
            "Every field name MUST match the FastAPI parameter name exactly. "
            "enctype='multipart/form-data' is the #1 forgotten thing — without it, file uploads silently fail."
        ),
        "common_mistakes": [
            "Forgetting enctype='multipart/form-data' — file upload silently fails.",
            "Mismatched name attributes — FastAPI returns 422 'field required'.",
            "Hardcoding the action URL (http://127.0.0.1:8000/...) — breaks in production.",
        ],
    },

    # ─── Stage 16 ────────────────────────────────────────────────────────
    {
        "stage": 16,
        "slug": "bench-stage-16-css-styling",
        "title": "The CSS — line-by-line",
        "summary": "Dark theme, cards with hover lift, form on the left, user guide on the right.",
        "code": "* { margin: 5px; padding: 0; box-sizing: border-box; }\nbody { background-color: #1a1a1a; font-family: Arial, sans-serif; }\nheader { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; border-radius: 30px; }\nmain { display: flex; gap: 20px; padding: 20px; }\n.card { background-color: #465402; border: 1px solid #333; border-radius: 10px; padding: 30px; transition: all 0.2s; }\n.card:hover { transform: translateY(-2px); box-shadow: 0 10px 26px rgba(0,0,0,0.35); }\n.b1 { display: flex; flex-direction: column; background-color: #a0c000; }\n.user-guide { flex: 0 0 40%; border-left: 1px solid #333; color: white; }\n.user-guide li:before { content: \"→\"; color: #a0c000; margin-right: 10px; }",
        "line_by_line": [
            ("* { margin: 5px; padding: 0; box-sizing: border-box; }",
             "Universal reset. margin: 5px is unusual (usually 0) — gives everything a small gap. "
             "box-sizing: border-box — padding doesn't add to width (critical for layouts)."),
            ("body { background-color: #1a1a1a; font-family: Arial, sans-serif; }",
             "Dark background (#1a1a1a) + Arial font. "
             "Inherited by all children unless overridden."),
            ("header { display: flex; justify-content: space-between; ... }",
             "Flexbox: logo on left, nav on right. justify-content: space-between pushes them apart. "
             "border-radius: 30px — unusually high, gives a pill shape."),
            ("main { display: flex; gap: 20px; padding: 20px; }",
             "Two-column layout: form (left) + user guide (right). "
             "gap: 20px — space between them (modern alternative to margin)."),
            (".card { background-color: #465402; ... transition: all 0.2s; }",
             "Dark green background (#465402 — dark version of the brand #a0c000). "
             "transition: all 0.2s — animates ANY property change over 0.2s (smooth hover)."),
            (".card:hover { transform: translateY(-2px); box-shadow: 0 10px 26px rgba(0,0,0,0.35); }",
             "On hover: card moves UP 2px + gets a shadow. The 'lift' effect. "
             "translateY(-2px) — negative Y = up. Positive Y = down."),
            (".b1 { display: flex; flex-direction: column; background-color: #a0c000; }",
             "The form. Brand green background. flex-direction: column — stack labels vertically."),
            (".user-guide { flex: 0 0 40%; ... }",
             "flex: 0 0 40% — fixed width, 40% of the container. Won't grow or shrink. "
             "border-left — visual separator from the form."),
            (".user-guide li:before { content: \"→\"; color: #a0c000; }",
             "::before pseudo-element — inserts content BEFORE each <li>. "
             "Adds a green arrow → before each list item. No HTML change needed."),
        ],
        "intuition": (
            "Key techniques: "
            "(1) Flexbox for layout (header, main, form). "
            "(2) Hover lift effect on cards (transform + box-shadow + transition). "
            "(3) ::before pseudo-element for decorative bullets. "
            "(4) Brand color #a0c000 used consistently (form background, arrow color, links). "
            "(5) Dark theme — #1a1a1a background + white text."
        ),
        "common_mistakes": [
            "Forgetting transition: all 0.2s — hover effect snaps instead of animating.",
            "Using margin instead of gap on flex containers — margin collapses, gap doesn't.",
            "Forgetting box-sizing: border-box — padding makes elements wider than expected.",
        ],
    },
]


# Flatten for slug lookup
_BENCH_FLAT = {stage["slug"]: stage for stage in BENCHMARK_COURSE}


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/learn/benchmark", response_class=HTMLResponse)
async def learn_benchmark_overview(request: Request):
    """Render the benchmark engine course overview — all 16 stages."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    return templates.TemplateResponse("learn_benchmark.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "view": "overview",
        "course": BENCHMARK_COURSE,
    })


@router.get("/learn/benchmark/{slug}", response_class=HTMLResponse)
async def learn_benchmark_stage(request: Request, slug: str):
    """Render a single stage page with code + line-by-line explanation."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    stage = _BENCH_FLAT.get(slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    # Find prev/next
    idx = next((i for i, s in enumerate(BENCHMARK_COURSE) if s["slug"] == slug), -1)
    prev_stage = BENCHMARK_COURSE[idx - 1] if idx > 0 else None
    next_stage = BENCHMARK_COURSE[idx + 1] if idx < len(BENCHMARK_COURSE) - 1 else None

    return templates.TemplateResponse("learn_benchmark.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "view": "stage",
        "stage": stage,
        "prev_stage": prev_stage,
        "next_stage": next_stage,
        "total_stages": len(BENCHMARK_COURSE),
    })
