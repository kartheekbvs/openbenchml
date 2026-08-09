#!/usr/bin/env python3
"""
OpenBenchML - Development Runner
===================================
Quick start script for local development.
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    print()
    print("=" * 60)
    print("  OpenBenchML v2.0.0 - Development Server")
    print("=" * 60)
    print()
    print("  URL:       http://localhost:8000")
    print("  API Docs:  http://localhost:8000/docs")
    print("  ReDoc:     http://localhost:8000/redoc")
    print("  Health:    http://localhost:8000/health")
    print("  API Info:  http://localhost:8000/api/info")
    print()
    print("  Database:  SQLite (openbenchml.db)")
    print("  Sandbox:   Disabled (models run directly)")
    print("  Rate Limit: Enabled")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app", "templates", "static"],
        log_level="info",
    )
