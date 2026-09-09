"""
LLM Bridge Client — Python side that talks to the Node.js LLM bridge.

This replaces the unreliable subprocess approach (z-ai CLI / node -e).
Instead, it:
  1. Starts the Node.js bridge server (mcp_server/llm_bridge.js) once
  2. Sends HTTP POST requests to it
  3. Gets real LLM responses back

This is the RELIABLE way to call the z-ai-web-dev-sdk from Python.
"""

from __future__ import annotations

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
from typing import Optional

_BRIDGE_PORT = 4599
_BRIDGE_URL = f"http://127.0.0.1:{_BRIDGE_PORT}"
_bridge_process: Optional[subprocess.Popen] = None
_bridge_ready: bool = False


def _ensure_bridge_running() -> bool:
    """Start the Node.js LLM bridge if not running. Returns True if ready."""
    global _bridge_process, _bridge_ready

    if _bridge_ready:
        return True

    # Check if bridge is already running (maybe from a previous call)
    if _check_bridge_health():
        _bridge_ready = True
        return True

    # Start the bridge
    bridge_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_bridge.js")
    if not os.path.exists(bridge_script):
        print(f"[llm-bridge] Script not found: {bridge_script}", file=sys.stderr)
        return False

    try:
        _bridge_process = subprocess.Popen(
            ["node", bridge_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            # Detach so it survives the request
            start_new_session=True,
        )
        print(f"[llm-bridge] Started Node.js bridge (PID {_bridge_process.pid})", file=sys.stderr)
    except Exception as e:
        print(f"[llm-bridge] Failed to start: {e}", file=sys.stderr)
        return False

    # Wait for it to be ready (max 10 seconds)
    for _ in range(20):
        time.sleep(0.5)
        if _check_bridge_health():
            _bridge_ready = True
            print("[llm-bridge] Ready!", file=sys.stderr)
            return True

    print("[llm-bridge] Did not become ready in 10s", file=sys.stderr)
    return False


def _check_bridge_health() -> bool:
    """Check if the bridge is running and responding."""
    try:
        req = urllib.request.Request(f"{_BRIDGE_URL}/health", method='GET')
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return data.get("ok", False)
    except Exception:
        return False


def call_llm_via_bridge(system_prompt: str, user_prompt: str, timeout: int = 25) -> Optional[str]:
    """Call the LLM via the Node.js bridge. Returns the raw text response.

    Returns None if the bridge is unavailable or the call fails.
    """
    if not _ensure_bridge_running():
        return None

    try:
        payload = json.dumps({"system": system_prompt, "user": user_prompt}).encode('utf-8')
        req = urllib.request.Request(
            f"{_BRIDGE_URL}/chat",
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                return data.get("text", "")
            else:
                print(f"[llm-bridge] Error: {data.get('error', 'unknown')}", file=sys.stderr)
                return None
    except urllib.error.URLError as e:
        print(f"[llm-bridge] URL error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[llm-bridge] Error: {e}", file=sys.stderr)
        return None


def shutdown_bridge():
    """Shutdown the bridge process (called on app shutdown)."""
    global _bridge_process, _bridge_ready
    if _bridge_process:
        try:
            _bridge_process.terminate()
            _bridge_process.wait(timeout=5)
        except Exception:
            try:
                _bridge_process.kill()
            except Exception:
                pass
        _bridge_process = None
        _bridge_ready = False
