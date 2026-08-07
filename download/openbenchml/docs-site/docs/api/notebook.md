# Notebook API

`POST /api/notebook/run` executes user-supplied Python code in the same
sandbox as `/api/convert` and returns the captured stdout/stderr. Use it
to power in-browser playgrounds, CI checks, or quick "does this code work?"
probes from the CLI.

!!! note "Authentication required"
    All endpoints on this page require a `Bearer` token.

## Run Python code

```http
POST /api/notebook/run
Content-Type: application/json
Authorization: Bearer <token>
```

### Request body

| Field              | Type    | Required | Default | Notes                                            |
| ------------------ | ------- | -------- | ------- | ------------------------------------------------ |
| `code`             | string  | yes      | —       | 1–50,000 chars.                                  |
| `timeout_seconds`  | integer | no       | `30`    | Range `1`–`120`. Wall-clock limit.               |

### Example

```bash
curl -X POST http://localhost:8000/api/notebook/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import numpy as np\nprint(f\"np version: {np.__version__}\")\nprint(f\"sum: {np.array([1,2,3]).sum()}\")",
    "timeout_seconds": 10
  }'
```

### Response — `200 OK`

The HTTP status is always 200 — execution success/failure is encoded in
the body's `ok` field so clients can use the same code path for both.

```json
{
  "ok": true,
  "stdout": "np version: 1.26.4\nsum: 6\n",
  "stderr": "",
  "error": null,
  "timed_out": false
}
```

### Response — `200 OK` (execution failed)

```json
{
  "ok": false,
  "stdout": "",
  "stderr": "Traceback (most recent call last):\n  File \"<user_code>\", line 1, in <module>\nNameError: name 'foo' is not defined\n",
  "error": "NameError: name 'foo' is not defined",
  "timed_out": false
}
```

### Response — `200 OK` (blocked import)

```json
{
  "ok": false,
  "stdout": "",
  "stderr": "Traceback (most recent call last):\n  File \"<user_code>\", line 1, in <module>\nImportError: Import of 'subprocess' is blocked by OpenBenchML sandbox.\n",
  "error": "ImportError: Import of 'subprocess' is blocked by OpenBenchML sandbox.",
  "timed_out": false
}
```

### Response — `200 OK` (timeout)

```json
{
  "ok": false,
  "stdout": "0\n1\n2\n...\n18\n",
  "stderr": "Traceback (most recent call last):\n  ...\nTimeoutError: Code execution exceeded 2s limit.\n",
  "error": "Code execution exceeded 2s limit.",
  "timed_out": true
}
```

### Response — `401 Unauthorized`

```json
{ "detail": "Authentication required" }
```

## What's pre-imported

See [Convert → Pre-imported libraries](../user-guide/convert.md#pre-imported-libraries).
The notebook uses the same sandbox as `/convert`.

## Difference from `/api/convert`

| Endpoint               | Runs code? | Pickles `model`? | Creates `MLModel` row? |
| ---------------------- | ---------- | ---------------- | ---------------------- |
| `POST /api/notebook/run` | ✅        | ❌                | ❌                      |
| `POST /api/convert`      | ✅        | ✅                | ✅                      |

Use the notebook for **exploration**, use convert for **creating models**.
