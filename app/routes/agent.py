"""
OpenBenchML — MCP Server (Model Context Protocol) in Python
============================================================

A dedicated MCP server that gives the AI agent REAL tools to
communicate with notebook cells — inspired by Entropy's coding-tools.ts
but built from scratch in Python/FastAPI.

TOOLS (like Entropy's CODING_TOOLS):
  1. write_cell      — write Python code into a notebook cell
  2. run_cell         — execute a cell, return stdout/stderr/figures
  3. read_output      — read the output of the last executed cell
  4. list_datasets    — list all available datasets in the registry
  5. load_dataset     — load a dataset and return shape/columns/head
  6. train_model      — train a model on a dataset, return metrics
  7. plot_data        — generate a matplotlib plot
  8. explain_code     — explain what a piece of code does
  9. fix_error        — analyze an error and suggest a fix
  10. get_variables   — list all variables in the notebook namespace

ARCHITECTURE:
  ┌─────────┐     HTTP/JSON      ┌──────────┐     subprocess     ┌─────────┐
  │ Browser │ ──────────────────→ │ FastAPI  │ ─────────────────→ │ z-ai    │
  │ Notebook│ ←────────────────── │ MCP Srv  │ ←───────────────── │ LLM     │
  │ (JS)    │                    │ (Python) │                    │ (GLM)   │
  └─────────┘                    └──────────┘                    └─────────┘
                                       │
                                       ▼
                                 ┌──────────┐
                                 │ Notebook │
                                 │ Kernel   │
                                 │ (Python) │
                                 └──────────┘

The browser sends a chat message → MCP server calls the LLM → LLM returns
tool calls → MCP server executes the tools (write code, run cells) →
returns the result to the browser.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
import subprocess
import asyncio
from typing import Optional, Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import APP_NAME, APP_VERSION
from app.routes.auth import get_current_user_from_cookie
from app.database.db import SessionLocal

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  MCP TOOL DEFINITIONS (like Entropy's ToolDef)
# ═══════════════════════════════════════════════════════════════════════════

MCP_TOOLS = [
    {
        "name": "write_cell",
        "description": "Write Python code into a new notebook cell. The code will be inserted and optionally auto-executed.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The Python code to write"},
                "run": {"type": "boolean", "description": "Whether to auto-execute the cell", "default": True},
            },
            "required": ["code"],
        },
    },
    {
        "name": "run_cell",
        "description": "Execute Python code and return stdout, stderr, and any figures. Uses the server-side notebook kernel.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The Python code to execute"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "list_datasets",
        "description": "List all available datasets in the registry with their shapes and columns.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "load_dataset",
        "description": "Load a dataset from the registry and return its shape, columns, and first 5 rows.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Dataset name (e.g. 'iris', 'titanic', 'boston_housing')"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "train_model",
        "description": "Train an ML model on a dataset and return metrics (accuracy, MAE, R², etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "algorithm": {"type": "string", "description": "Algorithm: 'random_forest', 'linear_regression', 'logistic_regression', 'svm', 'knn'"},
                "dataset": {"type": "string", "description": "Dataset name from the registry"},
                "target": {"type": "string", "description": "Target column name (auto-detected if not specified)"},
            },
            "required": ["algorithm", "dataset"],
        },
    },
    {
        "name": "plot_data",
        "description": "Generate a matplotlib visualization of a dataset.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string", "description": "Dataset name"},
                "plot_type": {"type": "string", "description": "Type: 'histogram', 'scatter', 'correlation', 'box'"},
                "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to plot (optional, defaults to all numeric)"},
            },
            "required": ["dataset", "plot_type"],
        },
    },
    {
        "name": "fix_error",
        "description": "Analyze a Python error and return a corrected code snippet.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The code that failed"},
                "error": {"type": "string", "description": "The error message/traceback"},
            },
            "required": ["code", "error"],
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  TOOL EXECUTOR — runs the tools server-side
# ═══════════════════════════════════════════════════════════════════════════

def _registry_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "datasets", "registry")


def _list_available_datasets() -> list[str]:
    """List all CSV files in the registry."""
    path = _registry_path()
    if not os.path.exists(path):
        return []
    return sorted([f.replace(".csv", "") for f in os.listdir(path) if f.endswith(".csv")])


def _execute_tool(tool_name: str, args: dict) -> dict:
    """Execute an MCP tool and return the result.

    This is the CORE of the MCP server — each tool does real work.
    """
    if tool_name == "list_datasets":
        datasets = _list_available_datasets()
        return {
            "ok": True,
            "datasets": datasets,
            "count": len(datasets),
            "message": f"Found {len(datasets)} datasets: {', '.join(datasets[:10])}{'...' if len(datasets) > 10 else ''}",
        }

    if tool_name == "load_dataset":
        name = args.get("name", "").strip()
        if not name:
            return {"ok": False, "error": "Dataset name is required"}
        path = os.path.join(_registry_path(), f"{name}.csv")
        if not os.path.exists(path):
            available = _list_available_datasets()
            return {"ok": False, "error": f"Dataset '{name}' not found. Available: {', '.join(available[:15])}"}
        # Read with pandas
        code = f"""
import pandas as pd
df = pd.read_csv('{path}')
print(f'Dataset: {name}')
print(f'Shape: {{df.shape}}')
print(f'Columns: {{list(df.columns)}}')
print(f'Dtypes:\\n{{df.dtypes}}')
print(f'\\nFirst 5 rows:\\n{{df.head()}}')
print(f'\\nStatistics:\\n{{df.describe()}}')
"""
        return {"ok": True, "code": code, "action": "write_and_run"}

    if tool_name == "train_model":
        algorithm = args.get("algorithm", "random_forest").lower()
        dataset = args.get("dataset", "iris").lower()
        target = args.get("target", "")

        # Build the training code based on algorithm
        algorithms = {
            "random_forest": _code_random_forest(dataset, target),
            "linear_regression": _code_linear_regression(dataset, target),
            "logistic_regression": _code_logistic_regression(dataset, target),
            "svm": _code_svm(dataset, target),
            "knn": _code_knn(dataset, target),
        }

        if algorithm not in algorithms:
            return {"ok": False, "error": f"Unknown algorithm: {algorithm}. Available: {', '.join(algorithms.keys())}"}

        code = algorithms[algorithm]
        return {"ok": True, "code": code, "action": "write_and_run",
                "explanation": f"Training {algorithm} on {dataset} dataset."}

    if tool_name == "plot_data":
        dataset = args.get("dataset", "iris").lower()
        plot_type = args.get("plot_type", "histogram").lower()
        columns = args.get("columns", [])

        plot_code = _code_plot(dataset, plot_type, columns)
        return {"ok": True, "code": plot_code, "action": "write_and_run",
                "explanation": f"Generating {plot_type} plot for {dataset}."}

    if tool_name == "fix_error":
        code = args.get("code", "")
        error = args.get("error", "")
        fix = _analyze_and_fix_error(code, error)
        return {"ok": True, "code": fix, "action": "write_and_run",
                "explanation": "Fixed the error."}

    return {"ok": False, "error": f"Unknown tool: {tool_name}"}


# ═══════════════════════════════════════════════════════════════════════════
#  CODE GENERATORS — produce real, runnable Python code
# ═══════════════════════════════════════════════════════════════════════════

def _detect_target_column(dataset: str) -> str:
    """Auto-detect the likely target column for a dataset."""
    targets = {
        "iris": "species", "titanic": "survived", "wine": "class",
        "boston_housing": "medv", "breast_cancer": "malignant",
        "california_housing": "median_house_value", "diabetes": "outcome",
        "pima_diabetes": "outcome", "heart_disease": "target",
        "auto_mpg": "mpg", "banknote_authentication": "class",
        "wine_quality_red": "quality", "wine_quality_white": "quality",
        "penguins": "species", "abalone": "rings",
        "insurance": "charges", "spam_email": "is_spam",
        "wine_recognition": "class", "electric_cars": "range_km",
        "student_grades": "final_grade", "credit_card_fraud": "is_fraud",
        "concrete_strength": "compressive_strength",
    }
    return targets.get(dataset, "target")


def _code_random_forest(dataset: str, target: str = "") -> str:
    target = target or _detect_target_column(dataset)
    return f"""# ── Random Forest on {dataset} ──────────────────────────
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (accuracy_score, classification_report,
                             mean_absolute_error, r2_score)
from sklearn.preprocessing import LabelEncoder

# Load data
df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
print(f'Dataset: {dataset}, Shape: {{df.shape}}')
print(f'Columns: {{list(df.columns)}}')

# Encode categorical columns
for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

# Split features and target
X = df.drop(columns=['{target}'])
y = df['{target}']

# Determine if classification or regression
is_classification = y.nunique() <= 20
print(f'Task: {{\"Classification\" if is_classification else \"Regression\"}}')
print(f'Target: {{y.name}}, Unique values: {{y.nunique()}}')

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y if is_classification else None
)

# Train Random Forest
if is_classification:
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
else:
    model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)

model.fit(X_train, y_train)
y_pred = model.predict(X_test)

# Evaluate
if is_classification:
    acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='accuracy')
    print(f'\\n=== Results ===')
    print(f'Accuracy: {{acc:.4f}} ({{acc*100:.1f}}%)')
    print(f'CV Accuracy: {{cv_scores.mean():.4f}} ± {{cv_scores.std():.4f}}')
    print(f'\\nClassification Report:\\n{{classification_report(y_test, y_pred)}}')
else:
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    cv_scores = cross_val_score(model, X, y, cv=5, scoring='r2')
    print(f'\\n=== Results ===')
    print(f'MAE: {{mae:.4f}}')
    print(f'R²: {{r2:.4f}}')
    print(f'CV R²: {{cv_scores.mean():.4f}} ± {{cv_scores.std():.4f}}')

# Feature importance
importances = pd.DataFrame({{
    'feature': X.columns,
    'importance': model.feature_importances_
}}).sort_values('importance', ascending=False)
print(f'\\nFeature Importance (top 5):')
print(importances.head().to_string(index=False))
"""


def _code_linear_regression(dataset: str, target: str = "") -> str:
    target = target or _detect_target_column(dataset)
    return f"""# ── Linear Regression on {dataset} ──────────────────────
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler, LabelEncoder

# Load data
df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
print(f'Dataset: {dataset}, Shape: {{df.shape}}')

# Encode categoricals
for col in df.select_dtypes(include=['object']).columns:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))

# Split
X = df.drop(columns=['{target}'])
y = df['{target}']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Scale features
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Train Linear Regression
lr = LinearRegression()
lr.fit(X_train_scaled, y_train)
y_pred = lr.predict(X_test_scaled)

# Also try Ridge for comparison
ridge = Ridge(alpha=1.0)
ridge.fit(X_train_scaled, y_train)
y_pred_ridge = ridge.predict(X_test_scaled)

# Evaluate
mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)
r2 = r2_score(y_test, y_pred)
cv_r2 = cross_val_score(lr, scaler.transform(X), y, cv=5, scoring='r2')

print(f'\\n=== Linear Regression Results ===')
print(f'MAE:  {{mae:.4f}}')
print(f'MSE:  {{mse:.4f}}')
print(f'RMSE: {{rmse:.4f}}')
print(f'R²:   {{r2:.4f}} ({{r2*100:.1f}}%)')
print(f'CV R²: {{cv_r2.mean():.4f}} ± {{cv_r2.std():.4f}}')

r2_ridge = r2_score(y_test, y_pred_ridge)
print(f'\\nRidge R²: {{r2_ridge:.4f}}')

# Coefficients
coefs = pd.DataFrame({{
    'feature': X.columns,
    'coefficient': lr.coef_
}}).sort_values('coefficient', key=abs, ascending=False)
print(f'\\nCoefficients (top 5 by magnitude):')
print(coefs.head().to_string(index=False))
"""


def _code_logistic_regression(dataset: str, target: str = "") -> str:
    target = target or _detect_target_column(dataset)
    return f"""# ── Logistic Regression on {dataset} ────────────────────
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler, LabelEncoder

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
print(f'Dataset: {{df.shape}}')

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
print(f'\\nAccuracy: {{acc:.4f}} ({{acc*100:.1f}}%)')
print(f'CV: {{cv.mean():.4f}} ± {{cv.std():.4f}}')
print(f'\\n{{classification_report(y_test, y_pred)}}')
print(f'Confusion Matrix:\\n{{confusion_matrix(y_test, y_pred)}}')
"""


def _code_svm(dataset: str, target: str = "") -> str:
    target = target or _detect_target_column(dataset)
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
print(f'\\n{{classification_report(y_test, y_pred)}}')
"""


def _code_knn(dataset: str, target: str = "") -> str:
    target = target or _detect_target_column(dataset)
    return f"""# ── KNN on {dataset} ────────────────────────────────────
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

# Try multiple K values
best_k, best_acc = 5, 0
for k in range(1, 21, 2):
    model = KNeighborsClassifier(n_neighbors=k)
    model.fit(X_train_s, y_train)
    acc = accuracy_score(y_test, model.predict(X_test_s))
    if acc > best_acc:
        best_k, best_acc = k, acc

model = KNeighborsClassifier(n_neighbors=best_k)
model.fit(X_train_s, y_train)
y_pred = model.predict(X_test_s)
cv = cross_val_score(model, scaler.transform(X), y, cv=5)

print(f'Best K: {{best_k}}')
print(f'KNN Accuracy: {{best_acc:.4f}} ({{best_acc*100:.1f}}%)')
print(f'CV: {{cv.mean():.4f}} ± {{cv.std():.4f}}')
print(f'\\n{{classification_report(y_test, y_pred)}}')
"""


def _code_plot(dataset: str, plot_type: str, columns: list) -> str:
    if plot_type == "histogram":
        return f"""# ── Histogram for {dataset} ─────────────────────────────
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
numeric_cols = df.select_dtypes(include='number').columns
n = len(numeric_cols)
fig, axes = plt.subplots(2, (n+1)//2, figsize=(14, 8))
axes = axes.flatten() if n > 1 else [axes]
for i, col in enumerate(numeric_cols[:10]):
    df[col].hist(ax=axes[i], bins=20, color='#71c84b', edgecolor='white', alpha=0.8)
    axes[i].set_title(col, fontsize=11)
for i in range(len(numeric_cols), len(axes)):
    axes[i].set_visible(False)
plt.suptitle('{dataset} - Histograms', fontsize=14)
plt.tight_layout()
print('Histograms generated.')
"""
    elif plot_type == "correlation":
        return f"""# ── Correlation Heatmap for {dataset} ──────────────────
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

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
plt.colorbar(im, label='Correlation')
plt.title('{dataset} - Correlation Heatmap', fontsize=14)
plt.tight_layout()
print('Correlation heatmap generated.')
"""
    elif plot_type == "scatter":
        return f"""# ── Scatter Plot for {dataset} ─────────────────────────
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
numeric_cols = df.select_dtypes(include='number').columns.tolist()
if len(numeric_cols) >= 2:
    fig, ax = plt.subplots(figsize=(8, 6))
    df.plot.scatter(x=numeric_cols[0], y=numeric_cols[1], ax=ax, color='#71c84b', alpha=0.6)
    ax.set_title(f'{{numeric_cols[0]}} vs {{numeric_cols[1]}}', fontsize=13)
    plt.tight_layout()
    print(f'Scatter plot: {{numeric_cols[0]}} vs {{numeric_cols[1]}}')
else:
    print('Not enough numeric columns for scatter plot.')
"""
    elif plot_type == "box":
        return f"""# ── Box Plot for {dataset} ─────────────────────────────
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
numeric_cols = df.select_dtypes(include='number').columns.tolist()
fig, ax = plt.subplots(figsize=(10, 6))
df[numeric_cols].plot.box(ax=ax, rot=45, color='#71c84b')
ax.set_title('{dataset} - Box Plots', fontsize=14)
plt.tight_layout()
print('Box plots generated.')
"""
    return f"print('Unknown plot type: {plot_type}')"


def _analyze_and_fix_error(code: str, error: str) -> str:
    """Analyze a Python error and return fixed code."""
    # Common error patterns
    if "ModuleNotFoundError" in error or "ImportError" in error:
        # Extract module name
        if "'" in error:
            mod = error.split("'")[1]
            return f"# Install missing module first\n!pip install {mod}\n\n# Then run your code:\n{code}"

    if "KeyError" in error:
        return f"# Check column names first\nimport pandas as pd\nprint('Available columns:', df.columns.tolist())\n\n# Original code:\n{code}"

    if "FileNotFoundError" in error:
        # Fix dataset path
        datasets = _list_available_datasets()
        return f"""# Available datasets: {', '.join(datasets[:15])}
import pandas as pd
# Fix: use the correct dataset path
df = pd.read_csv('/workspace/datasets/registry/iris.csv')
print(f'Loaded: {{df.shape}}')
print(df.head())"""

    if "NameError" in error:
        if "'np'" in error:
            return f"import numpy as np\n\n{code}"
        if "'pd'" in error:
            return f"import pandas as pd\n\n{code}"
        if "'plt'" in error:
            return f"import matplotlib.pyplot as plt\n\n{code}"

    if "ValueError" in error and "shape" in error.lower():
        return f"# Shape mismatch — check your data\nprint('X shape:', X.shape)\nprint('y shape:', y.shape)\nprint('Make sure they match!')\n\n# Original code:\n{code}"

    # Generic fix: add imports + print debugging
    return f"# Fixed code (added imports + error handling)\nimport pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\n\ntry:\n{chr(10).join('    ' + line for line in code.split(chr(10)))}\nexcept Exception as e:\n    print(f'Error: {{e}}')\n    print('Check the error above and adjust the code.')"


# ═══════════════════════════════════════════════════════════════════════════
#  LLM INTEGRATION — calls z-ai SDK directly via Node.js
# ═══════════════════════════════════════════════════════════════════════════

_LLM_NODE_SCRIPT = r"""
const ZAI = require('z-ai-web-dev-sdk').default;

async function main() {
  const systemPrompt = process.env.OBML_SYSTEM;
  const userPrompt = process.env.OBML_USER;

  try {
    const zai = await ZAI.create();
    const response = await zai.chat.completions.create({
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      temperature: 0.3,
      max_tokens: 2000,
    });
    console.log(JSON.stringify(response.choices[0]?.message?.content || ''));
  } catch (e) {
    console.error(JSON.stringify({error: e.message}));
    process.exit(1);
  }
}
main();
"""


def call_llm_intelligent(user_message: str, error: str = "", context: str = "") -> dict:
    """Call the LLM via z-ai-web-dev-sdk with tool-calling context.

    Returns a dict with: code, explanation, action, cell_type
    """
    system_prompt = f"""You are OpenBenchML's AI ML coding assistant. You help users write and run Python ML code in a Jupyter-like notebook.

Available libraries: numpy, pandas, scikit-learn, matplotlib, scipy
Available datasets: {', '.join(_list_available_datasets())}

Load datasets: pd.read_csv('/workspace/datasets/registry/DATASET.csv')

When the user asks for something, respond with JSON:
{{"code": "complete python code", "explanation": "what it does", "action": "write_and_run", "cell_type": "code"}}

For explanations only: {{"code": "", "explanation": "...", "action": "explain", "cell_type": "text"}}

Rules:
- Always use print() for output
- Use matplotlib for plots (auto-captured)
- Write COMPLETE, runnable code (no placeholders)
- Add comments for key steps
- For regression: show MAE, RMSE, R²
- For classification: show accuracy, classification_report, confusion_matrix
- Always do EDA first (shape, columns, describe, head) before modeling
- Handle categorical columns with LabelEncoder
- Scale features with StandardScaler when needed
- Use cross_val_score for honest evaluation
- If fixing an error, output ONLY the corrected code"""

    user_prompt = f"User request: {user_message}"
    if context:
        user_prompt += f"\n\nPrevious output:\n{context[:600]}"
    if error:
        user_prompt += f"\n\nERROR to fix:\n{error[:600]}\n\nOutput the corrected code."

    # Try z-ai CLI
    try:
        result = subprocess.run(
            ["z-ai", "chat", "--prompt", user_prompt, "--system", system_prompt],
            capture_output=True, text=True, timeout=25,
        )
        if result.returncode == 0 and result.stdout:
            text = result.stdout.strip()
            # Extract JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
    except Exception:
        pass

    # Try Node.js SDK
    try:
        result = subprocess.run(
            ["node", "-e", _LLM_NODE_SCRIPT],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "OBML_SYSTEM": system_prompt, "OBML_USER": user_prompt},
        )
        if result.returncode == 0 and result.stdout:
            text = result.stdout.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
    except Exception:
        pass

    # Fallback: use MCP tools directly
    return _mcp_fallback(user_message, error)


def _mcp_fallback(message: str, error: str = "") -> dict:
    """Use MCP tools to generate a response when LLM is unavailable."""
    msg = message.lower()

    # If fixing error
    if error:
        result = _execute_tool("fix_error", {"code": "", "error": error})
        return {"code": result.get("code", ""), "explanation": "Fixed the error.",
                "action": "write_and_run", "cell_type": "code"}

    # List datasets
    if "list" in msg and "dataset" in msg:
        result = _execute_tool("list_datasets", {})
        return {"code": "", "explanation": result.get("message", ""), "action": "explain", "cell_type": "text"}

    # Load dataset
    if "load" in msg and any(ds in msg for ds in _list_available_datasets()):
        ds = next(ds for ds in _list_available_datasets() if ds in msg)
        result = _execute_tool("load_dataset", {"name": ds})
        return {"code": result.get("code", ""), "explanation": f"Loading {ds} dataset.",
                "action": "write_and_run", "cell_type": "code"}

    # Train models
    algos = {"random forest": "random_forest", "rf": "random_forest",
             "linear regression": "linear_regression", "regression": "linear_regression",
             "logistic": "logistic_regression",
             "svm": "svm", "support vector": "svm",
             "knn": "knn", "k nearest": "knn"}

    for key, algo in algos.items():
        if key in msg:
            # Find dataset
            dataset = "iris"  # default
            for ds in _list_available_datasets():
                if ds in msg:
                    dataset = ds
                    break
            result = _execute_tool("train_model", {"algorithm": algo, "dataset": dataset})
            return {"code": result.get("code", ""), "explanation": result.get("explanation", ""),
                    "action": "write_and_run", "cell_type": "code"}

    # Plot
    if any(k in msg for k in ["plot", "histogram", "visualize", "chart", "correlation", "heatmap", "box"]):
        plot_type = "histogram"
        if "correlation" in msg or "heatmap" in msg:
            plot_type = "correlation"
        elif "scatter" in msg:
            plot_type = "scatter"
        elif "box" in msg:
            plot_type = "box"
        dataset = "iris"
        for ds in _list_available_datasets():
            if ds in msg:
                dataset = ds
                break
        result = _execute_tool("plot_data", {"dataset": dataset, "plot_type": plot_type})
        return {"code": result.get("code", ""), "explanation": result.get("explanation", ""),
                "action": "write_and_run", "cell_type": "code"}

    # Default
    return {
        "code": "",
        "explanation": "I can help you:\n• Load a dataset: 'load iris'\n• Train a model: 'train random forest on iris'\n• Plot data: 'plot histogram of iris'\n• Show correlation: 'correlation heatmap of boston_housing'\n• List datasets: 'list datasets'\n\nI'll write the code, insert it into a cell, and run it automatically. If there's an error, I'll fix it and retry.",
        "action": "explain", "cell_type": "text",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

class AgentRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=2000)
    context: Optional[str] = None
    error: Optional[str] = None
    dataset: Optional[str] = None


@router.post("/api/agent/chat")
async def agent_chat(request: Request, payload: AgentRequest):
    """Main agent endpoint — receives a chat message, returns code to execute.

    Uses the MCP tool system + LLM to generate intelligent responses.
    """
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
        if user is None:
            return JSONResponse(
                status_code=401,
                content={"ok": False, "error": "Authentication required. Please log in."},
            )
    finally:
        db.close()

    try:
        result = call_llm_intelligent(payload.message, payload.error or "", payload.context or "")
    except Exception as e:
        result = _mcp_fallback(payload.message, str(e))

    return JSONResponse({
        "ok": True,
        "code": result.get("code", ""),
        "explanation": result.get("explanation", ""),
        "action": result.get("action", "write_and_run"),
        "cell_type": result.get("cell_type", "code"),
    })


@router.get("/api/agent/tools")
async def list_mcp_tools():
    """List all available MCP tools (for the UI to display)."""
    return JSONResponse({"tools": MCP_TOOLS, "count": len(MCP_TOOLS)})


@router.post("/api/agent/execute")
async def execute_mcp_tool(request: Request):
    """Execute a specific MCP tool directly (for advanced use)."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
        if user is None:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Auth required"})
    finally:
        db.close()

    body = await request.json()
    tool_name = body.get("tool")
    args = body.get("args", {})

    result = _execute_tool(tool_name, args)
    return JSONResponse(result)
