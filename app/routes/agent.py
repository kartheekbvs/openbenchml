"""
OpenBenchML — Agent API Routes
================================

Thin FastAPI wrapper around the MCP server (mcp_server/).
The actual logic lives in mcp_server/agent.py + mcp_server/tools.py.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.routes.auth import get_current_user_from_cookie
from app.database.db import SessionLocal

# Import from the MCP server
from mcp_server.agent import run_agent, call_llm, MAX_ITERATIONS
from mcp_server.tools import list_tools, execute_tool

router = APIRouter()


class AgentRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=2000)
    context: Optional[str] = None
    error: Optional[str] = None
    dataset: Optional[str] = None


@router.post("/api/agent/chat")
async def agent_chat(request: Request, payload: AgentRequest):
    """Main agent endpoint — receives a chat message, returns code to execute."""
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
        result = run_agent(payload.message, payload.context or "", payload.error or "")
    except Exception as e:
        result = {
            "code": "",
            "explanation": f"Agent error: {e}",
            "action": "explain",
            "cell_type": "text",
            "iteration": 0,
        }

    return JSONResponse({
        "ok": True,
        "code": result.get("code", ""),
        "explanation": result.get("explanation", ""),
        "action": result.get("action", "write_and_run"),
        "cell_type": result.get("cell_type", "code"),
        "iteration": result.get("iteration", 0),
    })


@router.get("/api/agent/tools")
async def get_tools():
    """List all available MCP tools."""
    return JSONResponse({"tools": list_tools(), "count": len(list_tools())})


@router.post("/api/agent/execute")
async def execute_tool_endpoint(request: Request):
    """Execute a specific MCP tool directly."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
        if user is None:
            return JSONResponse(status_code=401, content={"ok": False, "error": "Auth required"})
    finally:
        db.close()

    body = await request.json()
    tool_name = body.get("tool", "")
    args = body.get("args", {})

    result = execute_tool(tool_name, args)
    return JSONResponse(result)


@router.get("/api/agent/health")
async def agent_health():
    """Health check for the agent + MCP server."""
    return JSONResponse({
        "ok": True,
        "mcp_server": "online",
        "tools": len(list_tools()),
        "max_iterations": MAX_ITERATIONS,
    })
