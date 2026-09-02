"""
OpenBenchML — Learn with Project (Student Performance Predictor)
================================================================

A new toggle on /learn that teaches the FULL stack by building ONE
real project from scratch. 12 stages, each with:

    Python  ->  ML  ->  FastAPI  ->  Jinja  ->  HTML

The teaching style follows the "concept -> tiny task -> check -> next"
loop (the same style used in the chat conversation that inspired this
feature).  We never dump 100 lines and say "understand this"; every
stage teaches ONE intuition and asks the learner to write 2-5 lines.

PROJECT: Student Performance Predictor
---------------------------------------
A website where a student enters their study habits and sees a
predicted final-exam score.  Every layer has an obvious motive:

    Student
       |  enters info
       v
    HTML form
       |
       v
    Jinja template (renders the form / the result)
       |
       v
    FastAPI route  (POST /predict)
       |
       v
    Python / ML    (loads trained model, calls .predict)
       |
       v
    Trained model  (model.pkl, trained offline)
       |
       v
    Prediction     (a float, e.g. 81.4)
       |
       v
    Jinja result page
       |
       v
    Student sees the number

This file defines the PROJECT_COURSE list and three routes:

    GET /learn/project            -> overview (12 stages)
    GET /learn/project/{slug}     -> single stage page
    GET /learn/project            (with ?stage=N)  -> same as /{slug}

The course is intentionally kept SEPARATE from the existing LEARN_TREE
so the current Learn section is not disturbed.
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
#  PROJECT COURSE — 12 stages
# ═══════════════════════════════════════════════════════════════════════════

PROJECT_COURSE = [
    # ─── Stage 0 — Project setup & motive ────────────────────────────────
    {
        "stage": 0,
        "slug": "project-stage-00-setup",
        "title": "Why this project? The 5-layer motive",
        "summary": "Pick a project where every layer (Python, ML, FastAPI, Jinja, HTML) has an obvious reason to exist. Meet the Student Performance Predictor.",
        "intuition": (
            "Most courses fail because the project is decorative — you train a model "
            "and then 'also build a frontend' that nobody uses. Here, every layer "
            "exists because the previous one couldn't do the job alone. "
            "\n\n"
            "Python alone can train a model, but it can't serve it to 100 users at once. "
            "FastAPI alone can serve a JSON number, but a student can't type into JSON. "
            "Jinja alone can render a form, but the form needs a server to receive it. "
            "HTML alone can show a number, but it can't compute it. "
            "\n\n"
            "So the chain is forced: each layer solves a real gap."
        ),
        "tiny_task": (
            "On a piece of paper (or in a comment), write the 5 layers in order "
            "and one sentence each on WHY it is needed. Don't write code yet."
        ),
        "check": (
            "Expected answer shape:\n"
            "  Python  -> train the model, do the math\n"
            "  ML      -> turn habits into a predicted score\n"
            "  FastAPI -> accept the form POST, call the model, return the result\n"
            "  Jinja   -> render the form and the result with the same shell\n"
            "  HTML    -> the actual page the student sees in the browser"
        ),
        "routes_box": (
            "No routes yet. This stage is about understanding the WHY. "
            "The routes will be: GET / (home + form), POST /predict (submit form), "
            "GET /result (show prediction). 3 routes total for the whole project."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "At this stage there's no FastAPI yet, so no response model is needed. "
            "We will introduce a Pydantic response model only at Stage 8 — once the "
            "form is working in plain HTML. Don't add it earlier; it would just be "
            "ceremony with no benefit."
        ),
        "files": [
            {
                "name": "folder-structure.txt",
                "lang": "text",
                "code": (
                    "student_predictor/\n"
                    "  app/\n"
                    "    main.py          # FastAPI app + routes\n"
                    "    ml/\n"
                    "      train.py       # trains model.pkl from CSV\n"
                    "      predict.py     # loads model.pkl, exposes predict_score()\n"
                    "      model.pkl      # the trained model (created by train.py)\n"
                    "    templates/\n"
                    "      base.html      # shared shell (nav, footer)\n"
                    "      home.html      # the form page\n"
                    "      result.html    # the result page\n"
                    "    static/\n"
                    "      style.css      # one small stylesheet\n"
                    "  data/\n"
                    "    students.csv     # the dataset\n"
                    "  requirements.txt\n"
                    "  run.sh\n"
                    "\n"
                    "12 files total. That's the whole project."
                ),
            },
        ],
        "explanation": (
            "The folder structure mirrors the 5-layer motive. app/ml/ is the ML layer, "
            "app/main.py is the FastAPI layer, app/templates/ is the Jinja layer, "
            "app/static/ is the HTML/CSS layer. data/ holds the dataset. The split "
            "isn't decoration — it's how you keep 'training time' (offline, slow, "
            "writes model.pkl) separate from 'serving time' (online, fast, reads "
            "model.pkl)."
        ),
        "common_mistakes": [
            "Putting the model training inside the FastAPI route — train once offline, serve many times online.",
            "Skipping the folder structure and dumping everything in main.py — works for 50 lines, breaks at 200.",
            "Picking a dataset with 50 features you don't understand — you'll spend the project fighting the data, not learning the stack.",
        ],
        "next_preview": (
            "Next: Stage 1 loads the dataset with pandas and asks the 4 basic questions: "
            "head(), shape, info(), describe()."
        ),
    },

    # ─── Stage 1 — Dataset understanding ─────────────────────────────────
    {
        "stage": 1,
        "slug": "project-stage-01-dataset",
        "title": "Meet the dataset — 4 questions you always ask",
        "summary": "head(), shape, info(), describe(). The 4 questions you ask of ANY dataset before touching ML.",
        "intuition": (
            "Before you train anything, you must answer 4 questions about the data. "
            "These 4 questions are non-negotiable — skipping them is the #1 cause of "
            "broken ML projects. "
            "\n\n"
            "  1. head()  -> what does a row LOOK like? (columns, value shapes)\n"
            "  2. shape   -> how many rows x columns? (is there enough data?)\n"
            "  3. info()  -> what type is each column? are there nulls?\n"
            "  4. describe()  -> what's the range/mean/std of each numeric column?\n"
            "\n"
            "If you can answer all 4 in one sentence each, you understand the dataset. "
            "If you can't, you're not ready to model it."
        ),
        "tiny_task": (
            "Run these 4 commands on the students.csv below and write down ONE "
            "sentence you learn from each.\n"
            "\n"
            "  import pandas as pd\n"
            "  df = pd.read_csv('students.csv')\n"
            "  df.head()\n"
            "  df.shape\n"
            "  df.info()\n"
            "  df.describe()"
        ),
        "check": (
            "You should learn something like:\n"
            "  head()    -> each row is 1 student, columns are study_hours, attendance, ...\n"
            "  shape     -> 1000 rows x 8 columns  (enough for ML)\n"
            "  info()    -> all numeric, no nulls (lucky us)\n"
            "  describe() -> final_score ranges 0-100, mean 67, std 14"
        ),
        "routes_box": (
            "Still no routes. This stage is pure pandas — runs in a Jupyter cell, "
            "a Python REPL, or our /notebook. No web server needed yet."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "Pandas doesn't need a Pydantic response model — it's a data-analysis "
            "library, not a web framework. The response model question only becomes "
            "real when FastAPI enters at Stage 8."
        ),
        "files": [
            {
                "name": "data/students.csv",
                "lang": "csv",
                "code": (
                    "student_id,study_hours,previous_score,attendance,assignments_completed,sleep_hours,extracurricular_hours,parental_support,final_score\n"
                    "1,4.5,72,85,8,7,2,3,68\n"
                    "2,6.0,81,92,10,7,1,4,79\n"
                    "3,2.0,55,60,4,6,4,2,51\n"
                    "4,7.5,88,95,10,8,0,5,91\n"
                    "5,3.0,65,72,6,5,3,3,62\n"
                    "6,5.5,78,88,9,7,2,4,76\n"
                    "7,1.5,45,55,3,5,5,1,42\n"
                    "8,8.0,92,98,10,8,1,5,95\n"
                    "9,4.0,68,80,7,6,2,3,66\n"
                    "10,6.5,85,90,10,7,0,4,83\n"
                    "... (1000 rows total)\n"
                ),
            },
            {
                "name": "explore.py",
                "lang": "python",
                "code": (
                    "import pandas as pd\n"
                    "\n"
                    "df = pd.read_csv('data/students.csv')\n"
                    "\n"
                    "# Question 1: what does a row look like?\n"
                    "print(df.head())\n"
                    "\n"
                    "# Question 2: how big is the dataset?\n"
                    "print(df.shape)        # (1000, 8)\n"
                    "\n"
                    "# Question 3: types + nulls?\n"
                    "print(df.info())\n"
                    "\n"
                    "# Question 4: spread of numeric columns?\n"
                    "print(df.describe())\n"
                ),
            },
        ],
        "explanation": (
            "head() shows the first 5 rows so you can see what a 'record' actually "
            "looks like — is it a student? a transaction? an image? shape tells you "
            "if you have enough data (100 rows = too few, 1M rows = too slow for "
            "this project). info() reveals nulls and type mismatches — "
            "study_hours as a string instead of a float is a classic bug. describe() "
            "gives you the statistical sanity check — if final_score's max is 250, "
            "something is wrong with the data."
        ),
        "common_mistakes": [
            "Skipping info() and being surprised by nulls at training time.",
            "Not noticing a column is a string when it should be a number — pandas will keep it as object dtype and sklearn will crash later.",
            "Looking at describe() but not asking 'does this make sense?' — if sleep_hours has a max of 24, fine; if it has a max of 50, the data is broken.",
        ],
        "next_preview": (
            "Next: Stage 2 visualises 3 relationships — does study time matter? "
            "does attendance matter? does previous score correlate with final?"
        ),
    },

    # ─── Stage 2 — Visualization ─────────────────────────────────────────
    {
        "stage": 2,
        "slug": "project-stage-02-visualize",
        "title": "3 plots that tell you if ML is even possible",
        "summary": "Scatter plot of each feature vs the target. If there's no visible relationship, ML can't magically find one.",
        "intuition": (
            "Before training, plot each feature against the target. You're looking "
            "for ANY visible trend — a cloud is fine, but a flat horizontal line "
            "means that feature is useless. "
            "\n\n"
            "Why this matters: ML can only learn what's in the data. If "
            "study_hours vs final_score is a flat cloud, no model in the world "
            "can use study_hours to predict final_score. You'd be wasting your "
            "time adding it as a feature. "
            "\n\n"
            "3 plots, 3 questions:\n"
            "  1. study_hours   vs final_score  -> do studiers score higher?\n"
            "  2. attendance    vs final_score  -> do attendees score higher?\n"
            "  3. previous_score vs final_score -> is past performance predictive?"
        ),
        "tiny_task": (
            "Make ONE scatter plot of study_hours vs final_score. Just one. "
            "Don't try to make it pretty.\n"
            "\n"
            "  import matplotlib.pyplot as plt\n"
            "  df.plot.scatter(x='study_hours', y='final_score')\n"
            "  plt.show()"
        ),
        "check": (
            "You should see a cloud that trends UP-AND-TO-THE-RIGHT. "
            "If you see a flat horizontal line, ML on this feature is hopeless. "
            "If you see a clean diagonal, ML will be easy."
        ),
        "routes_box": (
            "Still no routes. Visualization runs offline, in a notebook or script. "
            "The web app will surface these plots later (Stage 11) — but for now "
            "we're just exploring the data."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "Matplotlib returns a Figure object, not JSON. No response model needed."
        ),
        "files": [
            {
                "name": "explore_plots.py",
                "lang": "python",
                "code": (
                    "import pandas as pd\n"
                    "import matplotlib.pyplot as plt\n"
                    "\n"
                    "df = pd.read_csv('data/students.csv')\n"
                    "\n"
                    "fig, axes = plt.subplots(1, 3, figsize=(15, 4))\n"
                    "\n"
                    "# Plot 1: study_hours vs final_score\n"
                    "df.plot.scatter(x='study_hours', y='final_score', ax=axes[0], alpha=0.5)\n"
                    "axes[0].set_title('Study hours vs Final score')\n"
                    "\n"
                    "# Plot 2: attendance vs final_score\n"
                    "df.plot.scatter(x='attendance', y='final_score', ax=axes[1], alpha=0.5, color='green')\n"
                    "axes[1].set_title('Attendance vs Final score')\n"
                    "\n"
                    "# Plot 3: previous_score vs final_score\n"
                    "df.plot.scatter(x='previous_score', y='final_score', ax=axes[2], alpha=0.5, color='orange')\n"
                    "axes[2].set_title('Previous score vs Final score')\n"
                    "\n"
                    "plt.tight_layout()\n"
                    "plt.savefig('data/explore.png', dpi=100)\n"
                    "plt.show()\n"
                ),
            },
        ],
        "explanation": (
            "Each subplot answers one question. If plot 1 trends up, study time "
            "matters. If plot 3 is a tight diagonal, previous_score is the strongest "
            "predictor (it usually is — past performance is the best predictor of "
            "future performance). If a plot is a flat cloud, drop that feature. "
            "The point isn't to make pretty charts — it's to decide which features "
            "deserve to be in your model."
        ),
        "common_mistakes": [
            "Plotting all 8 features at once in a correlation matrix and being overwhelmed. Plot 3, look, decide, move on.",
            "Skipping this step entirely and going straight to model.fit() — you'll have no idea why the model is bad.",
            "Making plots pretty (titles, colors, legends) before checking if they show a trend. Pretty but useless is still useless.",
        ],
        "next_preview": (
            "Next: Stage 3 cleans the data — handles nulls, encodes categoricals, "
            "and splits into X (features) and y (target)."
        ),
    },

    # ─── Stage 3 — Cleaning + X/y split ──────────────────────────────────
    {
        "stage": 3,
        "slug": "project-stage-03-clean",
        "title": "Clean the data + split into X and y",
        "summary": "Drop nulls, encode categoricals, separate features (X) from target (y). The last cleaning step before ML.",
        "intuition": (
            "sklearn models refuse to train on dirty data. 'Dirty' means: nulls, "
            "non-numeric columns, and the target column mixed into the features. "
            "Cleaning fixes all three. "
            "\n\n"
            "  - nulls           -> fill with median (numeric) or mode (categorical)\n"
            "  - categoricals     -> one-hot encode (turn 'low/med/high' into 3 binary columns)\n"
            "  - X / y split     -> X = everything except final_score, y = final_score\n"
            "\n"
            "After this step, X is a 2D numpy array of numbers, y is a 1D array of "
            "numbers. That's the only format sklearn accepts."
        ),
        "tiny_task": (
            "Split the DataFrame into X and y. Just 2 lines:\n"
            "\n"
            "  X = df.drop(columns=['final_score', 'student_id'])\n"
            "  y = df['final_score']\n"
            "\n"
            "Then check X.shape and y.shape. X should be (1000, 6) and y should be (1000,)."
        ),
        "check": (
            "X.shape == (1000, 6)   # 1000 students, 6 features\n"
            "y.shape == (1000,)     # 1000 final scores\n"
            "\n"
            "If X still has final_score in it, your model will cheat by reading the "
            "answer. If X still has student_id, the model will memorize IDs instead "
            "of learning patterns."
        ),
        "routes_box": (
            "Still no routes. Cleaning is offline. The cleaned data lives in memory "
            "(or you can save it as X.csv and y.csv if you want to inspect)."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "This is sklearn/pandas, not FastAPI. No response model needed."
        ),
        "files": [
            {
                "name": "clean.py",
                "lang": "python",
                "code": (
                    "import pandas as pd\n"
                    "\n"
                    "df = pd.read_csv('data/students.csv')\n"
                    "\n"
                    "# Step 1: drop the ID column — it's not a feature\n"
                    "df = df.drop(columns=['student_id'])\n"
                    "\n"
                    "# Step 2: check nulls\n"
                    "print(df.isnull().sum())\n"
                    "# If any column has nulls, fill them:\n"
                    "#   df = df.fillna(df.median(numeric_only=True))\n"
                    "\n"
                    "# Step 3: encode categoricals (parental_support is already numeric 1-5)\n"
                    "# If you had a text column like 'internet_quality' = low/med/high:\n"
                    "#   df = pd.get_dummies(df, columns=['internet_quality'], drop_first=True)\n"
                    "\n"
                    "# Step 4: split into X (features) and y (target)\n"
                    "X = df.drop(columns=['final_score'])\n"
                    "y = df['final_score']\n"
                    "\n"
                    "print('X shape:', X.shape)   # (1000, 6)\n"
                    "print('y shape:', y.shape)   # (1000,)\n"
                    "print('Features:', list(X.columns))\n"
                ),
            },
        ],
        "explanation": (
            "drop(student_id) is critical — IDs are unique per row, so the model "
            "would just memorize 'student 1 -> 68' instead of learning the pattern "
            "'more study hours -> higher score'. drop(final_score) is even more "
            "critical — leaving the target in X is called 'data leakage' and gives "
            "you 100% accuracy that completely fails on new students. "
            "get_dummies turns a categorical column into N binary columns — "
            "essential for sklearn which only accepts numbers."
        ),
        "common_mistakes": [
            "Forgetting to drop student_id — model memorizes instead of generalizing.",
            "Leaking the target into X — model reports 99% accuracy and fails on real students.",
            "Calling get_dummies BEFORE the train/test split — causes 'feature mismatch' at prediction time when a new student has a category the model never saw.",
        ],
        "next_preview": (
            "Next: Stage 4 trains your first ML model — LinearRegression — with "
            "fit() and score(). Just 4 lines."
        ),
    },

    # ─── Stage 4 — First ML model ────────────────────────────────────────
    {
        "stage": 4,
        "slug": "project-stage-04-first-model",
        "title": "Your first ML model — 4 lines that do the magic",
        "summary": "train_test_split + LinearRegression.fit + .predict + .score. The smallest possible ML pipeline.",
        "intuition": (
            "ML training is shockingly small once the data is clean. 4 lines: "
            "\n"
            "  1. Split X, y into train and test sets (80/20)\n"
            "  2. Create a LinearRegression() object\n"
            "  3. Call model.fit(X_train, y_train) — this is the 'learning'\n"
            "  4. Call model.score(X_test, y_test) — this is the 'grade'\n"
            "\n"
            "fit() is where the math happens. For LinearRegression, it finds the "
            "best-fitting line through the data (least squares). For "
            "RandomForest, it builds many decision trees. You don't write the "
            "math — sklearn did. Your job is to feed it clean data and read the score."
        ),
        "tiny_task": (
            "Train a LinearRegression on the student data and print the score.\n"
            "\n"
            "  from sklearn.linear_model import LinearRegression\n"
            "  from sklearn.model_selection import train_test_split\n"
            "  X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)\n"
            "  model = LinearRegression().fit(X_train, y_train)\n"
            "  print(model.score(X_test, y_test))"
        ),
        "check": (
            "score should be around 0.75-0.85 — meaning the model explains 75-85% "
            "of the variance in final_score. If it's near 0, your data is dirty. "
            "If it's 1.0, you have data leakage (final_score is in X)."
        ),
        "routes_box": (
            "Still no routes. This is the offline training script that produces "
            "model.pkl. Once we have model.pkl, Stage 8 will load it inside a "
            "FastAPI route to serve predictions."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "Training script, not web server. No response model needed."
        ),
        "files": [
            {
                "name": "app/ml/train.py",
                "lang": "python",
                "code": (
                    "import pandas as pd\n"
                    "from sklearn.linear_model import LinearRegression\n"
                    "from sklearn.model_selection import train_test_split\n"
                    "import joblib\n"
                    "\n"
                    "# 1. Load + clean (same as Stage 3)\n"
                    "df = pd.read_csv('data/students.csv').drop(columns=['student_id'])\n"
                    "X = df.drop(columns=['final_score'])\n"
                    "y = df['final_score']\n"
                    "\n"
                    "# 2. Split into train (80%) and test (20%)\n"
                    "X_train, X_test, y_train, y_test = train_test_split(\n"
                    "    X, y, test_size=0.2, random_state=42\n"
                    ")\n"
                    "\n"
                    "# 3. Train (the 'learning' step)\n"
                    "model = LinearRegression()\n"
                    "model.fit(X_train, y_train)\n"
                    "\n"
                    "# 4. Score (the 'grade')\n"
                    "train_score = model.score(X_train, y_train)\n"
                    "test_score  = model.score(X_test, y_test)\n"
                    "print(f'Train R^2: {train_score:.3f}')\n"
                    "print(f'Test  R^2: {test_score:.3f}')\n"
                    "\n"
                    "# 5. Save the trained model so FastAPI can load it later\n"
                    "joblib.dump(model, 'app/ml/model.pkl')\n"
                    "print('Saved -> app/ml/model.pkl')\n"
                ),
            },
            {
                "name": "run.sh",
                "lang": "bash",
                "code": (
                    "pip install pandas scikit-learn joblib\n"
                    "python app/ml/train.py\n"
                    "\n"
                    "# Output:\n"
                    "#   Train R^2: 0.823\n"
                    "#   Test  R^2: 0.798\n"
                    "#   Saved -> app/ml/model.pkl\n"
                ),
            },
        ],
        "explanation": (
            "train_test_split is the most important line in ML. It carves out 20% "
            "of the data the model never sees during training, then we score on "
            "that unseen 20%. This number (test R^2) is the ONLY honest measure "
            "of how the model will perform on new students. Train R^2 is "
            "optimistic — the model has seen that data. If train is 0.99 and "
            "test is 0.50, you've overfit. joblib.dump serializes the trained "
            "model to a .pkl file so the web app can load it without re-training."
        ),
        "common_mistakes": [
            "Scoring on the train set and reporting it as the model's accuracy — that's cheating.",
            "Forgetting random_state — every run gives a different split, so your scores aren't reproducible.",
            "Not saving the model — you'd have to retrain on every server restart, which is slow and gives different models.",
        ],
        "next_preview": (
            "Next: Stage 5 explains what that 0.80 R^2 actually means — and "
            "introduces MAE, MSE, RMSE so you can interpret predictions in real units."
        ),
    },

    # ─── Stage 5 — Evaluation metrics ────────────────────────────────────
    {
        "stage": 5,
        "slug": "project-stage-05-metrics",
        "title": "What does R^2 = 0.80 actually mean?",
        "summary": "MAE, MSE, RMSE, R^2 — 4 metrics that answer 4 different questions about model quality.",
        "intuition": (
            "R^2 = 0.80 means 'the model explains 80% of the variance in "
            "final_score'. That's an abstract statistical statement. "
            "\n\n"
            "For a real-world project, you want metrics in the SAME UNITS as the "
            "target. If final_score is 0-100, you want to say 'on average, the "
            "model is off by 5 points'. That's MAE. "
            "\n\n"
            "4 metrics, 4 questions:\n"
            "  MAE  -> 'on average, how many points off?'         (in target units)\n"
            "  MSE  -> 'how bad are the BIG errors?'              (squared, penalises outliers)\n"
            "  RMSE -> same as MSE but in target units            (interpretable)\n"
            "  R^2  -> 'how much better than just guessing mean?' (0 to 1, scale-free)"
        ),
        "tiny_task": (
            "Compute MAE for your trained model and interpret it.\n"
            "\n"
            "  from sklearn.metrics import mean_absolute_error\n"
            "  y_pred = model.predict(X_test)\n"
            "  mae = mean_absolute_error(y_test, y_pred)\n"
            "  print(f'MAE = {mae:.2f} points')"
        ),
        "check": (
            "If MAE = 4.5, that means: 'on average, the model's prediction is "
            "4.5 points off from the actual final_score'. Since final_score is "
            "0-100, that's 4.5% error — pretty good!"
        ),
        "routes_box": (
            "Still no routes. Metrics are computed offline. Once the FastAPI app "
            "is live, we can surface these metrics on a '/model-info' page — but "
            "the metrics themselves are computed here, at training time."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "Offline metric computation, no FastAPI. No response model needed."
        ),
        "files": [
            {
                "name": "app/ml/evaluate.py",
                "lang": "python",
                "code": (
                    "import pandas as pd\n"
                    "from sklearn.linear_model import LinearRegression\n"
                    "from sklearn.model_selection import train_test_split\n"
                    "from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score\n"
                    "import numpy as np\n"
                    "\n"
                    "df = pd.read_csv('data/students.csv').drop(columns=['student_id'])\n"
                    "X = df.drop(columns=['final_score'])\n"
                    "y = df['final_score']\n"
                    "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n"
                    "\n"
                    "model = LinearRegression().fit(X_train, y_train)\n"
                    "y_pred = model.predict(X_test)\n"
                    "\n"
                    "print(f'MAE  = {mean_absolute_error(y_test, y_pred):.2f} points')\n"
                    "print(f'MSE  = {mean_squared_error(y_test, y_pred):.2f}')\n"
                    "print(f'RMSE = {np.sqrt(mean_squared_error(y_test, y_pred)):.2f} points')\n"
                    "print(f'R^2  = {r2_score(y_test, y_pred):.3f}')\n"
                    "\n"
                    "# Example output:\n"
                    "#   MAE  = 4.32 points\n"
                    "#   MSE  = 28.50\n"
                    "#   RMSE = 5.34 points\n"
                    "#   R^2  = 0.798\n"
                ),
            },
        ],
        "explanation": (
            "MAE is the most interpretable — 'off by 4.3 points on average' makes "
            "sense to anyone. RMSE is similar but bigger because it squares the "
            "errors first (so a 20-point error counts 16x as much as a 5-point "
            "error — RMSE punishes big mistakes). R^2 is scale-free, so you can "
            "compare it across datasets — but it doesn't tell you 'how many points "
            "off'. Always report MAE to non-technical people; always report R^2 in "
            "academic papers; report both in production dashboards."
        ),
        "common_mistakes": [
            "Reporting only R^2 — your boss will ask 'but how many points off is that?' and you won't have an answer.",
            "Confusing MSE and RMSE — MSE is in squared units (points^2), RMSE is in target units (points). Always report RMSE, never MSE directly.",
            "Computing metrics on the TRAIN set — use the test set, always. Train metrics are optimism, test metrics are reality.",
        ],
        "next_preview": (
            "Next: Stage 6 is ERROR ANALYSIS — sort by absolute error, look at the "
            "worst predictions, and ask 'what kind of student does the model get wrong?'"
        ),
    },

    # ─── Stage 6 — Error analysis ────────────────────────────────────────
    {
        "stage": 6,
        "slug": "project-stage-06-error-analysis",
        "title": "Find your worst predictions — error analysis",
        "summary": "Don't just calculate a metric. Investigate WHERE the model fails. This is what separates real ML from API-calling.",
        "intuition": (
            "A metric tells you HOW BAD the model is on average. Error analysis "
            "tells you WHERE it's bad — and that's 10x more useful. "
            "\n\n"
            "Steps:\n"
            "  1. Build a results DataFrame with: Actual, Predicted, Error, Abs_Error\n"
            "  2. Sort by Abs_Error descending — the top rows are your worst predictions\n"
            "  3. Look up the original features for those worst rows (X_test.loc[idx])\n"
            "  4. Ask: 'what's unusual about this student?'\n"
            "\n"
            "This is where ML becomes interesting. You're no longer doing "
            "fit/predict/score — you're debugging the model's reasoning."
        ),
        "tiny_task": (
            "Sort the results by Absolute_Error descending and show the top 10.\n"
            "\n"
            "  results = pd.DataFrame({\n"
            "      'Actual': y_test,\n"
            "      'Predicted': y_pred,\n"
            "  })\n"
            "  results['Error'] = results['Actual'] - results['Predicted']\n"
            "  results['Abs_Error'] = results['Error'].abs()\n"
            "  worst10 = results.sort_values(by='Abs_Error', ascending=False).head(10)\n"
            "  print(worst10)"
        ),
        "check": (
            "You'll see something like:\n"
            "       Actual  Predicted   Error  Abs_Error\n"
            "  220   47.9     86.4    -38.5      38.5\n"
            "  10    98.0     66.7     31.3      31.3\n"
            "  ...\n"
            "\n"
            "These are the students the model gets badly wrong. Next we ask WHY."
        ),
        "routes_box": (
            "No routes. Error analysis is offline — it's how you decide whether "
            "to retrain with more features, switch to RandomForest, or accept the "
            "current model and ship it."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "Pandas DataFrame analysis. No FastAPI. No response model."
        ),
        "files": [
            {
                "name": "app/ml/error_analysis.py",
                "lang": "python",
                "code": (
                    "import pandas as pd\n"
                    "from sklearn.linear_model import LinearRegression\n"
                    "from sklearn.model_selection import train_test_split\n"
                    "\n"
                    "df = pd.read_csv('data/students.csv').drop(columns=['student_id'])\n"
                    "X = df.drop(columns=['final_score'])\n"
                    "y = df['final_score']\n"
                    "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n"
                    "model = LinearRegression().fit(X_train, y_train)\n"
                    "y_pred = model.predict(X_test)\n"
                    "\n"
                    "# Build the results table\n"
                    "results = pd.DataFrame({'Actual': y_test, 'Predicted': y_pred})\n"
                    "results['Error']     = results['Actual'] - results['Predicted']\n"
                    "results['Abs_Error'] = results['Error'].abs()\n"
                    "\n"
                    "# Top 10 worst predictions\n"
                    "worst10 = results.sort_values(by='Abs_Error', ascending=False).head(10)\n"
                    "print('=== WORST 10 PREDICTIONS ===')\n"
                    "print(worst10)\n"
                    "\n"
                    "# Look up the features for the very worst prediction\n"
                    "worst_idx = worst10.index[0]\n"
                    "print(f'\\n=== FEATURES OF WORST PREDICTION (index {worst_idx}) ===')\n"
                    "print(X_test.loc[worst_idx])\n"
                    "\n"
                    "# Compare with a student the model got RIGHT\n"
                    "best10 = results.sort_values(by='Abs_Error').head(10)\n"
                    "best_idx = best10.index[0]\n"
                    "print(f'\\n=== FEATURES OF BEST PREDICTION (index {best_idx}) ===')\n"
                    "print(X_test.loc[best_idx])\n"
                ),
            },
        ],
        "explanation": (
            "Sorting by Abs_Error reveals the model's blind spots. The worst row "
            "(Actual 47.9, Predicted 86.4) is a student the model thought would "
            "score high but actually scored low. Why? Look at their features — "
            "maybe they have high study_hours AND low attendance, and the model "
            "weighted study_hours too heavily. The best row tells you what the "
            "model is GOOD at — probably 'average students with average "
            "everything'. Linear models fail on outliers because they assume a "
            "linear relationship. A RandomForest (Stage 7) handles outliers "
            "better because it bins features."
        ),
        "common_mistakes": [
            "Computing the metric and moving on — the metric is the START of the analysis, not the end.",
            "Not looking up the original features — without X_test.loc[idx], the worst-10 list is just numbers with no story.",
            "Comparing only the worst prediction — always look at worst AND best to see what the model is good vs bad at.",
        ],
        "next_preview": (
            "Next: Stage 7 swaps LinearRegression for RandomForest and compares. "
            "Does a non-linear model fix those worst predictions?"
        ),
    },

    # ─── Stage 7 — Better model (RandomForest) ───────────────────────────
    {
        "stage": 7,
        "slug": "project-stage-07-randomforest",
        "title": "Try a better model — RandomForest",
        "summary": "Same X, same y, different model. RandomForest captures non-linear patterns that LinearRegression can't.",
        "intuition": (
            "LinearRegression assumes final_score is a weighted sum of features: "
            "score = 5 + 2*study_hours + 0.3*attendance + ... "
            "That's a plane in 6-dimensional space. "
            "\n\n"
            "RandomForest doesn't assume any shape. It builds 100 decision trees, "
            "each one asking yes/no questions like 'study_hours > 5?' and "
            "averaging their predictions. It can learn 'students who study > 5 "
            "hours AND have attendance > 80 score high, BUT students who study "
            "> 5 hours with attendance < 50 score low' — interactions that "
            "LinearRegression can't represent. "
            "\n\n"
            "The pattern in real ML: start with LinearRegression (simple, "
            "interpretable), then try RandomForest (more accurate, less "
            "interpretable), and compare."
        ),
        "tiny_task": (
            "Train a RandomForest on the same X, y and compare test R^2.\n"
            "\n"
            "  from sklearn.ensemble import RandomForestRegressor\n"
            "  rf = RandomForestRegressor(n_estimators=100, random_state=42)\n"
            "  rf.fit(X_train, y_train)\n"
            "  print(f'Linear R^2: {model.score(X_test, y_test):.3f}')\n"
            "  print(f'Forest  R^2: {rf.score(X_test, y_test):.3f}')"
        ),
        "check": (
            "RandomForest usually beats LinearRegression by 5-10% R^2 on this "
            "kind of data. If RF is WORSE, your data is mostly linear — and "
            "LinearRegression is the right choice (simpler, faster, more "
            "interpretable)."
        ),
        "routes_box": (
            "Still offline. We're choosing the BEST model before saving it as "
            "model.pkl. Once we save it (next stage), the FastAPI app doesn't "
            "care which algorithm was used — it just calls .predict()."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "Model comparison is offline. No response model."
        ),
        "files": [
            {
                "name": "app/ml/compare_models.py",
                "lang": "python",
                "code": (
                    "import pandas as pd\n"
                    "from sklearn.linear_model import LinearRegression\n"
                    "from sklearn.ensemble import RandomForestRegressor\n"
                    "from sklearn.model_selection import train_test_split\n"
                    "from sklearn.metrics import mean_absolute_error, r2_score\n"
                    "import joblib\n"
                    "\n"
                    "df = pd.read_csv('data/students.csv').drop(columns=['student_id'])\n"
                    "X = df.drop(columns=['final_score'])\n"
                    "y = df['final_score']\n"
                    "X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n"
                    "\n"
                    "# Model A: LinearRegression\n"
                    "lr = LinearRegression().fit(X_train, y_train)\n"
                    "lr_pred = lr.predict(X_test)\n"
                    "print(f'LinearRegression:  R^2={r2_score(y_test, lr_pred):.3f}  MAE={mean_absolute_error(y_test, lr_pred):.2f}')\n"
                    "\n"
                    "# Model B: RandomForest\n"
                    "rf = RandomForestRegressor(n_estimators=100, random_state=42).fit(X_train, y_train)\n"
                    "rf_pred = rf.predict(X_test)\n"
                    "print(f'RandomForest:      R^2={r2_score(y_test, rf_pred):.3f}  MAE={mean_absolute_error(y_test, rf_pred):.2f}')\n"
                    "\n"
                    "# Save the winner\n"
                    "if r2_score(y_test, rf_pred) > r2_score(y_test, lr_pred):\n"
                    "    joblib.dump(rf, 'app/ml/model.pkl')\n"
                    "    print('Saved RandomForest -> app/ml/model.pkl')\n"
                    "else:\n"
                    "    joblib.dump(lr, 'app/ml/model.pkl')\n"
                    "    print('Saved LinearRegression -> app/ml/model.pkl')\n"
                ),
            },
        ],
        "explanation": (
            "n_estimators=100 means 'build 100 decision trees and average their "
            "predictions'. More trees = more accurate but slower. 100 is the "
            "sweet spot for small datasets. random_state=42 makes the result "
            "reproducible — without it, every run gives a different forest. "
            "We save the winner — the FastAPI app doesn't care which algorithm "
            "won, because both LinearRegression and RandomForestRegressor have "
            "the same .predict() method. That's the beauty of sklearn's API."
        ),
        "common_mistakes": [
            "Using n_estimators=10 — too few trees, model is unstable. Use 100 minimum.",
            "Forgetting random_state — every run gives different scores, you can't compare models fairly.",
            "Picking the model with higher TRAIN R^2 instead of TEST R^2 — you'll pick the overfit one.",
        ],
        "next_preview": (
            "Next: Stage 8 is where FastAPI enters. We load model.pkl and expose "
            "the FIRST route: POST /predict that takes JSON and returns a score."
        ),
    },

    # ─── Stage 8 — First FastAPI route (POST /predict) ───────────────────
    {
        "stage": 8,
        "slug": "project-stage-08-fastapi-predict",
        "title": "First FastAPI route — POST /predict",
        "summary": "Load model.pkl once at startup. Expose POST /predict that takes JSON input and returns a predicted score.",
        "intuition": (
            "Finally — FastAPI enters. The route is shockingly small: "
            "\n"
            "  1. Load model.pkl ONCE when the app starts (don't load it per request — slow!)\n"
            "  2. Define a Pydantic model for the input JSON (StudentInput)\n"
            "  3. POST /predict receives StudentInput, builds a DataFrame, calls model.predict\n"
            "  4. Return the predicted score as JSON\n"
            "\n"
            "This is the moment the ML model becomes a SERVICE. Anyone with curl "
            "can now get a prediction."
        ),
        "tiny_task": (
            "Run the FastAPI app below and test it with curl.\n"
            "\n"
            "  python app/main.py\n"
            "\n"
            "Then in another terminal:\n"
            "  curl -X POST http://localhost:8000/predict \\\n"
            "       -H 'Content-Type: application/json' \\\n"
            "       -d '{\"study_hours\":6, \"previous_score\":72, \"attendance\":85, \"assignments_completed\":8, \"sleep_hours\":7, \"extracurricular_hours\":2, \"parental_support\":3}'\n"
            "\n"
            "You should get back: {\"predicted_score\": 76.4}"
        ),
        "check": (
            "If you see {\"predicted_score\": 76.4} (or similar), the whole ML "
            "pipeline is now reachable over HTTP. The model trained offline is "
            "now serving real-time predictions. That's the magic moment."
        ),
        "routes_box": (
            "ROUTES INTRODUCED HERE:\n"
            "  POST /predict  ->  takes StudentInput JSON, returns PredictResponse JSON\n"
            "\n"
            "Only ONE route so far. We'll add GET / (home page with form) in "
            "Stage 9, and the form will POST to this same /predict endpoint."
        ),
        "is_response_model_needed": "YES",
        "response_model_explanation": (
            "Yes — and here's why. Pydantic response models do THREE jobs at once:\n"
            "\n"
            "  1. VALIDATION of the output  ->  if your model returns a NaN, FastAPI catches it\n"
            "  2. DOCUMENTATION  ->  /docs shows the exact shape of the response\n"
            "  3. SERIALIZATION  ->  Python float -> JSON number automatically\n"
            "\n"
            "Without a response model, FastAPI would still return JSON — but you'd "
            "lose validation and docs. For a toy project, you can skip it. For "
            "anything real, always declare a response_model. It's 2 lines of code "
            "and pays for itself the first time a bug returns the wrong shape."
        ),
        "files": [
            {
                "name": "app/main.py",
                "lang": "python",
                "code": (
                    "from fastapi import FastAPI\n"
                    "from pydantic import BaseModel, Field\n"
                    "import joblib\n"
                    "import pandas as pd\n"
                    "import uvicorn\n"
                    "\n"
                    "app = FastAPI(title='Student Performance Predictor')\n"
                    "\n"
                    "# ── Load model ONCE at startup ──────────────────────────\n"
                    "# Don't load per request — would be 100x slower.\n"
                    "model = joblib.load('app/ml/model.pkl')\n"
                    "\n"
                    "\n"
                    "# ── Pydantic models (request + response) ───────────────\n"
                    "class StudentInput(BaseModel):\n"
                    "    study_hours: float = Field(..., ge=0, le=24)\n"
                    "    previous_score: float = Field(..., ge=0, le=100)\n"
                    "    attendance: float = Field(..., ge=0, le=100)\n"
                    "    assignments_completed: int = Field(..., ge=0, le=20)\n"
                    "    sleep_hours: float = Field(..., ge=0, le=24)\n"
                    "    extracurricular_hours: float = Field(..., ge=0, le=10)\n"
                    "    parental_support: int = Field(..., ge=1, le=5)\n"
                    "\n"
                    "\n"
                    "class PredictResponse(BaseModel):\n"
                    "    predicted_score: float\n"
                    "    performance_band: str  # 'Poor' / 'OK' / 'Good' / 'Excellent'\n"
                    "\n"
                    "\n"
                    "# ── Route: POST /predict ────────────────────────────────\n"
                    "@app.post('/predict', response_model=PredictResponse)\n"
                    "async def predict(student: StudentInput):\n"
                    "    # Pydantic already validated the input. Build a 1-row DataFrame\n"
                    "    # with the EXACT same column order as training.\n"
                    "    X_new = pd.DataFrame([{\n"
                    "        'study_hours': student.study_hours,\n"
                    "        'previous_score': student.previous_score,\n"
                    "        'attendance': student.attendance,\n"
                    "        'assignments_completed': student.assignments_completed,\n"
                    "        'sleep_hours': student.sleep_hours,\n"
                    "        'extracurricular_hours': student.extracurricular_hours,\n"
                    "        'parental_support': student.parental_support,\n"
                    "    }])\n"
                    "    score = float(model.predict(X_new)[0])\n"
                    "\n"
                    "    # Bucket into a performance band for the UI\n"
                    "    if score < 50:    band = 'Poor'\n"
                    "    elif score < 70:  band = 'OK'\n"
                    "    elif score < 85:  band = 'Good'\n"
                    "    else:             band = 'Excellent'\n"
                    "\n"
                    "    return PredictResponse(predicted_score=round(score, 1),\n"
                    "                           performance_band=band)\n"
                    "\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    uvicorn.run(app, host='0.0.0.0', port=8000)\n"
                ),
            },
            {
                "name": "test_predict.sh",
                "lang": "bash",
                "code": (
                    "# Start the server\n"
                    "python app/main.py &\n"
                    "\n"
                    "# Test with curl\n"
                    "curl -X POST http://localhost:8000/predict \\\n"
                    "  -H 'Content-Type: application/json' \\\n"
                    "  -d '{\n"
                    "    \"study_hours\": 6,\n"
                    "    \"previous_score\": 72,\n"
                    "    \"attendance\": 85,\n"
                    "    \"assignments_completed\": 8,\n"
                    "    \"sleep_hours\": 7,\n"
                    "    \"extracurricular_hours\": 2,\n"
                    "    \"parental_support\": 3\n"
                    "  }'\n"
                    "\n"
                    "# Response:\n"
                    "# {\"predicted_score\":76.4,\"performance_band\":\"Good\"}\n"
                    "\n"
                    "# Try invalid input — FastAPI returns 422 automatically:\n"
                    "curl -X POST http://localhost:8000/predict \\\n"
                    "  -H 'Content-Type: application/json' \\\n"
                    "  -d '{\"study_hours\": 999}'\n"
                    "# -> 422 Unprocessable Entity (study_hours must be <= 24)\n"
                ),
            },
        ],
        "explanation": (
            "Three big ideas in this route: "
            "(1) LOAD MODEL ONCE — `model = joblib.load(...)` runs at module import "
            "time, not inside the route. If you loaded it per request, every "
            "prediction would take 500ms instead of 5ms. "
            "(2) Pydantic input — StudentInput validates input. If a user sends "
            "study_hours=999, FastAPI returns 422 automatically — your route "
            "code never runs. You never write validation code; Pydantic does it. "
            "(3) response_model=PredictResponse — FastAPI serializes the return "
            "value AND validates the output shape. If your route returns a NaN, "
            "FastAPI catches it instead of sending 'NaN' as JSON (which is "
            "invalid JSON and breaks the client)."
        ),
        "common_mistakes": [
            "Loading the model inside the route — every request reloads the .pkl, 100x slower.",
            "Not using response_model — you lose validation, lose /docs, and risk returning NaN as JSON.",
            "Building the input DataFrame with columns in a different ORDER than training — sklearn will silently give wrong predictions. Always match training column order exactly.",
        ],
        "next_preview": (
            "Next: Stage 9 adds the HTML form — Jinja2 templates that let a "
            "student type their info and click submit. Same /predict endpoint, "
            "now reachable from a browser."
        ),
    },

    # ─── Stage 9 — Jinja2 templates + form ───────────────────────────────
    {
        "stage": 9,
        "slug": "project-stage-09-jinja-form",
        "title": "Add Jinja2 templates — the form page",
        "summary": "base.html shell + home.html form. POSTs to the same /predict endpoint — but now from a browser, not curl.",
        "intuition": (
            "Right now /predict only accepts JSON. Browsers can't send JSON from "
            "a form — they send form-encoded data. Two options: "
            "\n"
            "  A. Add a SECOND route that accepts form-encoded data and returns HTML\n"
            "  B. Use JavaScript fetch() to send JSON from the form\n"
            "\n"
            "Option A is simpler and more classic — the form POSTs to /predict-form, "
            "FastAPI reads the form fields, calls the model, and renders result.html "
            "with the prediction. No JavaScript. This is the Jinja2 pattern."
        ),
        "tiny_task": (
            "Create base.html with a nav and an empty {% block content %}. Then "
            "create home.html that extends base.html and renders a <form> with "
            "7 number inputs, one per feature. Don't worry about styling yet."
        ),
        "check": (
            "Visit http://localhost:8000/ — you should see a bare HTML form with "
            "7 inputs and a Submit button. The form's action='/predict-form' "
            "method='POST'. Submitting will 404 until we add the route in the "
            "next file."
        ),
        "routes_box": (
            "ROUTES INTRODUCED HERE:\n"
            "  GET  /              ->  renders home.html (the form)\n"
            "  POST /predict-form  ->  reads form data, calls model, renders result.html\n"
            "\n"
            "Plus the existing POST /predict (JSON API) from Stage 8 stays — we "
            "now have TWO ways to get a prediction: JSON (for scripts) and form "
            "(for browsers). Total: 3 routes."
        ),
        "is_response_model_needed": "NO (for the form routes)",
        "response_model_explanation": (
            "The form routes return HTML, not JSON. Pydantic response_model is "
            "only for JSON responses — for HTML you use `response_class=HTMLResponse`. "
            "We keep the response_model on POST /predict (the JSON API) because "
            "that's still useful for scripts and the /docs page."
        ),
        "files": [
            {
                "name": "app/main.py",
                "lang": "python",
                "code": (
                    "from fastapi import FastAPI, Request, Form\n"
                    "from fastapi.responses import HTMLResponse\n"
                    "from fastapi.templating import Jinja2Templates\n"
                    "from pydantic import BaseModel, Field\n"
                    "import joblib, pandas as pd, uvicorn\n"
                    "\n"
                    "app = FastAPI(title='Student Performance Predictor')\n"
                    "templates = Jinja2Templates(directory='app/templates')\n"
                    "model = joblib.load('app/ml/model.pkl')\n"
                    "\n"
                    "FEATURES = ['study_hours', 'previous_score', 'attendance',\n"
                    "            'assignments_completed', 'sleep_hours',\n"
                    "            'extracurricular_hours', 'parental_support']\n"
                    "\n"
                    "def _predict(features_dict: dict) -> tuple[float, str]:\n"
                    "    X_new = pd.DataFrame([features_dict])[FEATURES]\n"
                    "    score = float(model.predict(X_new)[0])\n"
                    "    if score < 50:   band = 'Poor'\n"
                    "    elif score < 70: band = 'OK'\n"
                    "    elif score < 85: band = 'Good'\n"
                    "    else:            band = 'Excellent'\n"
                    "    return round(score, 1), band\n"
                    "\n"
                    "# ── Route 1: JSON API (Stage 8) ─────────────────────────\n"
                    "class StudentInput(BaseModel):\n"
                    "    study_hours: float = Field(..., ge=0, le=24)\n"
                    "    previous_score: float = Field(..., ge=0, le=100)\n"
                    "    attendance: float = Field(..., ge=0, le=100)\n"
                    "    assignments_completed: int = Field(..., ge=0, le=20)\n"
                    "    sleep_hours: float = Field(..., ge=0, le=24)\n"
                    "    extracurricular_hours: float = Field(..., ge=0, le=10)\n"
                    "    parental_support: int = Field(..., ge=1, le=5)\n"
                    "\n"
                    "class PredictResponse(BaseModel):\n"
                    "    predicted_score: float\n"
                    "    performance_band: str\n"
                    "\n"
                    "@app.post('/predict', response_model=PredictResponse)\n"
                    "async def predict_json(student: StudentInput):\n"
                    "    score, band = _predict(student.model_dump())\n"
                    "    return PredictResponse(predicted_score=score, performance_band=band)\n"
                    "\n"
                    "# ── Route 2: home page (the form) ───────────────────────\n"
                    "@app.get('/', response_class=HTMLResponse)\n"
                    "async def home(request: Request):\n"
                    "    return templates.TemplateResponse('home.html', {\n"
                    "        'request': request,\n"
                    "        'features': FEATURES,\n"
                    "    })\n"
                    "\n"
                    "# ── Route 3: form submission ────────────────────────────\n"
                    "@app.post('/predict-form', response_class=HTMLResponse)\n"
                    "async def predict_form(\n"
                    "    request: Request,\n"
                    "    study_hours: float = Form(...),\n"
                    "    previous_score: float = Form(...),\n"
                    "    attendance: float = Form(...),\n"
                    "    assignments_completed: int = Form(...),\n"
                    "    sleep_hours: float = Form(...),\n"
                    "    extracurricular_hours: float = Form(...),\n"
                    "    parental_support: int = Form(...),\n"
                    "):\n"
                    "    features = {\n"
                    "        'study_hours': study_hours,\n"
                    "        'previous_score': previous_score,\n"
                    "        'attendance': attendance,\n"
                    "        'assignments_completed': assignments_completed,\n"
                    "        'sleep_hours': sleep_hours,\n"
                    "        'extracurricular_hours': extracurricular_hours,\n"
                    "        'parental_support': parental_support,\n"
                    "    }\n"
                    "    score, band = _predict(features)\n"
                    "    return templates.TemplateResponse('result.html', {\n"
                    "        'request': request,\n"
                    "        'score': score,\n"
                    "        'band': band,\n"
                    "        'inputs': features,\n"
                    "    })\n"
                    "\n"
                    "if __name__ == '__main__':\n"
                    "    uvicorn.run(app, host='0.0.0.0', port=8000)\n"
                ),
            },
            {
                "name": "app/templates/base.html",
                "lang": "html",
                "code": (
                    "<!DOCTYPE html>\n"
                    "<html>\n"
                    "<head>\n"
                    "  <title>{% block title %}Student Predictor{% endblock %}</title>\n"
                    "  <link rel='stylesheet' href='/static/style.css'>\n"
                    "</head>\n"
                    "<body>\n"
                    "  <header>\n"
                    "    <p>Student Performance Predictor</p>\n"
                    "    <nav>\n"
                    "      <a href='/'>Home</a>\n"
                    "      <a href='/docs'>API</a>\n"
                    "    </nav>\n"
                    "  </header>\n"
                    "  <main>\n"
                    "    {% block content %}{% endblock %}\n"
                    "  </main>\n"
                    "  <footer><p>Built with FastAPI + Jinja2 + sklearn</p></footer>\n"
                    "  </body>\n"
                    "</html>\n"
                ),
            },
            {
                "name": "app/templates/home.html",
                "lang": "html",
                "code": (
                    "{% extends 'base.html' %}\n"
                    "{% block title %}Enter your study habits{% endblock %}\n"
                    "\n"
                    "{% block content %}\n"
                    "  <h1>Predict your final score</h1>\n"
                    "  <form method='post' action='/predict-form'>\n"
                    "    <label>Study hours/day\n"
                    "      <input type='number' step='0.1' name='study_hours' required>\n"
                    "    </label>\n"
                    "    <label>Previous score\n"
                    "      <input type='number' name='previous_score' required>\n"
                    "    </label>\n"
                    "    <label>Attendance %\n"
                    "      <input type='number' name='attendance' required>\n"
                    "    </label>\n"
                    "    <label>Assignments completed\n"
                    "      <input type='number' name='assignments_completed' required>\n"
                    "    </label>\n"
                    "    <label>Sleep hours\n"
                    "      <input type='number' step='0.1' name='sleep_hours' required>\n"
                    "    </label>\n"
                    "    <label>Extracurricular hours\n"
                    "      <input type='number' step='0.1' name='extracurricular_hours' required>\n"
                    "    </label>\n"
                    "    <label>Parental support (1-5)\n"
                    "      <input type='number' min='1' max='5' name='parental_support' required>\n"
                    "    </label>\n"
                    "    <button type='submit'>Predict Score</button>\n"
                    "  </form>\n"
                    "{% endblock %}\n"
                ),
            },
            {
                "name": "app/templates/result.html",
                "lang": "html",
                "code": (
                    "{% extends 'base.html' %}\n"
                    "{% block title %}Your predicted score{% endblock %}\n"
                    "\n"
                    "{% block content %}\n"
                    "  <div class='result-card'>\n"
                    "    <h1>Predicted Score</h1>\n"
                    "    <div class='score-number'>{{ score }}</div>\n"
                    "    <div class='band'>Performance: {{ band }}</div>\n"
                    "  </div>\n"
                    "\n"
                    "  <h3>You entered:</h3>\n"
                    "  <ul>\n"
                    "    {% for k, v in inputs.items() %}\n"
                    "      <li>{{ k }}: {{ v }}</li>\n"
                    "    {% endfor %}\n"
                    "  </ul>\n"
                    "\n"
                    "  <a href='/' class='back-btn'>&larr; Try another student</a>\n"
                    "{% endblock %}\n"
                ),
            },
        ],
        "explanation": (
            "Three new things: "
            "(1) Form(...) — FastAPI's way of saying 'this field comes from form data, "
            "not JSON'. The field name MUST match the input name='study_hours' in HTML. "
            "(2) TemplateResponse — renders the Jinja template with the variables you pass. "
            "Always pass 'request': request (FastAPI requirement). "
            "(3) {% extends %} + {% block %} — base.html defines a layout with holes; "
            "home.html and result.html fill those holes. Change the nav once in base.html, "
            "both pages update. That's the whole point of templates."
        ),
        "common_mistakes": [
            "Forgetting enctype — for plain text inputs, default enctype works. For file uploads, you need enctype='multipart/form-data'.",
            "Mismatched Form field name and HTML input name — Form(study_hours) MUST match name='study_hours' exactly.",
            "Not passing 'request': request to TemplateResponse — Jinja2Templates requires it since FastAPI 0.85.",
        ],
        "next_preview": (
            "Next: Stage 10 adds CSS — same templates, but now they look like a "
            "real product. We'll also add the 'cards' layout from your HTML mockup."
        ),
    },

    # ─── Stage 10 — CSS + cards layout ───────────────────────────────────
    {
        "stage": 10,
        "slug": "project-stage-10-css-cards",
        "title": "Add CSS — cards layout, hover effects",
        "summary": "One stylesheet. Cards with hover lift, colored accent, responsive form. The visual jump from 'tutorial' to 'product'.",
        "intuition": (
            "CSS is where the project goes from 'looks like a homework demo' to "
            "'looks like a real product'. 4 ideas carry 80% of the visual jump: "
            "\n"
            "  1. RESET        -> * { margin: 0; padding: 0; box-sizing: border-box; }\n"
            "  2. CARDS         -> div with border + border-radius + padding + hover transform\n"
            "  3. ACCENT COLOR  -> one brand color (e.g. #a0c000) used everywhere\n"
            "  4. FLEX / GRID   -> for layouts, never use float or tables\n"
            "\n"
            "That's it. No Tailwind, no Bootstrap. One 50-line stylesheet is enough."
        ),
        "tiny_task": (
            "Create app/static/style.css with the 4 ideas above. The result-card "
            "class should have a hover effect that lifts it 2px and adds a shadow. "
            "Reload / and see the visual jump."
        ),
        "check": (
            "After reloading, the form should be in a centered card with a "
            "border. The result page should have a big colored number for the "
            "predicted score. Hovering over a card should lift it slightly."
        ),
        "routes_box": (
            "No new routes. We add a STATIC FILE route — FastAPI serves /static/* "
            "from app/static/. Already wired up by mounting StaticFiles in main.py."
        ),
        "is_response_model_needed": "No",
        "response_model_explanation": (
            "CSS is static. The /static/style.css route returns a file directly, "
            "no Pydantic involved."
        ),
        "files": [
            {
                "name": "app/static/style.css",
                "lang": "css",
                "code": (
                    "* { margin: 5px; padding: 0; box-sizing: border-box; }\n"
                    "body {\n"
                    "  font-family: system-ui, sans-serif;\n"
                    "  background: #fafafa;\n"
                    "  color: #1a1a1a;\n"
                    "}\n"
                    "header {\n"
                    "  display: flex;\n"
                    "  justify-content: space-between;\n"
                    "  align-items: center;\n"
                    "  padding: 1rem 2rem;\n"
                    "  background: white;\n"
                    "  border-bottom: 1px solid #e5e5e5;\n"
                    "}\n"
                    "header p { color: #a0c000; font-weight: 600; }\n"
                    "nav ul { list-style: none; display: flex; gap: 1rem; }\n"
                    "nav a { color: #a0c000; text-decoration: none; }\n"
                    "main { max-width: 720px; margin: 2rem auto; padding: 0 1rem; }\n"
                    "\n"
                    "/* ─── Card ───────────────────────────────────────────── */\n"
                    ".card, .result-card {\n"
                    "  background: white;\n"
                    "  border: 1px solid #e5e5e5;\n"
                    "  border-radius: 10px;\n"
                    "  padding: 2rem;\n"
                    "  transition: all 0.2s;\n"
                    "}\n"
                    ".card:hover, .result-card:hover {\n"
                    "  transform: translateY(-2px);\n"
                    "  box-shadow: 0 10px 26px rgba(0,0,0,0.08);\n"
                    "}\n"
                    "\n"
                    "/* ─── Form ──────────────────────────────────────────── */\n"
                    "form { display: grid; gap: 1rem; }\n"
                    "label { display: flex; flex-direction: column; font-size: 0.9rem; color: #555; }\n"
                    "input {\n"
                    "  padding: 0.6rem;\n"
                    "  border: 1px solid #ddd;\n"
                    "  border-radius: 6px;\n"
                    "  font-size: 1rem;\n"
                    "}\n"
                    "input:focus { outline: 2px solid #a0c000; border-color: #a0c000; }\n"
                    "button {\n"
                    "  background: #a0c000;\n"
                    "  color: white;\n"
                    "  border: none;\n"
                    "  border-radius: 6px;\n"
                    "  padding: 0.8rem;\n"
                    "  font-size: 1rem;\n"
                    "  cursor: pointer;\n"
                    "  transition: background 0.2s;\n"
                    "}\n"
                    "button:hover { background: #8aab00; }\n"
                    "\n"
                    "/* ─── Result ────────────────────────────────────────── */\n"
                    ".score-number {\n"
                    "  font-size: 4rem;\n"
                    "  font-weight: bold;\n"
                    "  color: #a0c000;\n"
                    "  text-align: center;\n"
                    "  margin: 1rem 0;\n"
                    "}\n"
                    ".band { text-align: center; color: #555; font-size: 1.1rem; }\n"
                    ".back-btn {\n"
                    "  display: inline-block;\n"
                    "  margin-top: 1rem;\n"
                    "  color: #a0c000;\n"
                    "  text-decoration: none;\n"
                    "}\n"
                ),
            },
            {
                "name": "app/main.py (add static mount)",
                "lang": "python",
                "code": (
                    "# Add this near the top of main.py, after `app = FastAPI()`:\n"
                    "from fastapi.staticfiles import StaticFiles\n"
                    "app.mount('/static', StaticFiles(directory='app/static'), name='static')\n"
                    "\n"
                    "# Now <link rel='stylesheet' href='/static/style.css'> in base.html works."
                ),
            },
        ],
        "explanation": (
            "box-sizing: border-box is the most important CSS line — it makes "
            "padding NOT add to the element's width. Without it, a 200px card "
            "with 20px padding is actually 240px wide, which breaks layouts. "
            "transition: all 0.2s on cards is what makes the hover effect smooth "
            "instead of instant. translateY(-2px) moves the card UP 2px on hover "
            "— combined with the shadow, it looks like the card is being lifted. "
            "The accent color #a0c000 is used 6 times: header text, nav links, "
            "input focus ring, button background, score number, back link. ONE "
            "color, used consistently, is what makes a design feel intentional."
        ),
        "common_mistakes": [
            "Using float or tables for layout — always use flex/grid.",
            "Adding 5 different accent colors — pick ONE and use it everywhere.",
            "Forgetting box-sizing: border-box — layouts will be off by the padding amount and you'll go crazy debugging.",
        ],
        "next_preview": (
            "Next: Stage 11 adds a /model-info page that surfaces the training "
            "metrics + a feature-importance plot. Now the website explains ITSELF."
        ),
    },

    # ─── Stage 11 — Model info page ──────────────────────────────────────
    {
        "stage": 11,
        "slug": "project-stage-11-model-info",
        "title": "Add a /model-info page — show metrics + feature importance",
        "summary": "The model is a black box to users. Surface the R^2, MAE, and which features matter most. Trust comes from transparency.",
        "intuition": (
            "If a student gets predicted 76 and asks 'why?', you need an answer. "
            "Two answers, actually: "
            "\n"
            "  1. 'The model is off by ~4 points on average' (MAE)\n"
            "  2. 'previous_score matters most, then attendance, then study_hours' (feature importance)\n"
            "\n"
            "LinearRegression exposes coefficients (positive/negative weights per "
            "feature). RandomForest exposes feature_importances_ (0-1 share per "
            "feature). Both let you say 'which feature matters most'."
        ),
        "tiny_task": (
            "Add a /model-info route that renders a template showing: model type, "
            "training R^2, MAE, and a sorted list of feature importances. Use the "
            "saved model — don't retrain."
        ),
        "check": (
            "Visit http://localhost:8000/model-info — you should see: "
            "'Model: RandomForestRegressor | R^2: 0.83 | MAE: 4.1 points' and a "
            "list of features sorted by importance, with previous_score at the top."
        ),
        "routes_box": (
            "ROUTES INTRODUCED HERE:\n"
            "  GET /model-info  ->  renders model.html with metrics + feature importance\n"
            "\n"
            "Total project routes: 4 (/, /predict, /predict-form, /model-info). "
            "That's the whole app. No more routes needed."
        ),
        "is_response_model_needed": "No (HTML response)",
        "response_model_explanation": (
            "/model-info returns HTML, not JSON. Use response_class=HTMLResponse. "
            "If you also want a JSON version (for dashboards), add a parallel "
            "GET /api/model-info with response_model=ModelInfoResponse — but "
            "for this project, HTML is enough."
        ),
        "files": [
            {
                "name": "app/main.py (add /model-info route)",
                "lang": "python",
                "code": (
                    "# Add to app/main.py:\n"
                    "\n"
                    "@app.get('/model-info', response_class=HTMLResponse)\n"
                    "async def model_info(request: Request):\n"
                    "    # Inspect the loaded model — no retraining\n"
                    "    model_type = type(model).__name__\n"
                    "\n"
                    "    # Feature importances (RandomForest) or coefficients (LinearRegression)\n"
                    "    if hasattr(model, 'feature_importances_'):\n"
                    "        importances = list(zip(FEATURES, model.feature_importances_))\n"
                    "        importances.sort(key=lambda x: x[1], reverse=True)\n"
                    "        importance_type = 'feature_importances_'\n"
                    "    elif hasattr(model, 'coef_'):\n"
                    "        importances = list(zip(FEATURES, model.coef_))\n"
                    "        importances.sort(key=lambda x: abs(x[1]), reverse=True)\n"
                    "        importance_type = 'coefficient'\n"
                    "    else:\n"
                    "        importances = []\n"
                    "        importance_type = 'unknown'\n"
                    "\n"
                    "    # Re-compute test metrics by loading the data + splitting the same way\n"
                    "    import pandas as pd\n"
                    "    from sklearn.model_selection import train_test_split\n"
                    "    from sklearn.metrics import mean_absolute_error, r2_score\n"
                    "    df = pd.read_csv('data/students.csv').drop(columns=['student_id'])\n"
                    "    X = df.drop(columns=['final_score'])\n"
                    "    y = df['final_score']\n"
                    "    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n"
                    "    y_pred = model.predict(X_test)\n"
                    "    metrics = {\n"
                    "        'r2': round(r2_score(y_test, y_pred), 3),\n"
                    "        'mae': round(mean_absolute_error(y_test, y_pred), 2),\n"
                    "    }\n"
                    "\n"
                    "    return templates.TemplateResponse('model.html', {\n"
                    "        'request': request,\n"
                    "        'model_type': model_type,\n"
                    "        'metrics': metrics,\n"
                    "        'importances': importances,\n"
                    "        'importance_type': importance_type,\n"
                    "    })\n"
                ),
            },
            {
                "name": "app/templates/model.html",
                "lang": "html",
                "code": (
                    "{% extends 'base.html' %}\n"
                    "{% block title %}Model info{% endblock %}\n"
                    "\n"
                    "{% block content %}\n"
                    "  <div class='card'>\n"
                    "    <h1>Model Info</h1>\n"
                    "    <p><strong>Type:</strong> {{ model_type }}</p>\n"
                    "    <p><strong>R^2:</strong> {{ metrics.r2 }}  (1.0 is perfect, 0 is guessing)</p>\n"
                    "    <p><strong>MAE:</strong> {{ metrics.mae }} points  (average error)</p>\n"
                    "  </div>\n"
                    "\n"
                    "  <div class='card' style='margin-top: 1rem;'>\n"
                    "    <h2>Feature importance ({{ importance_type }})</h2>\n"
                    "    <p>Which inputs matter most to the model's prediction.</p>\n"
                    "    {% for feature, weight in importances %}\n"
                    "      <div class='imp-row'>\n"
                    "        <span class='imp-name'>{{ feature }}</span>\n"
                    "        <div class='imp-bar-bg'>\n"
                    "          <div class='imp-bar' style='width: {{ (weight * 100 if weight < 1 else weight) | round(1) }}%;'></div>\n"
                    "        </div>\n"
                    "        <span class='imp-val'>{{ weight | round(3) }}</span>\n"
                    "      </div>\n"
                    "    {% endfor %}\n"
                    "  </div>\n"
                    "{% endblock %}\n"
                ),
            },
            {
                "name": "app/static/style.css (add to bottom)",
                "lang": "css",
                "code": (
                    "/* Feature importance bars */\n"
                    ".imp-row { display: flex; align-items: center; gap: 0.5rem; margin: 0.4rem 0; }\n"
                    ".imp-name { width: 200px; font-family: monospace; font-size: 0.9rem; }\n"
                    ".imp-bar-bg { flex: 1; height: 18px; background: #eee; border-radius: 9px; overflow: hidden; }\n"
                    ".imp-bar { height: 100%; background: #a0c000; transition: width 0.3s; }\n"
                    ".imp-val { width: 60px; text-align: right; font-family: monospace; font-size: 0.85rem; color: #555; }\n"
                ),
            },
        ],
        "explanation": (
            "hasattr(model, 'feature_importances_') is the trick — RandomForest "
            "and most tree-based models expose feature_importances_ (a 0-1 array "
            "summing to 1, where bigger = more important). LinearRegression "
            "exposes coef_ instead (signed weights — positive means more of that "
            "feature INCREASES the prediction, negative means DECREASES). The "
            "same /model-info route handles both cases by checking which "
            "attribute exists. This is duck typing — we don't care WHAT the model "
            "is, we care what it CAN DO."
        ),
        "common_mistakes": [
            "Retraining the model on every /model-info request — load once at startup, just read its attributes here.",
            "Showing coefficients without absolute value — a -5 coefficient is MORE important than a +1, but sorting by raw value puts it last.",
            "Comparing RandomForest importances with LinearRegression coefficients directly — they're on different scales. Compare within one model type.",
        ],
        "next_preview": (
            "Final: Stage 12 wraps up — folder structure recap, how to run it, "
            "how to deploy to Render, and what to learn next."
        ),
    },

    # ─── Stage 12 — Wrap up + deploy ─────────────────────────────────────
    {
        "stage": 12,
        "slug": "project-stage-12-deploy",
        "title": "Wrap up — folder structure, deploy, what's next",
        "summary": "Recap the 12 stages, see the final folder tree, deploy to Render in 5 minutes, and choose what to learn next.",
        "intuition": (
            "You now have a complete project: Python trains the model, ML makes "
            "predictions, FastAPI serves them, Jinja renders the pages, HTML/CSS "
            "makes them look like a product. 12 stages, 4 routes, 8 files, 1 "
            "deployed website. "
            "\n\n"
            "The architecture is FORCED — every layer exists because the previous "
            "one couldn't do the job. That's the test of a good architecture: "
            "remove any layer and the project breaks."
        ),
        "tiny_task": (
            "Deploy to Render. Push to GitHub, create a Render web service, set "
            "build command 'pip install -r requirements.txt' and start command "
            "'uvicorn app.main:app --host 0.0.0.0 --port $PORT'. Done."
        ),
        "check": (
            "Visit your Render URL — the form should load, submit should give a "
            "prediction, /model-info should show metrics. That's a deployed ML "
            "product, built from scratch."
        ),
        "routes_box": (
            "FINAL ROUTES (recap):\n"
            "  GET  /              ->  form page (home.html)\n"
            "  POST /predict       ->  JSON API (for scripts)\n"
            "  POST /predict-form  ->  form submission (renders result.html)\n"
            "  GET  /model-info    ->  model metrics + feature importance\n"
            "\n"
            "4 routes. That's the entire web app. Every other URL (static files, "
            "/docs) is auto-served by FastAPI."
        ),
        "is_response_model_needed": "Only for /predict",
        "response_model_explanation": (
            "FINAL ANSWER on response models: "
            "\n"
            "  POST /predict       ->  YES, response_model=PredictResponse\n"
            "  POST /predict-form  ->  NO, returns HTML (response_class=HTMLResponse)\n"
            "  GET  /              ->  NO, returns HTML\n"
            "  GET  /model-info    ->  NO, returns HTML\n"
            "\n"
            "Rule of thumb: if a route returns JSON, declare a response_model. "
            "If it returns HTML, use response_class=HTMLResponse. If it returns "
            "a file, use FileResponse. Never mix — the client expects ONE "
            "content type per route."
        ),
        "files": [
            {
                "name": "final-folder-structure.txt",
                "lang": "text",
                "code": (
                    "student_predictor/\n"
                    "  app/\n"
                    "    main.py              # FastAPI app + 4 routes\n"
                    "    ml/\n"
                    "      train.py           # trains model.pkl (Stage 4)\n"
                    "      evaluate.py        # computes metrics (Stage 5)\n"
                    "      error_analysis.py  # finds worst predictions (Stage 6)\n"
                    "      compare_models.py  # Linear vs RF (Stage 7)\n"
                    "      model.pkl          # the saved winner\n"
                    "    templates/\n"
                    "      base.html          # shared shell (Stage 9)\n"
                    "      home.html          # the form (Stage 9)\n"
                    "      result.html        # the prediction (Stage 9)\n"
                    "      model.html         # /model-info page (Stage 11)\n"
                    "    static/\n"
                    "      style.css          # one stylesheet (Stage 10)\n"
                    "  data/\n"
                    "    students.csv         # the dataset (Stage 1)\n"
                    "  requirements.txt\n"
                    "  run.sh\n"
                    "  render.yaml           # Render deploy config\n"
                    "\n"
                    "14 files total. ~600 lines of code."
                ),
            },
            {
                "name": "requirements.txt",
                "lang": "text",
                "code": (
                    "fastapi==0.115.0\n"
                    "uvicorn[standard]==0.30.0\n"
                    "jinja2==3.1.4\n"
                    "pandas==2.2.2\n"
                    "scikit-learn==1.5.1\n"
                    "joblib==1.4.2\n"
                    "python-multipart==0.0.9\n"
                ),
            },
            {
                "name": "render.yaml",
                "lang": "yaml",
                "code": (
                    "services:\n"
                    "  - type: web\n"
                    "    name: student-performance-predictor\n"
                    "    runtime: python\n"
                    "    plan: free\n"
                    "    buildCommand: pip install -r requirements.txt\n"
                    "    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT\n"
                    "    healthCheckPath: /docs\n"
                    "    autoDeploy: true\n"
                ),
            },
            {
                "name": "run.sh",
                "lang": "bash",
                "code": (
                    "#!/bin/bash\n"
                    "# One-time setup\n"
                    "pip install -r requirements.txt\n"
                    "python app/ml/train.py        # produces app/ml/model.pkl\n"
                    "\n"
                    "# Every time you want to run\n"
                    "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload\n"
                    "\n"
                    "# Open http://localhost:8000 in your browser\n"
                ),
            },
        ],
        "explanation": (
            "The folder structure splits 'training time' (app/ml/) from 'serving "
            "time' (app/main.py + app/templates/ + app/static/). train.py runs "
            "offline, writes model.pkl, exits. main.py loads model.pkl once and "
            "serves predictions forever. That split is what makes deployment "
            "trivial — Render only needs to install requirements.txt and run "
            "uvicorn; the model is already trained and bundled. "
            "\n\n"
            "WHAT TO LEARN NEXT: "
            "(1) Add user accounts (Stage 3 of OpenBenchML's build course covers "
            "this — SQLite + JWT). "
            "(2) Add a database to save predictions per user. "
            "(3) Add a /notebook so users can experiment with the model. "
            "(4) Add a leaderboard for who can train the best model. "
            "(5) Add WebSocket live updates when a new model is uploaded. "
            "\n"
            "That's literally the path from 'student predictor' to 'OpenBenchML'. "
            "You just walked it backwards."
        ),
        "common_mistakes": [
            "Committing model.pkl to git — it's a binary, can be 100MB+. Use git-lfs or train on deploy.",
            "Using `--reload` in production — it watches files and restarts on every change, kills throughput.",
            "Not setting host='0.0.0.0' in production — Render won't be able to reach your app on 127.0.0.1.",
        ],
        "next_preview": (
            "You're done. The next project is YOURS — pick a dataset, run the "
            "same 12 stages, ship it. Or jump into OpenBenchML's Build Course "
            "to learn how to add auth, database, WebSocket, and the notebook "
            "kernel to this same app."
        ),
    },
]


# Flatten for slug lookup
_PROJECT_FLAT = {stage["slug"]: stage for stage in PROJECT_COURSE}


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/learn/project", response_class=HTMLResponse)
async def learn_project_overview(request: Request):
    """Render the project course overview — all 12 stages as a path."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    return templates.TemplateResponse("learn_project.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "view": "overview",
        "course": PROJECT_COURSE,
    })


@router.get("/learn/project/{slug}", response_class=HTMLResponse)
async def learn_project_stage(request: Request, slug: str):
    """Render a single stage page."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    stage = _PROJECT_FLAT.get(slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    # Find prev/next
    idx = next((i for i, s in enumerate(PROJECT_COURSE) if s["slug"] == slug), -1)
    prev_stage = PROJECT_COURSE[idx - 1] if idx > 0 else None
    next_stage = PROJECT_COURSE[idx + 1] if idx < len(PROJECT_COURSE) - 1 else None

    return templates.TemplateResponse("learn_project.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "view": "stage",
        "stage": stage,
        "prev_stage": prev_stage,
        "next_stage": next_stage,
        "total_stages": len(PROJECT_COURSE),
    })
