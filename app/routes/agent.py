"""
OpenBenchML — AI Coding Agent (Python port of Entropy's agent)
==============================================================

An autonomous AI assistant that can:
  1. Understand natural language requests ("train a random forest on iris")
  2. Write Python code into notebook cells
  3. Execute the code
  4. Read the output and iterate

Inspired by Entropy's coding-runner.ts but implemented in Python using:
  - z-ai-web-dev-sdk (GLM model) for LLM completions
  - FastAPI endpoint (/api/agent/chat) for the chat interface
  - Tool-calling pattern: the LLM returns code, we execute it

The agent has these tools:
  - write_code: write Python code into a notebook cell
  - run_code: execute the current cell and return stdout/stderr
  - read_output: read the output of the last cell
  - explain: explain a concept to the user

USAGE:
  POST /api/agent/chat
  Body: { "message": "Train a random forest on iris and show accuracy" }
  Response: { "code": "...", "explanation": "...", "action": "write_and_run" }
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import APP_NAME, APP_VERSION, templates
from app.routes.auth import get_current_user_from_cookie
from app.database.db import SessionLocal

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  Agent request/response models
# ═══════════════════════════════════════════════════════════════════════════

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    context: Optional[str] = Field(None, description="Previous cell output for context")
    dataset: Optional[str] = Field(None, description="Current dataset name")


class AgentChatResponse(BaseModel):
    code: str = Field("", description="Python code to insert into a cell")
    explanation: str = Field("", description="Natural language explanation")
    action: str = Field("write_and_run", description="write | write_and_run | explain")
    cell_type: str = Field("code", description="code | text")


# ═══════════════════════════════════════════════════════════════════════════
#  LLM integration — uses z-ai-web-dev-sdk via subprocess
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are OpenBenchML's AI coding assistant, embedded in a Jupyter-like notebook.
Your job is to help users write and execute Python ML code.

You have access to:
- numpy (np), pandas (pd), scikit-learn (sklearn), matplotlib (plt), scipy
- 20 pre-loaded datasets in /workspace/datasets/registry/ (iris, titanic, wine, breast_cancer, etc.)
- Pyodide (browser Python) or server-side Python

When the user asks you to do something:
1. Write the Python code that accomplishes their goal
2. Explain briefly what the code does
3. The code will be automatically inserted into a notebook cell and executed

RULES:
- Always use print() to show results (the notebook captures stdout)
- Use matplotlib for visualizations (figures are captured automatically)
- Load datasets with: pd.read_csv('/workspace/datasets/registry/iris.csv')
  or from sklearn: from sklearn.datasets import load_iris
- Keep code concise but complete (no placeholders)
- Add comments explaining key steps
- If the user asks about a concept (not code), set action="explain" and write an explanation

Return your response as JSON:
{
  "code": "import pandas as pd\\ndf = pd.read_csv(...)\\nprint(df.head())",
  "explanation": "This code loads the iris dataset and shows the first 5 rows.",
  "action": "write_and_run",
  "cell_type": "code"
}

For explanations only:
{
  "code": "",
  "explanation": "Random Forest works by...",
  "action": "explain",
  "cell_type": "text"
}
"""


def call_llm(user_message: str, context: str = "", dataset: str = "") -> dict:
    """Call the LLM (z-ai GLM) via the z-ai CLI.

    Falls back to a simple rule-based response if the CLI is unavailable.
    """
    # Build the full prompt
    user_prompt = f"User request: {user_message}"
    if context:
        user_prompt += f"\n\nPrevious cell output (for context):\n{context[:500]}"
    if dataset:
        user_prompt += f"\n\nCurrent dataset: {dataset}"
    user_prompt += "\n\nRespond with JSON only. Write complete, runnable Python code."

    try:
        # Try using the z-ai CLI (installed in the environment)
        result = subprocess.run(
            ["z-ai", "chat", "--prompt", f"{SYSTEM_PROMPT}\n\n{user_prompt}",
             "--system", "You are a Python ML coding assistant. Return JSON only."],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout:
            # Try to parse the response as JSON
            response_text = result.stdout.strip()
            # Find JSON in the response (LLM might wrap it in markdown)
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, Exception) as e:
        print(f"[agent] LLM call failed: {e}", flush=True)

    # Fallback: rule-based response
    return _fallback_response(user_message, dataset)


def _fallback_response(message: str, dataset: str = "") -> dict:
    """Simple rule-based fallback when the LLM is unavailable."""
    msg_lower = message.lower()

    # Dataset loading
    if "load" in msg_lower and any(ds in msg_lower for ds in ["iris", "titanic", "wine", "boston", "diabetes"]):
        ds_name = next(ds for ds in ["iris", "titanic", "wine", "boston", "diabetes"] if ds in msg_lower)
        return {
            "code": f"""import pandas as pd
df = pd.read_csv('/workspace/datasets/registry/{ds_name}.csv')
print(f'Dataset: {ds_name}')
print(f'Shape: {{df.shape}}')
print(f'Columns: {{list(df.columns)}}')
df.head()""",
            "explanation": f"Loaded the {ds_name} dataset from the registry. Showing shape, columns, and first 5 rows.",
            "action": "write_and_run",
            "cell_type": "code",
        }

    # Train a model
    if "train" in msg_lower or "fit" in msg_lower:
        if "random forest" in msg_lower or "rf" in msg_lower:
            return {
                "code": """from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import pandas as pd

# Load iris dataset
df = pd.read_csv('/workspace/datasets/registry/iris.csv')
X = df.drop(columns=['species'])
y = df['species']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train Random Forest
rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)

# Evaluate
y_pred = rf.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f'Accuracy: {accuracy:.4f}')
print()
print(classification_report(y_test, y_pred))""",
                "explanation": "Trained a Random Forest classifier on the iris dataset with 100 trees. Shows accuracy + classification report.",
                "action": "write_and_run",
                "cell_type": "code",
            }

        if "linear regression" in msg_lower or "regression" in msg_lower:
            return {
                "code": """from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import pandas as pd

# Load boston housing dataset
df = pd.read_csv('/workspace/datasets/registry/boston_housing.csv')
X = df.drop(columns=['medv'])
y = df['medv']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train Linear Regression
lr = LinearRegression()
lr.fit(X_train, y_train)

# Evaluate
y_pred = lr.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)
print(f'MAE: {mae:.2f}')
print(f'R²: {r2:.4f}')""",
                "explanation": "Trained a Linear Regression model on the Boston Housing dataset. Shows MAE and R² score.",
                "action": "write_and_run",
                "cell_type": "code",
            }

    # EDA / visualization
    if "plot" in msg_lower or "visualize" in msg_lower or "histogram" in msg_lower:
        return {
            "code": """import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/workspace/datasets/registry/iris.csv')

fig, axes = plt.subplots(2, 2, figsize=(12, 8))
df['sepal_length'].hist(ax=axes[0,0], bins=20, color='#a0c000')
axes[0,0].set_title('Sepal Length')
df['sepal_width'].hist(ax=axes[0,1], bins=20, color='#58a6ff')
axes[0,1].set_title('Sepal Width')
df['petal_length'].hist(ax=axes[1,0], bins=20, color='#bc8cff')
axes[1,0].set_title('Petal Length')
df['petal_width'].hist(ax=axes[1,1], bins=20, color='#f85149')
axes[1,1].set_title('Petal Width')
plt.tight_layout()
print('Histograms generated.')""",
            "explanation": "Created histograms for all 4 features in the iris dataset.",
            "action": "write_and_run",
            "cell_type": "code",
        }

    # Default: explain
    return {
        "code": "",
        "explanation": f"I can help you with that! Try asking me to:\n- 'Load the iris dataset'\n- 'Train a random forest on iris'\n- 'Plot a histogram of the iris features'\n- 'Do EDA on the titanic dataset'\n\nI'll write the code, insert it into a cell, and run it automatically.",
        "action": "explain",
        "cell_type": "text",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  API endpoint
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/api/agent/chat")
async def agent_chat(
    request: Request,
    payload: AgentChatRequest,
):
    """AI agent endpoint — receives a natural language request,
    returns Python code + explanation to insert into the notebook.

    The frontend inserts the code into a new cell and optionally runs it.
    """
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
    finally:
        db.close()

    # Call the LLM
    try:
        result = call_llm(payload.message, payload.context or "", payload.dataset or "")
    except Exception as e:
        # Fallback to rule-based
        result = _fallback_response(payload.message, payload.dataset or "")

    return JSONResponse({
        "ok": True,
        "code": result.get("code", ""),
        "explanation": result.get("explanation", ""),
        "action": result.get("action", "write_and_run"),
        "cell_type": result.get("cell_type", "code"),
    })
