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
    print("=" * 60)
    print("  OpenBenchML - Starting Development Server")
    print("=" * 60)
    print()
    print("  URL: http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("  Health: http://localhost:8000/health")
    print()
    print("  Using SQLite database (no PostgreSQL needed)")
    print("  Docker sandbox: disabled (models run directly)")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app", "templates", "static"],
    )
