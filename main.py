"""AICM Orchestrator - entry point. Starts the web server."""
import sys
import io
import os

# Fix Windows cp1252 encoding so emoji in logs don't crash
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

if __name__ == "__main__":
    import uvicorn
    from aicm.config import MODEL_INPUT_STRUCTURING, MODEL_BASE_FILTERING, MODEL_MISSING_INFO

    print("AICM Orchestrator starting...")
    print(f"  Stage 1 Input Structuring : {MODEL_INPUT_STRUCTURING}")
    print(f"  Stage 2 Base Filtering    : {MODEL_BASE_FILTERING}")
    print(f"  Stage 3 Missing Info      : {MODEL_MISSING_INFO}")
    print("\nOpen http://localhost:8000 in your browser")
    print("Press Ctrl+C to stop\n")

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
