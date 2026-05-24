"""Centralized configuration for AICM orchestrator."""
import os
from pathlib import Path

# Root directory
ROOT_DIR = Path(__file__).parent.parent

# Model configuration — global fallback
MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Per-stage model assignment (override global MODEL per agent)
MODEL_INPUT_STRUCTURING = os.getenv("MODEL_IS", "qwen2.5-coder:1.5b")
MODEL_BASE_FILTERING    = os.getenv("MODEL_BF", "llama3.2:3b")
MODEL_MISSING_INFO      = os.getenv("MODEL_MI", "phi4-mini")

# Pipeline configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "3"))
PARALLEL_WORKERS = int(os.getenv("PARALLEL_WORKERS", "2"))

# File paths
DATA_FILES_DIR = ROOT_DIR / "Data_Files"
CONTEXT_FILES_DIR = ROOT_DIR / "Context_FIles"
PROMPT_TEMPLATES_DIR = ROOT_DIR / "Prompt_Templates"
TEST_OUTPUTS_DIR = ROOT_DIR / "Test_outputs"

# Ensure directories exist
for dir_path in [DATA_FILES_DIR, CONTEXT_FILES_DIR, PROMPT_TEMPLATES_DIR, TEST_OUTPUTS_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)
