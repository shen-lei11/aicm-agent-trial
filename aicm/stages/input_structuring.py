"""Input structuring stage: fold Q&A into discovery note."""
import json
from aicm.io_utils import read_text
from aicm.ollama_client import call_llm, parse_json_safe
from aicm.stages._prompt_utils import split_template
from aicm.config import PROMPT_TEMPLATES_DIR, CONTEXT_FILES_DIR, MODEL_INPUT_STRUCTURING


def build_amended_note(discovery_note: str, preflight_answers: dict) -> str:
    """Build amended discovery note with preflight answers folded in."""
    answer_summary = "\n".join(
        [f"- {ans_id}: {ans_val}" for ans_id, ans_val in preflight_answers.items()]
    )
    amended = f"{discovery_note}\n\n[Preflight Answers]\n{answer_summary}"
    return amended


def run_input_structuring(discovery_note: str, preflight_answers: dict) -> dict:
    """Run input structuring stage."""
    print("\n Input Structuring Agent...", flush=True)

    amended_note = build_amended_note(discovery_note, preflight_answers)

    template_path = PROMPT_TEMPLATES_DIR / "input_structuring_agent_prompt.md"
    if not template_path.exists():
        system_prompt = "You are an AI governance expert structuring discovery note data."
        user_prompt = f"Parse and structure this discovery note:\n\n{amended_note}"
    else:
        template = read_text(str(template_path))
        system_prompt, user_prompt = split_template(template)

        # Load required context files — truncated to keep within num_ctx limit
        scenario_taxonomy = _load_context("scenario_taxonomy.md", max_chars=1200)
        dashboard_filter_mapping = _load_context("dashboard_filter_mapping.md", max_chars=1200)

        user_prompt = user_prompt.format(
            discovery_note=amended_note,
            scenario_taxonomy=scenario_taxonomy,
            dashboard_filter_mapping=dashboard_filter_mapping,
        )

    response = call_llm(user_prompt, system_prompt, model=MODEL_INPUT_STRUCTURING)

    try:
        scenario_profile = parse_json_safe(response)
    except Exception:
        scenario_profile = {
            "scenario_summary": amended_note,
            "confirmed_facts": {"discovery_note": amended_note},
            "inferred_facts": {},
            "unknowns": [],
        }

    return scenario_profile


def _load_context(filename: str, max_chars: int = None) -> str:
    """Load a context file, returning empty string if missing."""
    path = CONTEXT_FILES_DIR / filename
    if path.exists():
        return read_text(str(path), max_chars=max_chars)
    return f"[{filename} not found]"
