"""FastAPI backend for AICM web UI."""
import sys
import io
import threading
import uuid

# Force UTF-8 stdout/stderr so emoji in log lines don't crash on Windows cp1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from aicm.io_utils import verify_inventory
from aicm.ollama_client import ensure_ollama_running
from aicm.pipeline import PipelineSession, run_pipeline_bg
from aicm.config import MODEL, MODEL_INPUT_STRUCTURING, MODEL_BASE_FILTERING, MODEL_MISSING_INFO


app = FastAPI(title="AICM Orchestrator")


# Lifespan hook for startup
@app.on_event("startup")
async def startup():
    """Verify dependencies on startup."""
    print(f"Pipeline models:", flush=True)
    print(f"  Stage 1 Input Structuring : {MODEL_INPUT_STRUCTURING}", flush=True)
    print(f"  Stage 2 Base Filtering    : {MODEL_BASE_FILTERING}", flush=True)
    print(f"  Stage 3 Missing Info      : {MODEL_MISSING_INFO}", flush=True)
    if not verify_inventory():
        print("WARNING: Inventory verification failed", flush=True)
    if not ensure_ollama_running():
        print("WARNING: Ollama not accessible", flush=True)


# Static files (web UI)
@app.get("/")
async def root():
    """Serve index.html."""
    return FileResponse("web/index.html")


app.mount("/static", StaticFiles(directory="web"), name="static")


# API Models
class StartRequest(BaseModel):
    discovery_note: str


class AnswersRequest(BaseModel):
    answers: dict


class ConfigResponse(BaseModel):
    model: str
    model_input_structuring: str
    model_base_filtering: str
    model_missing_info: str
    session_registry_size: int


# API Endpoints
@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    return ConfigResponse(
        model=MODEL,
        model_input_structuring=MODEL_INPUT_STRUCTURING,
        model_base_filtering=MODEL_BASE_FILTERING,
        model_missing_info=MODEL_MISSING_INFO,
        session_registry_size=len(PipelineSession._registry),
    )


@app.post("/api/start")
async def start_pipeline(request: StartRequest):
    """Start a new pipeline session."""
    session_id = str(uuid.uuid4())
    session = PipelineSession(session_id, request.discovery_note)

    # Start background thread
    thread = threading.Thread(target=run_pipeline_bg, args=(session,), daemon=True)
    thread.start()

    return {"session_id": session_id, "status": "started"}


@app.get("/api/status/{session_id}")
async def get_status(session_id: str):
    """Get current session status."""
    session = PipelineSession.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.get_snapshot()


@app.post("/api/answer/{session_id}")
async def submit_answers(session_id: str, request: AnswersRequest):
    """Submit answers to pending questions."""
    session = PipelineSession.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Store answers and resume
    session.preflight_answers.update(request.answers)
    session.resume()

    return {"status": "answers_received"}


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    """Get final pipeline result."""
    session = PipelineSession.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.state != "complete":
        raise HTTPException(status_code=202, detail="Pipeline still running")

    return session.result


if __name__ == "__main__":
    import uvicorn
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
