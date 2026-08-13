"""
OpenBenchML — Real-World Dataset Downloader
============================================
Downloads well-known, public-domain ML datasets from GitHub raw URLs
and the UCI ML repository. Saves each as a CSV in /home/z/my-project/datasets/
with a companion JSON sidecar describing columns, target, and task type.

All sources are:
  - Public domain or CC-BY / CC0
  - Hosted on raw.githubusercontent.com or archive.ics.uci.edu
  - Small enough to fit in 512 MB RAM (Render free tier)
  - Real-world (not synthetic)

Run:  python /home/z/my-project/scripts/download_real_datasets.py
"""

import csv
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────────────

DATASETS_DIR = Path("/home/z/my-project/datasets")
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# Each entry: slug, url, target_col, task_type, title, description,
#             difficulty, drop_cols (columns to drop before feature matrix),
#             categorical_encode (True = one-hot encode categoricals)
DATASETS = [
    # ── Classification: binary ────────────────────────────────────────────
    {
        "slug": "titanic",
        "url": "https://raw.githubusercontent.com/datasciencedojo/datasets/master/titanic.csv",
        "target_col": "Survived",
        "task_type": "classification",
        "title": "Titanic Survival",
        "description": "Real passenger data from the RMS Titanic disaster. 891 passengers "
                       "with features including class, sex, age, siblings/spouses aboard, "
                       "parents/children aboard, fare paid, and embarkation port. The goal "
                       "is to predict survival (0 = died, 1 = survived). A classic Kaggle "
                       "starter dataset with mixed numeric and categorical features and "
                       "missing values — a realistic ML benchmark.",
        "difficulty": "beginner",
        "drop_cols": ["PassengerId", "Name", "Ticket", "Cabin"],
        "categorical_encode": True,
    },
    {
        "slug": "pima_diabetes",
        "url": "https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv",
        "target_col": "8",  # last column, no header
        "task_type": "classification",
        "title": "Pima Indians Diabetes",
        "description": "Real clinical data from the Pima Indians of Arizona, a population "
                       "with one of the highest rates of type-2 diabetes in the world. 768 "
                       "female patients, 8 features including plasma glucose concentration, "
                       "blood pressure, triceps skinfold thickness, insulin, BMI, diabetes "
                       "pedigree function, and age. Binary target: diabetes onset within 5 "
                       "years. Originally from the National Institute of Diabetes and "
                       "Digestive and Kidney Diseases.",
        "difficulty": "intermediate",
        "header": False,
        "column_names": ["Pregnancies", "Glucose", "BloodPressure", "SkinThickness",
                         "Insulin", "BMI", "DiabetesPedigree", "Age", "Outcome"],
        "drop_cols": [],
        "categorical_encode": False,
    },
    {
        "slug": "heart_disease",
        "url": "https://raw.githubusercontent.com/dphi-official/Datasets/master/heart_disease.csv",
        "target_col": "target",
        "task_type": "classification",
        "title": "Heart Disease (Cleveland)",
        "description": "Real clinical data from the Cleveland Clinic Foundation, originally "
                       "from the UCI ML repository. 303 patients with 13 features including "
                       "age, sex, chest pain type, resting blood pressure, cholesterol, "
                       "fasting blood sugar, ECG results, max heart rate, exercise-induced "
                       "angina, ST depression, slope, number of major vessels, and thal. "
                       "Binary target: presence of heart disease.",
        "difficulty": "intermediate",
        "drop_cols": [],
        "categorical_encode": True,
        "strip_bom": True,
    },
    {
        "slug": "sonar_mines_vs_rocks",
        "url": "https://raw.githubusercontent.com/jbrownlee/Datasets/master/sonar.csv",
        "target_col": "60",
        "task_type": "classification",
        "title": "Sonar: Mines vs Rocks",
        "description": "Real sonar signal data from the UCI ML repository. 208 patterns "
                       "obtained by bouncing sonar signals off metal cylinders (mines) and "
                       "rocks at various angles and under various conditions. 60 numeric "
                       "features in the range 0.0–1.0 represent energy in a particular "
                       "frequency band. Binary target: mine vs rock. A classic benchmark "
                       "for pattern classification.",
        "difficulty": "intermediate",
        "header": True,
        "drop_cols": [],
        "categorical_encode": False,
        "target_map": {"M": 1, "R": 0, "m": 1, "r": 0},
    },
    {
        "slug": "banknote_authentication",
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/00267/data_banknote_authentication.txt",
        "target_col": "4",
        "task_type": "classification",
        "title": "Banknote Authentication",
        "description": "Real data from the UCI ML repository. 1372 banknote images were "
                       "wavelet-transformed to extract 4 features: variance, skewness, "
                       "curtosis, and entropy of the image. Binary target: genuine vs "
                       "forged. A clean, easy-to-classify dataset — perfect for verifying "
                       "that a model framework's predict() pipeline is wired correctly.",
        "difficulty": "beginner",
        "header": False,
        "column_names": ["Variance", "Skewness", "Curtosis", "Entropy", "Class"],
        "drop_cols": [],
        "categorical_encode": False,
    },

    # ── Classification: multi-class ───────────────────────────────────────
    {
        "slug": "wine_quality_red",
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv",
        "target_col": "quality",
        "task_type": "classification",
        "title": "Wine Quality (Red)",
        "description": "Real physicochemical data from the UCI ML repository. 1599 red "
                       "Vinho Verde wines from northern Portugal, 11 features including "
                       "fixed acidity, volatile acidity, citric acid, residual sugar, "
                       "chlorides, free SO2, total SO2, density, pH, sulphates, alcohol. "
                       "Target: quality score 0–10 (sensory panel median). Treated as a "
                       "multi-class classification problem (3–8 in practice).",
        "difficulty": "intermediate",
        "header": True,
        "delimiter": ";",
        "drop_cols": [],
        "categorical_encode": False,
    },
    {
        "slug": "wine_quality_white",
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-white.csv",
        "target_col": "quality",
        "task_type": "classification",
        "title": "Wine Quality (White)",
        "description": "Real physicochemical data from the UCI ML repository. 4898 white "
                       "Vinho Verde wines from northern Portugal, same 11 features as the "
                       "red wine dataset. Target: quality score 0–10. Larger and slightly "
                       "more imbalanced than the red variant — a tougher multi-class "
                       "benchmark.",
        "difficulty": "advanced",
        "header": True,
        "delimiter": ";",
        "drop_cols": [],
        "categorical_encode": False,
    },
    {
        "slug": "iris_csv",
        "url": "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/iris.csv",
        "target_col": "species",
        "task_type": "classification",
        "title": "Iris (real CSV)",
        "description": "The classic Iris dataset — but loaded from the real CSV used by "
                       "seaborn (not the sklearn Bunch). 150 samples, 4 features (sepal "
                       "length, sepal width, petal length, petal width). Target: 3 species "
                       "(setosa, versicolor, virginica). Useful as a sanity check that the "
                       "CSV-loading pipeline produces identical numbers to sklearn's "
                       "built-in version.",
        "difficulty": "beginner",
        "drop_cols": [],
        "categorical_encode": False,
    },
    {
        "slug": "penguins",
        "url": "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv",
        "target_col": "species",
        "task_type": "classification",
        "title": "Palmer Penguins",
        "description": "Real data collected at Palmer Station, Antarctica by Dr. Kristen "
                       "Gorman. 344 penguins from 3 islands in the Palmer Archipelago, "
                       "with features including bill length, bill depth, flipper length, "
                       "body mass, sex, and island. Target: 3 species (Adelie, Chinstrap, "
                       "Gentoo). A modern alternative to Iris with mixed numeric and "
                       "categorical features and some missing values.",
        "difficulty": "beginner",
        "drop_cols": [],
        "categorical_encode": True,
    },

    # ── Regression ─────────────────────────────────────────────────────────
    {
        "slug": "auto_mpg",
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/auto-mpg/auto-mpg.data",
        "target_col": "mpg",
        "task_type": "regression",
        "title": "Auto MPG",
        "description": "Real data from the UCI ML repository. 398 cars from the 1970s and "
                       "1980s, 8 features including cylinders, displacement, horsepower, "
                       "weight, acceleration, model year, and origin. Target: miles-per-"
                       "gallon fuel efficiency. Contains some missing values marked as '?'.",
        "difficulty": "intermediate",
        "header": False,
        "delimiter": None,  # whitespace
        "column_names": ["mpg", "cylinders", "displacement", "horsepower", "weight",
                         "acceleration", "model_year", "origin", "car_name"],
        "drop_cols": ["car_name"],
        "categorical_encode": False,
        "na_values": ["?"],
    },
    {
        "slug": "boston_housing",
        "url": "https://raw.githubusercontent.com/selva86/datasets/master/BostonHousing.csv",
        "target_col": "medv",
        "task_type": "regression",
        "title": "Boston Housing",
        "description": "Real data from the classic Harrison & Rubinfeld (1978) study of "
                       "Boston house prices. 506 suburbs, 13 features including crime rate, "
                       "residential land zoning, industrial proportion, nitric oxides "
                       "concentration, average rooms, age of housing, distance to employment "
                       "centres, accessibility to radial highways, property tax rate, "
                       "pupil-teacher ratio, proportion of Black residents, lower-status "
                       "population proportion. Target: median home value in $1000s. The "
                       "original sklearn dataset — preserved here as a real CSV.",
        "difficulty": "intermediate",
        "drop_cols": [],
        "categorical_encode": True,
    },
    {
        "slug": "concrete_strength",
        "url": "https://archive.ics.uci.edu/ml/machine-learning-databases/concrete/compressive/Concrete_Data.xls",
        "target_col": None,  # set after we see the data — but this is .xls, skip if pandas missing
        "task_type": "regression",
        "title": "Concrete Compressive Strength",
        "description": "Real data from the UCI ML repository (Yeh, 1998). 1030 concrete "
                       "samples, 8 features including cement, blast furnace slag, fly ash, "
                       "water, superplasticizer, coarse aggregate, fine aggregate, age. "
                       "Target: concrete compressive strength in MPa. A real materials-"
                       "science regression benchmark.",
        "difficulty": "advanced",
        "skip": True,  # .xls format — handle separately or skip
    },
    {
        "slug": "real_estate",
        "url": "https://raw.githubusercontent.com/ageron/handson-ml2/master/datasets/housing/housing.csv",
        "target_col": "median_house_value",
        "task_type": "regression",
        "title": "California Housing (real CSV)",
        "description": "Real California census data from the 1990 California Housing dataset "
                       "(Pace & Barry, 1997). 20640 suburbs, 9 features including median "
                       "income, housing median age, total rooms, total bedrooms, population, "
                       "households, latitude, longitude, and ocean proximity. Target: median "
                       "house value. The same dataset sklearn fetches — but here as a real "
                       "CSV so the benchmark path is fully transparent.",
        "difficulty": "advanced",
        "drop_cols": [],
        "categorical_encode": True,
    },
]


# ─── Downloader ───────────────────────────────────────────────────────────────

USER_AGENT = "Mozilla/5.0 (OpenBenchML dataset downloader)"


def fetch(url: str, retries: int = 3, timeout: int = 30) -> str:
    """Fetch a URL with retries; raise on final failure."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_exc = exc
            print(f"  attempt {attempt}/{retries} failed: {exc}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_exc}")


def save_raw_and_sidecar(spec: dict, raw_text: str) -> Path:
    """Save raw CSV text and a JSON sidecar with metadata."""
    slug = spec["slug"]
    csv_path = DATASETS_DIR / f"{slug}.csv"
    sidecar_path = DATASETS_DIR / f"{slug}.meta.json"

    csv_path.write_text(raw_text, encoding="utf-8")

    sidecar = {
        "slug": slug,
        "title": spec["title"],
        "description": spec["description"],
        "task_type": spec["task_type"],
        "difficulty": spec.get("difficulty", "intermediate"),
        "target_col": spec["target_col"],
        "drop_cols": spec.get("drop_cols", []),
        "categorical_encode": spec.get("categorical_encode", False),
        "header": spec.get("header", True),
        "delimiter": spec.get("delimiter", ","),
        "column_names": spec.get("column_names"),
        "target_map": spec.get("target_map"),
        "na_values": spec.get("na_values", []),
        "source_url": spec["url"],
        "strip_bom": spec.get("strip_bom", False),
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    return csv_path


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"OpenBenchML real-world dataset downloader")
    print(f"  target dir: {DATASETS_DIR}")
    print(f"  datasets: {len(DATASETS)}")
    print()

    ok = 0
    failed = []

    for spec in DATASETS:
        if spec.get("skip"):
            print(f"[SKIP] {spec['slug']}: {spec.get('title', '')} (marked skip=True)")
            continue

        slug = spec["slug"]
        url = spec["url"]
        print(f"[FETCH] {slug} <- {url}")

        try:
            raw = fetch(url)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            failed.append((slug, str(exc)))
            continue

        n_lines = raw.count("\n") + (0 if raw.endswith("\n") else 1)
        path = save_raw_and_sidecar(spec, raw)
        size_kb = path.stat().st_size / 1024.0
        print(f"  saved {path.name}  ({n_lines} lines, {size_kb:.1f} KB)")
        ok += 1

    print()
    print(f"Done. {ok} downloaded, {len(failed)} failed.")
    if failed:
        print("Failed:")
        for slug, err in failed:
            print(f"  - {slug}: {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
