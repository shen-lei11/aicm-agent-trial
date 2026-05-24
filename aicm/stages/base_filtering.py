"""Base filtering stage: parallel map-reduce control filtering."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from aicm.io_utils import read_csv_rows, read_text
from aicm.ollama_client import call_llm, parse_json_safe
from aicm.stages._prompt_utils import split_template
from aicm.config import PROMPT_TEMPLATES_DIR, CONTEXT_FILES_DIR, DATA_FILES_DIR, BATCH_SIZE, PARALLEL_WORKERS, MODEL_BASE_FILTERING

# Correct CSV filename (aicm_base_controls_proper.csv)
CONTROLS_CSV = DATA_FILES_DIR / "aicm_base_controls_proper.csv"


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split list into chunks."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def _load_applicability_rules() -> str:
    path = CONTEXT_FILES_DIR / "control_applicability_rules.md"
    return read_text(str(path), max_chars=1200) if path.exists() else "[control_applicability_rules.md not found]"


def _run_batch(batch_controls: list[dict], scenario_profile: dict, control_applicability_rules: str) -> list[dict]:
    """Process a batch of controls."""
    template_path = PROMPT_TEMPLATES_DIR / "base_filtering_agent_prompt.md"
    if not template_path.exists():
        system_prompt = "You are a security control assessor."
        user_prompt = f"Assess controls: {json.dumps(batch_controls)}"
    else:
        template = read_text(str(template_path))
        system_prompt, user_prompt = split_template(template)
        user_prompt = user_prompt.format(
            scenario_profile=json.dumps(scenario_profile, indent=2),
            controls=json.dumps(batch_controls, indent=2),
            control_applicability_rules=control_applicability_rules,
        )

    response = call_llm(user_prompt, system_prompt, model=MODEL_BASE_FILTERING)

    try:
        decisions = parse_json_safe(response)
        if isinstance(decisions, dict):
            # Accept multiple possible key names the LLM might use
            decisions = (
                decisions.get("decisions")
                or decisions.get("base_control_decisions")
                or decisions.get("controls")
                or decisions.get("results")
                or []
            )
    except Exception:
        decisions = []

    if not decisions:
        # Fallback: mark all as "Needs Clarification"
        decisions = [
            {"control_id": c.get("control_id", "?"), "decision": "Needs Clarification"}
            for c in batch_controls
        ]

    # Defensive completeness check
    if not isinstance(decisions, list):
        decisions = [decisions] if decisions else []

    # Normalise each decision so control_id and decision are always plain strings
    normalised = []
    for d in decisions:
        if not isinstance(d, dict):
            continue
        cid = d.get("control_id", d.get("Control ID", "?"))
        dec = d.get("decision", "Needs Clarification")
        # LLM sometimes returns decision as a nested dict e.g. {"label": "Primary Requirement"}
        if isinstance(dec, dict):
            dec = dec.get("label", dec.get("decision", "Needs Clarification"))
        if isinstance(cid, dict):
            cid = cid.get("id", str(cid))
        d["control_id"] = str(cid)
        d["decision"] = str(dec)
        normalised.append(d)

    control_ids_in_batch = {c.get("control_id", "") for c in batch_controls}
    decision_ids = {d["control_id"] for d in normalised}
    missing_ids = control_ids_in_batch - decision_ids

    for missing_id in missing_ids:
        normalised.append({"control_id": missing_id, "decision": "Needs Clarification"})

    return normalised


def summarize_decisions(all_decisions: list[list[dict]]) -> list[dict]:
    """Reduce step: merge and summarize decisions."""
    merged = {}
    for batch_decisions in all_decisions:
        for decision in batch_decisions:
            if isinstance(decision, dict):
                control_id = decision.get("control_id", "")
                merged[control_id] = decision

    return list(merged.values())


def run_base_filtering(
    scenario_profile: dict, preflight_answers: dict = None
) -> dict:
    """Run base filtering stage with parallel batching."""
    print("\n Base Filtering Agent (parallel)...", flush=True)

    # Load control inventory from correct CSV
    try:
        controls = read_csv_rows(str(CONTROLS_CSV))
    except Exception as e:
        print(f"Warning: Could not load controls from {CONTROLS_CSV}: {e}", flush=True)
        controls = []

    if not controls:
        return {"filtered_controls": [], "total_controls": 0, "decisions": []}

    # Load context file once (shared across all batches)
    control_applicability_rules = _load_applicability_rules()

    # Chunk controls
    batches = chunk_list(controls, BATCH_SIZE)
    print(f"Processing {len(controls)} controls in {len(batches)} batches (size {BATCH_SIZE}, workers {PARALLEL_WORKERS})...", flush=True)

    # Map: Process batches in parallel
    all_decisions = []
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        futures = {
            executor.submit(_run_batch, batch, scenario_profile, control_applicability_rules): i
            for i, batch in enumerate(batches)
        }

        for i, future in enumerate(as_completed(futures)):
            try:
                decisions = future.result()
                all_decisions.append(decisions)
                print(f"  Batch {i + 1}/{len(batches)} done", flush=True)
            except Exception as e:
                print(f"  Batch {i + 1}/{len(batches)} failed: {e}", flush=True)
                all_decisions.append([])

    # Reduce: Summarize decisions
    merged_decisions = summarize_decisions(all_decisions)

    return {
        "filtered_controls": merged_decisions,
        "total_controls": len(controls),
        "decisions": merged_decisions,
    }
