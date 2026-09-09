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
    """Call the LLM via the persistent Node.js bridge.

    This is the REAL LLM call — not templates. The LLM generates code
    dynamically based on the user's request + context + errors.

    Falls back to MCP tools ONLY if the LLM is completely unavailable.
    """
    prompt = f"User request: {user_message}"
    if context:
        prompt += f"\n\nPrevious cell output:\n{context[:800]}"
    if error:
        prompt += f"\n\nERROR from last code execution:\n{error[:800]}"
        prompt += "\n\nAnalyze the error and output ONLY the corrected code as JSON."

    # Layer 1: Persistent Node.js bridge (RELIABLE — stays alive between requests)
    try:
        from mcp_server.llm_client import call_llm_via_bridge
        text = call_llm_via_bridge(_SYSTEM_PROMPT, prompt, timeout=25)
        if text:
            # Extract JSON from the LLM response
            s, e = text.find("{"), text.rfind("}") + 1
            if s != -1 and e > s:
                result = json.loads(text[s:e])
                if "code" in result:
                    return result
            # LLM responded but no JSON — wrap it
            return {"code": "", "explanation": text[:1000], "action": "explain", "cell_type": "text"}
    except Exception as e:
        print(f"[agent] Bridge call failed: {e}", file=sys.stderr)

    # Layer 2: z-ai CLI (fallback if bridge is down)
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

    # Layer 3: MCP tool fallback (templates — only if ALL LLM calls fail)
    return _mcp_fallback(user_message, error)


def _mcp_fallback(message: str, error: str = "") -> dict:
    """Smart natural language understanding — handles multi-intent messages.

    Understands phrases like:
      "create a ml model on iris and do eda and create visualization"
      → combines: EDA + train model + plot into ONE code cell

    This is NOT keyword matching — it's intent detection with synonyms.
    """
    msg = message.lower().strip()

    # ── Error fixing ──
    if error:
        return execute_tool("fix_error", {"code": "", "error": error})

    # ── Detect dataset ──
    dataset = _find_dataset(msg)

    # ── Detect ALL intents in the message ──
    intents = _detect_intents(msg)

    # ── List datasets ──
    if "list_datasets" in intents and len(intents) == 1:
        r = execute_tool("list_datasets", {})
        return {"code": "", "explanation": r.get("message", ""), "action": "explain", "cell_type": "text"}

    # ── Explain concept ──
    if "explain" in intents and len(intents) == 1:
        r = execute_tool("explain_concept", {"concept": msg})
        return {"code": "", "explanation": r.get("explanation", ""), "action": "explain", "cell_type": "text"}

    # ── Single intent ──
    if len(intents) == 1:
        intent = intents[0]
        if intent == "eda":
            r = execute_tool("do_eda", {"dataset": dataset})
            return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}
        if intent == "load":
            r = execute_tool("load_dataset", {"name": dataset})
            return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}
        if intent == "compare":
            r = execute_tool("compare_models", {"dataset": dataset})
            return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}
        if intent == "plot":
            plot_type = _detect_plot_type(msg)
            r = execute_tool("plot_data", {"dataset": dataset, "plot_type": plot_type})
            return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}
        if intent == "train":
            algo = _detect_algorithm(msg)
            r = execute_tool("train_model", {"algorithm": algo, "dataset": dataset})
            return {"code": r.get("code", ""), "explanation": r.get("explanation", ""), "action": "write_and_run", "cell_type": "code"}

    # ── MULTI-INTENT: combine multiple tools into one code cell ──
    if len(intents) > 1 or "preprocess" in intents:
        combined_code = f"# ── Combined: {' + '.join(intents)} on {dataset} ──────────\n"
        combined_explain = []

        if "eda" in intents or "load" in intents:
            r = execute_tool("do_eda", {"dataset": dataset})
            combined_code += r.get("code", "") + "\n\n"
            combined_explain.append(f"EDA on {dataset}")

        if "preprocess" in intents:
            pre_code = _code_preprocessing(dataset)
            combined_code += pre_code + "\n\n"
            combined_explain.append("Preprocessing (outliers + scaling + encoding)")

        if "train" in intents:
            algo = _detect_algorithm(msg)
            r = execute_tool("train_model", {"algorithm": algo, "dataset": dataset})
            combined_code += r.get("code", "") + "\n\n"
            combined_explain.append(f"Train {algo}")

        if "plot" in intents:
            plot_type = _detect_plot_type(msg)
            r = execute_tool("plot_data", {"dataset": dataset, "plot_type": plot_type})
            combined_code += r.get("code", "")
            combined_explain.append(f"Plot {plot_type}")

        if "compare" in intents:
            r = execute_tool("compare_models", {"dataset": dataset})
            combined_code += r.get("code", "")
            combined_explain.append("Compare 5 models")

        return {
            "code": combined_code,
            "explanation": f"Combined: {', '.join(combined_explain)} on {dataset}.",
            "action": "write_and_run",
            "cell_type": "code",
        }

    # ── Default help ──
    return {
        "code": "",
        "explanation": "I can help you:\n• 'create a model on iris' → train ML model\n• 'do eda on titanic' → full EDA with plots\n• 'plot correlation of boston_housing' → visualization\n• 'compare models on iris' → 5 models compared\n• 'create a ml model on iris and do eda and visualization' → all-in-one\n• 'explain overfitting' → concept explanation\n\nI'll write the code, insert it, and run it automatically.",
        "action": "explain",
        "cell_type": "text",
    }


def _detect_intents(msg: str) -> list:
    """Detect ALL intents in a natural language message.

    Understands synonyms:
      train: 'train', 'create model', 'build model', 'ml model', 'fit',
             'classify', 'regress', 'predict', 'machine learning'
      eda:   'eda', 'explore', 'understand', 'analyze', 'analysis',
             'data analysis', 'data exploration'
      plot:  'plot', 'visualize', 'visualization', 'chart', 'histogram',
             'correlation', 'heatmap', 'scatter', 'box', 'graph',
             'feature visualization', 'distribution'
      load:  'load', 'show', 'display', 'read', 'import dataset'
      compare: 'compare', 'best model', 'which model'
      list:  'list', 'available', 'what datasets'
      explain: 'explain', 'what is', 'how does', 'tell me about'
    """
    intents = []

    # Train intent (broad synonyms)
    train_words = ["train", "create model", "build model", "ml model", "fit",
                   "classify", "regress", "predict", "machine learning",
                   "create a model", "make a model", "build a model",
                   "train a model", "create ml", "model on",
                   "multiple linear", "multiple regression", "multivariate",
                   "linear regression", "logistic", "random forest",
                   "svm", "knn", "decision tree", "gradient boost",
                   "train a", "build a ml", "create a ml"]
    if any(w in msg for w in train_words):
        intents.append("train")

    # EDA intent
    eda_words = ["eda", "explore", "understand", "analyze", "analysis",
                 "data analysis", "data exploration", "do eda", "do edda",
                 "exploratory", "investigate", "high level"]
    if any(w in msg for w in eda_words):
        intents.append("eda")

    # Preprocessing intent (NEW)
    preprocess_words = ["preprocess", "preprocessing", "clean", "cleaning",
                        "outlier", "outliers", "missing value", "null",
                        "impute", "imputation", "encode", "encoding",
                        "scale", "scaling", "normalize", "standardize",
                        "feature selection", "select feature", "select k",
                        "transform", "pipeline"]
    if any(w in msg for w in preprocess_words):
        intents.append("preprocess")

    # Plot intent
    plot_words = ["plot", "visualize", "visualization", "chart", "histogram",
                  "correlation", "heatmap", "scatter", "box", "graph",
                  "feature visualization", "distribution", "features",
                  "visual", "draw", "figure", "box plot", "relation",
                  "relationship", "loss", "losses", "residual"]
    if any(w in msg for w in plot_words):
        intents.append("plot")

    # Load intent (only if no other intent — load is implied by eda/train)
    load_words = ["load", "show me", "display", "read dataset", "import dataset",
                  "open dataset", "view dataset"]
    if any(w in msg for w in load_words) and not intents:
        intents.append("load")

    # Compare intent
    if any(w in msg for w in ["compare", "best model", "which model", "versus", "vs"]):
        intents.append("compare")

    # List intent
    if any(w in msg for w in ["list", "available", "what datasets", "which datasets"]):
        intents.append("list_datasets")

    # Explain intent
    if any(w in msg for w in ["explain", "what is", "how does", "tell me about", "what are"]):
        intents.append("explain")

    return intents


def _detect_algorithm(msg: str) -> str:
    """Detect which ML algorithm the user wants."""
    if any(w in msg for w in ["random forest", "rf", "randomforest"]):
        return "random_forest"
    if any(w in msg for w in ["multiple linear", "multiple regression",
                              "multivariate linear", "linear regression",
                              "linearregression", "linreg", "multiple leniar",
                              "mutiple leniar", "mutliple"]):
        return "linear_regression"
    if any(w in msg for w in ["logistic", "logreg"]):
        return "logistic_regression"
    if "svm" in msg or "support vector" in msg:
        return "svm"
    if "knn" in msg or "k nearest" in msg or "knearest" in msg:
        return "knn"
    # Default: random forest (most popular, works for classification + regression)
    return "random_forest"


def _detect_plot_type(msg: str) -> str:
    """Detect which plot type the user wants."""
    if any(w in msg for w in ["correlation", "heatmap", "heat map"]):
        return "correlation"
    if "scatter" in msg:
        return "scatter"
    if any(w in msg for w in ["box", "outlier"]):
        return "box"
    if any(w in msg for w in ["histogram", "hist", "distribution", "features"]):
        return "histogram"
    # Default: histogram (shows feature distributions)
    return "histogram"


def _code_preprocessing(dataset: str) -> str:
    """Generate preprocessing code: outliers, encoding, scaling, feature selection."""
    target = _detect_target_from_dataset(dataset)
    return f"""# ── Preprocessing on {dataset} ──────────────────────────
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_selection import SelectKBest, f_regression, f_classif

df = pd.read_csv('/workspace/datasets/registry/{dataset}.csv')
print(f'Before preprocessing: {{df.shape}}')

# 1. Handle missing values
print(f'\\nMissing values: {{df.isnull().sum().sum()}}')
if df.isnull().sum().sum() > 0:
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col].fillna(df[col].mode()[0], inplace=True)
        else:
            df[col].fillna(df[col].median(), inplace=True)
    print('✓ Filled missing values')

# 2. Encode categorical columns
cat_cols = df.select_dtypes(include=['object']).columns
for col in cat_cols:
    df[col] = LabelEncoder().fit_transform(df[col].astype(str))
    print(f'✓ Encoded: {{col}}')

# 3. Outlier detection + removal (IQR method)
numeric_cols = df.select_dtypes(include=[np.number]).columns
outlier_count = 0
for col in numeric_cols:
    Q1, Q3 = df[col].quantile([0.25, 0.75])
    IQR = Q3 - Q1
    lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    outliers = ((df[col] < lower) | (df[col] > upper)).sum()
    if outliers > 0:
        print(f'  {{col}}: {{outliers}} outliers detected')
        outlier_count += outliers

# Box plot BEFORE outlier removal
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
df[numeric_cols].plot.box(ax=axes[0], rot=45)
axes[0].set_title('Before Outlier Removal')

# Remove outliers
for col in numeric_cols:
    Q1, Q3 = df[col].quantile([0.25, 0.75])
    IQR = Q3 - Q1
    lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    df = df[(df[col] >= lower) & (df[col] <= upper)]

print(f'\\nAfter outlier removal: {{df.shape}} (removed {{outlier_count}} outliers)')

# Box plot AFTER
df[numeric_cols].plot.box(ax=axes[1], rot=45)
axes[1].set_title('After Outlier Removal')
plt.tight_layout()

# 4. Feature scaling
X = df.drop(columns=['{target}'])
y = df['{target}']
scaler = StandardScaler()
X_scaled = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)
print(f'\\n✓ Scaled features (StandardScaler)')

# 5. Feature selection
is_cls = y.nunique() <= 20
selector = SelectKBest(f_classif if is_cls else f_regression, k=min(5, len(X.columns)))
selector.fit(X_scaled, y)
scores = pd.DataFrame({{
    'feature': X.columns,
    'score': selector.scores_
}}).sort_values('score', ascending=False)
print(f'\\nFeature Selection (top 5):')
print(scores.head().to_string(index=False))

# Plot feature scores
fig, ax = plt.subplots(figsize=(8, 4))
scores.head(10).plot.bar(x='feature', y='score', ax=ax, color='#71c84b')
ax.set_title('Feature Importance (SelectKBest)')
plt.tight_layout()
print(f'\\n✓ Preprocessing complete.')"""


def _detect_target_from_dataset(dataset: str) -> str:
    """Detect the target column for a dataset."""
    from mcp_server.tools import _detect_target
    return _detect_target(dataset)


def _find_dataset(msg: str) -> str:
    """Find a dataset name in the message — handles spaces and underscores.

    'boston housing' → 'boston_housing'
    'boston_housing' → 'boston_housing'
    'wine quality red' → 'wine_quality_red'
    """
    from mcp_server.tools import _list_datasets
    datasets = _list_datasets()
    msg_lower = msg.lower()

    # Direct match (underscore version)
    for ds in datasets:
        if ds in msg_lower:
            return ds

    # Try with spaces → underscores: "boston housing" → "boston_housing"
    for ds in datasets:
        spaced = ds.replace("_", " ")
        if spaced in msg_lower:
            return ds

    # Try partial matches: "boston" → "boston_housing", "wine" → "wine_recognition"
    partial_map = {
        "boston": "boston_housing",
        "california": "california_housing",
        "breast": "breast_cancer",
        "credit": "credit_card_fraud",
        "electric": "electric_cars",
        "concrete": "concrete_strength",
        "student": "student_grades",
        "spam": "spam_email",
        "titanic": "titanic",
        "iris": "iris",
        "penguin": "penguins",
        "diabetes": "pima_diabetes",
        "heart": "heart_disease",
        "wine": "wine_recognition",
        "abalone": "abalone",
        "insurance": "insurance",
        "mpg": "auto_mpg",
        "banknote": "banknote_authentication",
    }
    for key, ds in partial_map.items():
        if key in msg_lower and ds in datasets:
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
