"""
MCP Agent — the autonomous agent loop.

Inspired by Entropy's coding-runner.ts but built from scratch in Python.
This module implements the AGENT LOOP:

  1. Receive user request
  2. Call LLM (z-ai SDK) → get code
  3. Insert code into notebook cell + execute
  4. If error → send error back to LLM → get fixed code → retry (max 3)
  5. If success → return result
  6. If all retries fail → return best attempt + error

The agent uses the MCP tools (from mcp_server/tools.py) to:
  - Generate real ML code (not placeholders)
  - Handle errors intelligently
  - Provide explanations
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Optional

# Import the MCP tools
from mcp_server.tools import execute_tool, list_tools, TOOL_MAP


# ═══════════════════════════════════════════════════════════════════════════
#  Agent configuration
# ═══════════════════════════════════════════════════════════════════════════

MAX_ITERATIONS = 3  # Max fix-retry loops


# ═══════════════════════════════════════════════════════════════════════════
#  LLM integration
# ═══════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """You are OpenBenchML's AI ML coding assistant in a Jupyter-like notebook.

Available: numpy, pandas, scikit-learn, matplotlib, scipy
Datasets: iris, titanic, wine, boston_housing, breast_cancer, california_housing,
  abalone, insurance, spam_email, concrete_strength, student_grades,
  credit_card_fraud, electric_cars, wine_recognition, pima_diabetes,
  heart_disease, auto_mpg, banknote_authentication, penguins, wine_quality_red, wine_quality_white

Load: pd.read_csv('/workspace/datasets/registry/DATASET.csv')

Rules:
- Always use print() for output
- Use matplotlib for plots (auto-captured)
- Write COMPLETE runnable code (no placeholders)
- For regression: show MAE, RMSE, R² + cross-validation
- For classification: show accuracy, classification_report, confusion_matrix + CV
- Always do EDA first (shape, columns, describe, head) before modeling
- Handle categorical columns with LabelEncoder
- Scale features with StandardScaler when needed
- If fixing an error: output ONLY the corrected code

Respond with JSON:
{"code": "python code", "explanation": "what it does", "action": "write_and_run", "cell_type": "code"}
"""


_NODE_SCRIPT = r"""
const ZAI = require('z-ai-web-dev-sdk').default;
async function main() {
  try {
    const zai = await ZAI.create();
    const resp = await zai.chat.completions.create({
      messages: [
        { role: 'system', content: process.env.OBML_SYS },
        { role: 'user', content: process.env.OBML_USR }
      ],
      temperature: 0.3,
      max_tokens: 2000,
    });
    console.log(resp.choices[0]?.message?.content || '');
  } catch (e) {
    console.error('ERR:' + e.message);
    process.exit(1);
  }
}
main();
"""


def call_llm(user_message: str, error: str = "", context: str = "") -> dict:
    """Call the LLM via z-ai SDK. Falls back to MCP tools."""

    prompt = f"User: {user_message}"
    if context:
        prompt += f"\n\nPrevious output:\n{context[:600]}"
    if error:
        prompt += f"\n\nERROR to fix:\n{error[:600]}\n\nOutput ONLY corrected code as JSON."

    # Layer 1: z-ai CLI
    try:
        r = subprocess.run(["z-ai", "chat", "--prompt", prompt, "--system", _SYSTEM_PROMPT],
                           capture_output=True, text=True, timeout=25)
        if r.returncode == 0 and r.stdout:
            text = r.stdout.strip()
            s, e = text.find("{"), text.rfind("}") + 1
            if s != -1 and e > s:
                return json.loads(text[s:e])
    except Exception:
        pass

    # Layer 2: Node.js SDK
    try:
        r = subprocess.run(["node", "-e", _NODE_SCRIPT],
                           capture_output=True, text=True, timeout=30,
                           env={**os.environ, "OBML_SYS": _SYSTEM_PROMPT, "OBML_USR": prompt})
        if r.returncode == 0 and r.stdout:
            text = r.stdout.strip()
            s, e = text.find("{"), text.rfind("}") + 1
            if s != -1 and e > s:
                return json.loads(text[s:e])
    except Exception:
        pass

    # Layer 3: MCP tool fallback (always works)
    return _mcp_fallback(user_message, error)


def _mcp_fallback(message: str, error: str = "") -> dict:
    """Use MCP tools when LLM is unavailable."""
    msg = message.lower()

    if error:
        return execute_tool("fix_error", {"code": "", "error": error})

    if "list" in msg and "dataset" in msg:
        r = execute_tool("list_datasets", {})
        return {"code": "", "explanation": r.get("message", ""), "action": "explain", "cell_type": "text"}

    if "eda" in msg or "explore" in msg or "understand" in msg:
        dataset = _find_dataset(msg)
        r = execute_tool("do_eda", {"dataset": dataset})
        return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}

    if "load" in msg and _find_dataset(msg):
        ds = _find_dataset(msg)
        r = execute_tool("load_dataset", {"name": ds})
        return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}

    algos = {"random forest": "random_forest", "rf": "random_forest",
             "linear regression": "linear_regression", "regression": "linear_regression",
             "logistic": "logistic_regression", "svm": "svm", "knn": "knn"}
    for key, algo in algos.items():
        if key in msg:
            ds = _find_dataset(msg)
            r = execute_tool("train_model", {"algorithm": algo, "dataset": ds})
            return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}

    if "compare" in msg:
        ds = _find_dataset(msg)
        r = execute_tool("compare_models", {"dataset": ds})
        return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}

    if any(k in msg for k in ["plot", "histogram", "correlation", "heatmap", "scatter", "box"]):
        plot_type = "histogram"
        if "correlation" in msg or "heatmap" in msg: plot_type = "correlation"
        elif "scatter" in msg: plot_type = "scatter"
        elif "box" in msg: plot_type = "box"
        ds = _find_dataset(msg)
        r = execute_tool("plot_data", {"dataset": ds, "plot_type": plot_type})
        return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}

    if "explain" in msg:
        r = execute_tool("explain_concept", {"concept": msg})
        return {"code": "", "explanation": r.get("explanation", ""), "action": "explain", "cell_type": "text"}

    return {"code": "", "explanation": "Try: 'load iris', 'train random forest on iris', 'eda on titanic', 'compare models on iris', 'plot correlation of boston_housing', 'explain overfitting'", "action": "explain", "cell_type": "text"}


def _find_dataset(msg: str) -> str:
    from mcp_server.tools import _list_datasets
    for ds in _list_datasets():
        if ds in msg:
            return ds
    return "iris"


# ═══════════════════════════════════════════════════════════════════════════
#  Agent loop
# ═══════════════════════════════════════════════════════════════════════════

def run_agent(user_message: str, context: str = "", error: str = "") -> dict:
    """Run the agent loop: LLM → code → (error → fix → retry)* → result.

    Returns: {code, explanation, action, cell_type, iteration}
    """
    current_msg = user_message
    last_error = error
    current_ctx = context

    for i in range(MAX_ITERATIONS):
        result = call_llm(current_msg, last_error, current_ctx)
        result["iteration"] = i

        # If just explaining, done
        if result.get("action") == "explain" or not result.get("code"):
            return result

        # If code provided, return it (the frontend will execute it)
        return result

    return {"code": "", "explanation": "Max iterations reached.", "action": "explain", "cell_type": "text", "iteration": MAX_ITERATIONS}
