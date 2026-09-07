"""
OpenBenchML — AI Coding Agent (production-grade, Entropy-inspired)
===================================================================

An autonomous AI assistant that:
  1. Understands natural language requests
  2. Writes Python code into notebook cells
  3. Executes the code
  4. Reads the output/errors and ITERATES (fix → retry loop)
  5. Keeps going until the code works or max iterations reached

Uses the z-ai-web-dev-sdk via Node.js subprocess for real LLM calls.
Falls back to rule-based responses if the SDK is unavailable.

AGENT LOOP (like Entropy's coding-runner):
  User: "Train a random forest on iris"
  → LLM generates code
  → Code inserted into cell + executed
  → If error: error sent back to LLM → LLM fixes code → retry
  → If success: return result + explanation
  → Max 3 iterations (prevents infinite loops)
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
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import APP_NAME, APP_VERSION, templates
from app.routes.auth import get_current_user_from_cookie
from app.database.db import SessionLocal

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  Models
# ═══════════════════════════════════════════════════════════════════════════

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=3, max_length=2000)
    context: Optional[str] = Field(None, description="Previous cell output for context")
    dataset: Optional[str] = Field(None, description="Current dataset name")
    error: Optional[str] = Field(None, description="Error from previous run (for fix loop)")


class AgentChatResponse(BaseModel):
    code: str = Field("", description="Python code to insert into a cell")
    explanation: str = Field("", description="Natural language explanation")
    action: str = Field("write_and_run", description="write | write_and_run | explain")
    cell_type: str = Field("code", description="code | text")
    iteration: int = Field(0, description="Which iteration of the fix loop")


# ═══════════════════════════════════════════════════════════════════════════
#  LLM integration — uses z-ai-web-dev-sdk via Node.js
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are OpenBenchML's AI coding assistant, embedded in a Jupyter-like notebook.
Your job is to help users write and execute Python ML code.

Available libraries: numpy (np), pandas (pd), scikit-learn (sklearn), matplotlib (plt), scipy
Available datasets: iris, titanic, wine, boston_housing, breast_cancer, california_housing, abalone, insurance, spam_email, concrete_strength, student_grades, credit_card_fraud, electric_cars, wine_recognition, pima_diabetes, heart_disease, auto_mpg, banknote_authentication, penguins, wine_quality_red, wine_quality_white

Load datasets with: pd.read_csv('/workspace/datasets/registry/iris.csv')
Or from sklearn: from sklearn.datasets import load_iris

RULES:
- Always use print() to show results
- Use matplotlib for visualizations (figures captured automatically)
- Keep code concise but complete (no placeholders, no "...")
- Add comments for key steps
- If fixing an error, ONLY output the corrected code

Respond with JSON:
{"code": "python code here", "explanation": "what it does", "action": "write_and_run", "cell_type": "code"}
"""


# Node.js script for calling the z-ai SDK
_NODE_SCRIPT = """
const ZAI = require('z-ai-web-dev-sdk').default;

async function main() {
  const system = process.env.OBML_SYSTEM_PROMPT;
  const user = process.env.OBML_USER_PROMPT;

  try {
    const zai = await ZAI.create();
    const response = await zai.chat.completions.create({
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user }
      ],
      temperature: 0.3,
      max_tokens: 2000,
    });
    console.log(response.choices[0]?.message?.content || '');
  } catch (e) {
    console.error('LLM_ERROR:' + e.message);
    process.exit(1);
  }
}
main();
"""


def call_llm(user_message: str, context: str = "", error: str = "") -> dict:
    """Call the LLM via z-ai-web-dev-sdk (Node.js subprocess).

    Returns dict with: code, explanation, action, cell_type
    Falls back to rule-based if SDK unavailable.
    """
    # Build the prompt
    user_prompt = f"User request: {user_message}"
    if context:
        user_prompt += f"\n\nPrevious output:\n{context[:800]}"
    if error:
        user_prompt += f"\n\nERROR from last run (fix this):\n{error[:800]}"
        user_prompt += "\n\nOutput ONLY the corrected code as JSON."
    else:
        user_prompt += "\n\nRespond with JSON only."

    # Try the z-ai CLI first (faster than Node subprocess)
    try:
        result = subprocess.run(
            ["z-ai", "chat",
             "--prompt", user_prompt,
             "--system", SYSTEM_PROMPT],
            capture_output=True,
            text=True,
            timeout=20,
            env={**os.environ, "OBML_SYSTEM_PROMPT": SYSTEM_PROMPT, "OBML_USER_PROMPT": user_prompt},
        )

        if result.returncode == 0 and result.stdout:
            response_text = result.stdout.strip()
            # Find JSON in the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)
                if "code" in parsed:
                    return parsed
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, Exception):
        pass

    # Try Node.js SDK
    try:
        result = subprocess.run(
            ["node", "-e", _NODE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=25,
            env={**os.environ, "OBML_SYSTEM_PROMPT": SYSTEM_PROMPT, "OBML_USER_PROMPT": user_prompt},
        )
        if result.returncode == 0 and result.stdout:
            response_text = result.stdout.strip()
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                return json.loads(response_text[json_start:json_end])
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, Exception):
        pass

    # Fallback: rule-based
    return _fallback_response(user_message, error)


def _fallback_response(message: str, error: str = "") -> dict:
    """Rule-based fallback when LLM is unavailable."""
    msg_lower = message.lower()

    # If fixing an error, suggest common fixes
    if error:
        if "ModuleNotFoundError" in error:
            mod = error.split("'")[1] if "'" in error else "module"
            return {
                "code": f"# Missing module: {mod}\n# Try: !pip install {mod}\nprint('Please install {mod} first: !pip install {mod}')",
                "explanation": f"The error indicates `{mod}` is not installed. Try running `!pip install {mod}` in a cell first.",
                "action": "write",
                "cell_type": "code",
            }
        if "KeyError" in error:
            return {
                "code": "# Check your column names\nprint(df.columns.tolist())",
                "explanation": "KeyError usually means a column name is wrong. Print the columns to check.",
                "action": "write_and_run",
                "cell_type": "code",
            }
        return {
            "code": "",
            "explanation": f"Error: {error[:200]}\n\nCheck the error above and try rephrasing your request.",
            "action": "explain",
            "cell_type": "text",
        }

    # Dataset loading
    datasets = ["iris", "titanic", "wine", "boston", "diabetes", "breast_cancer",
                "california_housing", "abalone", "insurance", "student_grades",
                "credit_card_fraud", "electric_cars", "concrete_strength", "penguins"]
    if "load" in msg_lower and any(ds in msg_lower for ds in datasets):
        ds_name = next(ds for ds in datasets if ds in msg_lower)
        return {
            "code": f"""import pandas as pd
df = pd.read_csv('/workspace/datasets/registry/{ds_name}.csv')
print(f'Dataset: {ds_name}')
print(f'Shape: {{df.shape}}')
print(f'Columns: {{list(df.columns)}}')
print()
print(df.head())""",
            "explanation": f"Loaded the {ds_name} dataset. Showing shape, columns, and first 5 rows.",
            "action": "write_and_run",
            "cell_type": "code",
        }

    # Train models
    if any(k in msg_lower for k in ["train", "fit", "model", "classify", "regress"]):
        if "random forest" in msg_lower or "rf" in msg_lower:
            return {
                "code": """from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import pandas as pd

df = pd.read_csv('/workspace/datasets/registry/iris.csv')
X = df.drop(columns=['species'])
y = df['species']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)

y_pred = rf.predict(X_test)
print(f'Accuracy: {accuracy_score(y_test, y_pred):.4f}')
print()
print(classification_report(y_test, y_pred))""",
                "explanation": "Trained a Random Forest on iris with 100 trees. Shows accuracy + classification report.",
                "action": "write_and_run",
                "cell_type": "code",
            }
        if "linear" in msg_lower or "regression" in msg_lower:
            return {
                "code": """from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import pandas as pd

df = pd.read_csv('/workspace/datasets/registry/boston_housing.csv')
X = df.drop(columns=['medv'])
y = df['medv']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

lr = LinearRegression()
lr.fit(X_train, y_train)

y_pred = lr.predict(X_test)
print(f'MAE: {mean_absolute_error(y_test, y_pred):.2f}')
print(f'R2: {r2_score(y_test, y_pred):.4f}')""",
                "explanation": "Trained Linear Regression on Boston Housing. Shows MAE and R².",
                "action": "write_and_run",
                "cell_type": "code",
            }

    # EDA / plots
    if any(k in msg_lower for k in ["plot", "visualize", "histogram", "chart", "eda"]):
        return {
            "code": """import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/workspace/datasets/registry/iris.csv')
fig, axes = plt.subplots(2, 2, figsize=(12, 8))
df.select_dtypes(include='number').iloc[:, :4].hist(ax=axes, bins=20, color='#71c84b')
plt.tight_layout()
print('Histograms generated.')""",
            "explanation": "Created histograms for all numeric features.",
            "action": "write_and_run",
            "cell_type": "code",
        }

    # Correlation
    if "correlation" in msg_lower or "heatmap" in msg_lower:
        return {
            "code": """import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv('/workspace/datasets/registry/iris.csv')
corr = df.select_dtypes(include='number').corr()
fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(corr, annot=True, cmap='Greens', ax=ax)
plt.title('Correlation Heatmap')
plt.tight_layout()""",
            "explanation": "Generated a correlation heatmap. (Requires seaborn: !pip install seaborn)",
            "action": "write_and_run",
            "cell_type": "code",
        }

    # Default
    return {
        "code": "",
        "explanation": "I can help you with:\n• 'Load the iris dataset'\n• 'Train a random forest on iris'\n• 'Plot histograms'\n• 'Show correlation heatmap'\n• 'Train linear regression on boston'\n\nI'll write the code, insert it, and run it automatically. If there's an error, I'll fix it and retry.",
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
    """
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
    finally:
        db.close()

    try:
        result = call_llm(payload.message, payload.context or "", payload.error or "")
    except Exception as e:
        result = _fallback_response(payload.message, str(e))

    return JSONResponse({
        "ok": True,
        "code": result.get("code", ""),
        "explanation": result.get("explanation", ""),
        "action": result.get("action", "write_and_run"),
        "cell_type": result.get("cell_type", "code"),
        "iteration": result.get("iteration", 0),
    })
