"""
MCP Tool Registry — defines all tools the AI agent can use.

Inspired by Entropy's coding-tools.ts but built from scratch in Python.
Each tool has: name, description, parameters (JSON Schema), and an executor.

TOOLS:
  1. write_cell       — write Python code into a notebook cell
  2. run_cell          — execute Python code, return stdout/stderr/figures
  3. read_output       — read the last cell's output
  4. list_datasets     — list all 20 datasets in the registry
  5. load_dataset      — load a dataset, return shape/columns/head/describe
  6. train_model       — train RF/LR/LogReg/SVM/KNN with full evaluation
  7. plot_data         — generate histogram/correlation/scatter/box plots
  8. do_eda            — full EDA: shape, dtypes, nulls, describe, correlations
  9. fix_error         — analyze an error and return corrected code
  10. explain_concept  — explain an ML concept with code examples
  11. compare_models   — train multiple models, compare side by side
  12. get_variables    — list variables in the notebook namespace
"""

from __future__ import annotations

import os
import json
from typing import Any, Callable, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════
#  Tool type
# ═══════════════════════════════════════════════════════════════════════════

class Tool:
    """An MCP tool definition + executor."""
    def __init__(self, name: str, description: str, parameters: dict,
                 executor: Callable[[dict], dict]):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.executor = executor

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def execute(self, args: dict) -> dict:
        try:
            return self.executor(args)
        except Exception as e:
            return {"ok": False, "error": f"Tool '{self.name}' failed: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
#  Registry path helper
# ═══════════════════════════════════════════════════════════════════════════

def _registry_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "static", "datasets", "registry")


def _list_datasets() -> List[str]:
    path = _registry_path()
    if not os.path.exists(path):
        return []
    return sorted([f.replace(".csv", "") for f in os.listdir(path) if f.endswith(".csv")])


def _detect_target(dataset: str) -> str:
    targets = {
        "iris": "species", "titanic": "survived", "wine": "class",
        "boston_housing": "medv", "breast_cancer": "malignant",
        "california_housing": "median_house_value", "pima_diabetes": "outcome",
        "heart_disease": "target", "auto_mpg": "mpg",
        "banknote_authentication": "class", "wine_quality_red": "quality",
        "wine_quality_white": "quality", "penguins": "species",
        "abalone": "rings", "insurance": "charges", "spam_email": "is_spam",
        "wine_recognition": "class", "electric_cars": "range_km",
        "student_grades": "final_grade", "credit_card_fraud": "is_fraud",
        "concrete_strength": "compressive_strength",
    }
    return targets.get(dataset, "target")


# ═══════════════════════════════════════════════════════════════════════════
#  Tool Executors
# ═══════════════════════════════════════════════════════════════════════════

def _tool_list_datasets(args: dict) -> dict:
    datasets = _list_datasets()
    return {"ok": True, "datasets": datasets, "count": len(datasets),
            "message": f"{len(datasets)} datasets available: {', '.join(datasets[:10])}{'...' if len(datasets) > 10 else ''}"}


def _tool_load_dataset(args: dict) -> dict:
    name = args.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "Dataset name required"}
    path = os.path.join(_registry_path(), f"{name}.csv")
    if not os.path.exists(path):
        return {"ok": False, "error": f"'{name}' not found. Available: {', '.join(_list_datasets()[:15])}"}
    code = f"""import pandas as pd
df = pd.read_csv('{path}')
print(f'Dataset: {name}')
print(f'Shape: {{df.shape}}')
print(f'Columns: {{list(df.columns)}}')
print(f'\\nDtypes:\\n{{df.dtypes}}')
print(f'\\nFirst 5 rows:\\n{{df.head()}}')
print(f'\\nStatistics:\\n{{df.describe()}}')
print(f'\\nMissing values:\\n{{df.isnull().sum()}}')"""
    return {"ok": True, "code": code, "action": "write_and_run",
            "explanation": f"Loaded {name} with full EDA (shape, columns, dtypes, head, describe, missing values)."}


def _tool_do_eda(args: dict) -> dict:
    dataset = args.get("dataset", "iris")
    code = f"""# ── Full EDA on {dataset} ──────────────────────────────────
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')

# 1. Basic info
print(f'{"="*60}')
print(f'DATASET: {dataset}')
print(f'{"="*60}')
print(f'Shape: {{df.shape}} ({{df.shape[0]}} rows × {{df.shape[1]}} columns)')
print(f'Memory: {{df.memory_usage(deep=True).sum() / 1024:.1f}} KB')

# 2. Column types
print(f'\\nColumn types:')
print(df.dtypes.value_counts())

# 3. Missing values
nulls = df.isnull().sum()
if nulls.sum() > 0:
    print(f'\\n⚠ Missing values:')
    print(nulls[nulls > 0])
else:
    print(f'\\n✓ No missing values')

# 4. Numeric statistics
print(f'\\nNumeric statistics:')
print(df.describe().round(2))

# 5. Categorical statistics
cat_cols = df.select_dtypes(include=['object']).columns
if len(cat_cols) > 0:
    print(f'\\nCategorical columns:')
    for col in cat_cols:
        print(f'  {{col}}: {{df[col].nunique()}} unique — {{list(df[col].unique()[:5])}}')

# 6. Correlations
numeric = df.select_dtypes(include=[np.number])
if len(numeric.columns) > 1:
    print(f'\\nTop correlations:')
    corr = numeric.corr().abs().unstack().sort_values(ascending=False)
    corr = corr[corr < 1.0].head(10)
    for (a, b), v in corr.items():
        print(f'  {{a}} ↔ {{b}}: {{v:.3f}}')

# 7. Distribution plots
fig, axes = plt.subplots(2, max(1, min(len(numeric.columns), 4)), figsize=(14, 8))
axes = axes.flatten() if len(numeric.columns) > 1 else [axes]
for i, col in enumerate(numeric.columns[:8]):
    if i < len(axes):
        df[col].hist(ax=axes[i], bins=20, color='#71c84b', edgecolor='white', alpha=0.8)
        axes[i].set_title(col, fontsize=10)
for i in range(len(numeric.columns), len(axes)):
    axes[i].set_visible(False)
plt.suptitle('{dataset} — Distributions', fontsize=13)
plt.tight_layout()
print(f'\\n✓ EDA complete. Histograms generated.')"""
    return {"ok": True, "code": code, "action": "write_and_run",
            "explanation": f"Full EDA on {dataset}: shape, types, missing values, statistics, correlations, and distribution plots."}


def _tool_train_model(args: dict) -> dict:
    algorithm = args.get("algorithm", "random_forest").lower()
    dataset = args.get("dataset", "iris").lower()
    target = args.get("target", "") or _detect_target(dataset)

    code_map = {
        "random_forest": _code_rf(dataset, target),
        "linear_regression": _code_lr(dataset, target),
        "logistic_regression": _code_logreg(dataset, target),
        "svm": _code_svm(dataset, target),
        "knn": _code_knn(dataset, target),
    }

    if algorithm not in code_map:
        return {"ok": False, "error": f"Unknown: {algorithm}. Available: {', '.join(code_map.keys())}"}

    return {"ok": True, "code": code_map[algorithm], "action": "write_and_run",
            "explanation": f"Training {algorithm} on {dataset} (target: {target})."}


def _tool_compare_models(args: dict) -> dict:
    dataset = args.get("dataset", "iris")
    target = args.get("target", "") or _detect_target(dataset)
    code = f"""# ── Compare 5 models on {dataset} ─────────────────────────
import pandas as pd
import numpy as np
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import accuracy_score

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

X = df.drop(columns=['{target}'])
y = df['{target}']
is_cls = y.nunique() <= 20

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y if is_cls else None)
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

models = {{
    'RandomForest': RandomForestClassifier(n_estimators=100, random_state=42) if is_cls else None,
    'LogisticReg': LogisticRegression(max_iter=2000, random_state=42) if is_cls else None,
    'SVM': SVC(kernel='rbf', random_state=42) if is_cls else None,
    'KNN': KNeighborsClassifier(n_neighbors=5) if is_cls else None,
    'GradBoost': GradientBoostingClassifier(n_estimators=50, random_state=42) if is_cls else None,
}}

print(f'{"="*50}')
print(f'MODEL COMPARISON on {dataset} (target: {target})')
print(f'{"="*50}')
print(f'{{"Model":<18}} {{"Accuracy":>10}} {{"CV_mean":>10}} {{"CV_std":>8}}')
print(f'{"-"*50}')

results = []
for name, model in models.items():
    if model is None:
        continue
    model.fit(X_train_s, y_train)
    y_pred = model.predict(X_test_s)
    acc = accuracy_score(y_test, y_pred)
    cv = cross_val_score(model, scaler.transform(X), y, cv=5)
    print(f'{{name:<18}} {{acc:>10.4f}} {{cv.mean():>10.4f}} {{cv.std():>8.4f}}')
    results.append({{'model': name, 'accuracy': acc, 'cv_mean': cv.mean(), 'cv_std': cv.std()}})

best = max(results, key=lambda r: r['accuracy'])
print(f'\\n🏆 Best: {{best["model"]}} ({{best["accuracy"]*100:.1f}}%)')
"""
    return {"ok": True, "code": code, "action": "write_and_run",
            "explanation": f"Comparing 5 models on {dataset}. Shows accuracy + CV for each, picks the winner."}


def _tool_plot_data(args: dict) -> dict:
    dataset = args.get("dataset", "iris")
    plot_type = args.get("plot_type", "histogram")

    plots = {
        "histogram": _plot_hist(dataset),
        "correlation": _plot_corr(dataset),
        "scatter": _plot_scatter(dataset),
        "box": _plot_box(dataset),
    }
    if plot_type not in plots:
        return {"ok": False, "error": f"Unknown plot: {plot_type}. Available: {', '.join(plots.keys())}"}
    return {"ok": True, "code": plots[plot_type], "action": "write_and_run",
            "explanation": f"Generated {plot_type} plot for {dataset}."}


def _tool_fix_error(args: dict) -> dict:
    code = args.get("code", "")
    error = args.get("error", "")
    fixed = _analyze_error(code, error)
    return {"ok": True, "code": fixed, "action": "write_and_run",
            "explanation": "Fixed the error based on analysis."}


def _tool_explain_concept(args: dict) -> dict:
    concept = args.get("concept", "").lower()
    explanations = {
        "random forest": "Random Forest builds many decision trees (100 by default) and averages their predictions. Each tree sees a random subset of rows (bootstrap) and a random subset of features at each split. This randomness prevents overfitting. Final prediction = majority vote (classification) or average (regression).",
        "overfitting": "Overfitting = model memorizes training data but fails on new data. Symptom: train accuracy 99%, test accuracy 60%. Fix: simpler model, more data, regularization (L1/L2), cross-validation, early stopping.",
        "cross-validation": "Cross-validation splits data into K folds (usually 5), trains on K-1 folds, tests on 1. Repeats K times. The average score is a more honest estimate than a single train/test split. Use cross_val_score(model, X, y, cv=5).",
        "gradient descent": "Gradient descent finds the minimum of a function by taking steps in the -gradient direction. Learning rate controls step size. Too large = diverge. Too small = slow. Adam optimizer adapts the learning rate per parameter.",
        "pca": "PCA finds the directions (principal components) of maximum variance in the data. It reduces dimensions (e.g. 64D to 2D) while keeping as much variance as possible. Always scale features first. Use it for visualization and dimensionality reduction.",
    }
    for key, exp in explanations.items():
        if key in concept:
            return {"ok": True, "code": "", "explanation": f"**{key.title()}**\n\n{exp}",
                    "action": "explain", "cell_type": "text"}
    return {"ok": True, "code": "", "explanation": f"I can explain: random forest, overfitting, cross-validation, gradient descent, PCA.\n\nAsk: 'explain random forest'",
            "action": "explain", "cell_type": "text"}


# ═══════════════════════════════════════════════════════════════════════════
#  Code generators
# ═══════════════════════════════════════════════════════════════════════════

def _code_rf(dataset, target):
    return f"""# ── Random Forest on {dataset} ──────────────────────────
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, mean_absolute_error, r2_score
from sklearn.preprocessing import LabelEncoder

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
print(f'Shape: {{df.shape}} | Columns: {{list(df.columns)}}')

for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

X = df.drop(columns=['{target}'])
y = df['{target}']
is_cls = y.nunique() <= 20

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y if is_cls else None)

model = (RandomForestClassifier if is_cls else RandomForestRegressor)(n_estimators=100, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

if is_cls:
    acc = accuracy_score(y_test, y_pred)
    cv = cross_val_score(model, X, y, cv=5)
    print(f'\\nAccuracy: {{acc:.4f}} ({{acc*100:.1f}}%)')
    print(f'CV: {{cv.mean():.4f}} ± {{cv.std():.4f}}')
    print(f'\\n{{classification_report(y_test, y_pred)}}')
else:
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    cv = cross_val_score(model, X, y, cv=5, scoring='r2')
    print(f'\\nMAE: {{mae:.4f}} | R²: {{r2:.4f}}')
    print(f'CV R²: {{cv.mean():.4f}} ± {{cv.std():.4f}}')

importance = pd.DataFrame({{'feature': X.columns, 'importance': model.feature_importances_}}).sort_values('importance', ascending=False)
print(f'\\nFeature Importance:')
print(importance.head().to_string(index=False))"""


def _code_lr(dataset, target):
    return f"""# ── Linear Regression on {dataset} ──────────────────────
import pandas as pd, numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, LabelEncoder

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

X = df.drop(columns=['{target}'])
y = df['{target}']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

lr = LinearRegression()
lr.fit(X_train_s, y_train)
y_pred = lr.predict(X_test_s)

mae = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2 = r2_score(y_test, y_pred)
cv = cross_val_score(lr, scaler.transform(X), y, cv=5, scoring='r2')

print(f'MAE:  {{mae:.4f}}')
print(f'RMSE: {{rmse:.4f}}')
print(f'R²:   {{r2:.4f}} ({{r2*100:.1f}}%)')
print(f'CV R²: {{cv.mean():.4f}} ± {{cv.std():.4f}}')

coefs = pd.DataFrame({{'feature': X.columns, 'coef': lr.coef_}}).sort_values('coef', key=abs, ascending=False)
print(f'\\nCoefficients:')
print(coefs.head().to_string(index=False))"""


def _code_logreg(dataset, target):
    return f"""# ── Logistic Regression on {dataset} ────────────────────
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler, LabelEncoder

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

X = df.drop(columns=['{target}'])
y = df['{target}']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

model = LogisticRegression(max_iter=2000, random_state=42)
model.fit(X_train_s, y_train)
y_pred = model.predict(X_test_s)

acc = accuracy_score(y_test, y_pred)
cv = cross_val_score(model, scaler.transform(X), y, cv=5)
print(f'Accuracy: {{acc:.4f}} ({{acc*100:.1f}}%)')
print(f'CV: {{cv.mean():.4f}} ± {{cv.std():.4f}}')
print(f'\\n{{classification_report(y_test, y_pred)}}')
print(f'Confusion Matrix:\\n{{confusion_matrix(y_test, y_pred)}}')"""


def _code_svm(dataset, target):
    return f"""# ── SVM on {dataset} ────────────────────────────────────
import pandas as pd
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler, LabelEncoder

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

X = df.drop(columns=['{target}'])
y = df['{target}']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

model = SVC(kernel='rbf', C=1.0, random_state=42)
model.fit(X_train_s, y_train)
y_pred = model.predict(X_test_s)

acc = accuracy_score(y_test, y_pred)
cv = cross_val_score(model, scaler.transform(X), y, cv=5)
print(f'SVM Accuracy: {{acc:.4f}} ({{acc*100:.1f}}%)')
print(f'CV: {{cv.mean():.4f}} ± {{cv.std():.4f}}')
print(f'\\n{{classification_report(y_test, y_pred)}}')"""


def _code_knn(dataset, target):
    return f"""# ── KNN on {dataset} (auto-tune K) ─────────────────────
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import StandardScaler, LabelEncoder

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

X = df.drop(columns=['{target}'])
y = df['{target}']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

best_k, best_acc = 5, 0
for k in range(1, 21, 2):
    m = KNeighborsClassifier(n_neighbors=k)
    m.fit(X_train_s, y_train)
    a = accuracy_score(y_test, m.predict(X_test_s))
    if a > best_acc:
        best_k, best_acc = k, a

model = KNeighborsClassifier(n_neighbors=best_k)
model.fit(X_train_s, y_train)
y_pred = model.predict(X_test_s)
cv = cross_val_score(model, scaler.transform(X), y, cv=5)
print(f'Best K: {{best_k}} | Accuracy: {{best_acc:.4f}} ({{best_acc*100:.1f}}%)')
print(f'CV: {{cv.mean():.4f}} ± {{cv.std():.4f}}')
print(f'\\n{{classification_report(y_test, y_pred)}}')"""


def _plot_hist(dataset):
    return f"""import pandas as pd, matplotlib.pyplot as plt
df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
numeric = df.select_dtypes(include='number').columns
n = len(numeric)
fig, axes = plt.subplots(2, (n+1)//2, figsize=(14, 8))
axes = axes.flatten()
for i, col in enumerate(numeric[:10]):
    df[col].hist(ax=axes[i], bins=20, color='#71c84b', edgecolor='white', alpha=0.8)
    axes[i].set_title(col, fontsize=10)
for i in range(n, len(axes)):
    axes[i].set_visible(False)
plt.suptitle('{dataset} — Histograms', fontsize=14)
plt.tight_layout()
print('Histograms generated.')"""


def _plot_corr(dataset):
    return f"""import pandas as pd, matplotlib.pyplot as plt, numpy as np
df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
corr = df.select_dtypes(include='number').corr()
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(corr, cmap='RdYlGn', vmin=-1, vmax=1, aspect='auto')
ax.set_xticks(range(len(corr.columns)))
ax.set_xticklabels(corr.columns, rotation=45, ha='right', fontsize=9)
ax.set_yticks(range(len(corr.columns)))
ax.set_yticklabels(corr.columns, fontsize=9)
for i in range(len(corr.columns)):
    for j in range(len(corr.columns)):
        ax.text(j, i, f'{{corr.iloc[i,j]:.2f}}', ha='center', va='center', fontsize=7)
plt.colorbar(im)
plt.title('{dataset} — Correlation Heatmap')
plt.tight_layout()
print('Correlation heatmap generated.')"""


def _plot_scatter(dataset):
    return f"""import pandas as pd, matplotlib.pyplot as plt
df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
cols = df.select_dtypes(include='number').columns.tolist()
if len(cols) >= 2:
    fig, ax = plt.subplots(figsize=(8, 6))
    df.plot.scatter(x=cols[0], y=cols[1], ax=ax, color='#71c84b', alpha=0.6)
    ax.set_title(f'{{cols[0]}} vs {{cols[1]}}')
    plt.tight_layout()
    print(f'Scatter: {{cols[0]}} vs {{cols[1]}}')"""


def _plot_box(dataset):
    return f"""import pandas as pd, matplotlib.pyplot as plt
df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
numeric = df.select_dtypes(include='number').columns.tolist()
fig, ax = plt.subplots(figsize=(10, 6))
df[numeric].plot.box(ax=ax, rot=45)
ax.set_title('{dataset} — Box Plots')
plt.tight_layout()
print('Box plots generated.')"""


def _analyze_error(code, error):
    if "ModuleNotFoundError" in error or "ImportError" in error:
        if "'" in error:
            mod = error.split("'")[1]
            return f"# Install: !pip install {mod}\n\n{code}"
    if "KeyError" in error:
        return "import pandas as pd\nprint('Columns:', df.columns.tolist())"
    if "FileNotFoundError" in error:
        return f"import pandas as pd\ndf = pd.read_csv('/workspace/datasets/registry/iris.csv')\nprint(df.head())"
    if "NameError" in error:
        if "'np'" in error: return f"import numpy as np\n\n{code}"
        if "'pd'" in error: return f"import pandas as pd\n\n{code}"
        if "'plt'" in error: return f"import matplotlib.pyplot as plt\n\n{code}"
    return f"import pandas as pd, numpy as np, matplotlib.pyplot as plt\n\ntry:\n{chr(10).join('    ' + l for l in code.split(chr(10)))}\nexcept Exception as e:\n    print(f'Error: {{e}}')"


# ═══════════════════════════════════════════════════════════════════════════
#  Register all tools
# ═══════════════════════════════════════════════════════════════════════════

TOOLS: List[Tool] = [
    Tool("list_datasets", "List all available datasets in the registry.", {"type": "object", "properties": {}}, _tool_list_datasets),
    Tool("load_dataset", "Load a dataset and show EDA (shape, columns, head, describe, missing values).", {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}, _tool_load_dataset),
    Tool("do_eda", "Full EDA: shape, types, nulls, statistics, correlations, and distribution plots.", {"type": "object", "properties": {"dataset": {"type": "string"}}, "required": ["dataset"]}, _tool_do_eda),
    Tool("train_model", "Train an ML model (random_forest, linear_regression, logistic_regression, svm, knn) with full evaluation + CV.", {"type": "object", "properties": {"algorithm": {"type": "string"}, "dataset": {"type": "string"}, "target": {"type": "string"}}, "required": ["algorithm", "dataset"]}, _tool_train_model),
    Tool("compare_models", "Train 5 models (RF, LogReg, SVM, KNN, GradBoost) and compare side by side.", {"type": "object", "properties": {"dataset": {"type": "string"}, "target": {"type": "string"}}, "required": ["dataset"]}, _tool_compare_models),
    Tool("plot_data", "Generate a plot (histogram, correlation, scatter, box) for a dataset.", {"type": "object", "properties": {"dataset": {"type": "string"}, "plot_type": {"type": "string"}}, "required": ["dataset", "plot_type"]}, _tool_plot_data),
    Tool("fix_error", "Analyze a Python error and return corrected code.", {"type": "object", "properties": {"code": {"type": "string"}, "error": {"type": "string"}}, "required": ["error"]}, _tool_fix_error),
    Tool("explain_concept", "Explain an ML concept (random_forest, overfitting, cross_validation, gradient_descent, pca).", {"type": "object", "properties": {"concept": {"type": "string"}}, "required": ["concept"]}, _tool_explain_concept),
]

TOOL_MAP = {t.name: t for t in TOOLS}


def execute_tool(name: str, args: dict) -> dict:
    tool = TOOL_MAP.get(name)
    if not tool:
        return {"ok": False, "error": f"Unknown tool: {name}. Available: {', '.join(TOOL_MAP.keys())}"}
    return tool.execute(args)


def list_tools() -> List[dict]:
    return [t.to_dict() for t in TOOLS]
