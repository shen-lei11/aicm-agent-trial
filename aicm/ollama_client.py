"""Ollama client for AICM orchestrator."""
import subprocess
import json
import sys
from pathlib import Path
import time
from aicm.config import MODEL, OLLAMA_HOST


def find_ollama_exe() -> str:
    """Find ollama.exe location."""
    # Try common paths
    possible_paths = [
        Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
        Path("C:") / "Program Files" / "Ollama" / "ollama.exe",
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    return "ollama"  # fallback to PATH lookup


def ensure_ollama_running(max_retries: int = 5) -> bool:
    """Ensure Ollama is running and accessible."""
    ollama_exe = find_ollama_exe()

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                [ollama_exe, "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                print(f"✓ Ollama is running with model: {MODEL}")
                return True
        except Exception:
            pass

        if attempt < max_retries - 1:
            print(f"⏳ Waiting for Ollama... (attempt {attempt + 1}/{max_retries})")
            time.sleep(2)

    print("✗ Ollama not accessible")
    return False


def call_llm(
    prompt: str,
    system_prompt: str = None,
    model: str = None,
    response_format: str = None,
) -> str:
    """Call LLM via Ollama."""
    if model is None:
        model = MODEL

    try:
        import ollama

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        prompt_chars = len(prompt) + len(system_prompt or "")
        print(f"    [LLM] Calling {model} ({prompt_chars} chars)...", flush=True)
        t0 = time.time()

        resp = ollama.chat(
            model=model,
            messages=messages,
            stream=False,
            options={
                "temperature": 0.0,
                "num_ctx": 2048,
                "num_predict": 1024,
                "low_vram": True,
            },
        )

        elapsed = round(time.time() - t0, 1)
        msg = getattr(resp, "message", None) or resp.get("message")
        content = getattr(msg, "content", None) or msg.get("content")
        print(f"    [LLM] Response in {elapsed}s ({len(content or '')} chars)", flush=True)
        return content
    except Exception as e:
        print(f"    [LLM] FAILED: {e}", flush=True)
        raise


def parse_json_safe(text: str) -> dict:
    """Parse JSON from text, handling fence markers."""
    # Strip markdown fences
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from: {text[:100]}")
