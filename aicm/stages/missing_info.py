"""Missing info stage: identify critical information gaps."""
import json
from aicm.io_utils import read_text, read_csv_rows
from aicm.ollama_client import call_llm, parse_json_safe
from aicm.stages._prompt_utils import split_template
from aicm.config import PROMPT_TEMPLATES_DIR, CONTEXT_FILES_DIR, DATA_FILES_DIR, MODEL_MISSING_INFO


def _load_question_bank() -> str:
    """Load missing_info_question_bank.csv as formatted text."""
    path = DATA_FILES_DIR / "missing_info_question_bank.csv"
    if not path.exists():
        return "[missing_info_question_bank.csv not found]"
    rows = read_csv_rows(str(path))
    lines = []
    for r in rows:
        lines.append(
            f"- [{r.get('question_id','')}] {r.get('question','')} "
            f"(affects: {r.get('affected_domains','')}, criticality: {r.get('criticality','')})"
        )
    # Truncate to keep within context window
    full = "\n".join(lines)
    return full[:1200] + "\n[...truncated]" if len(full) > 1200 else full


def run_missing_info(
    scenario_profile: dict,
    base_filtering_output: dict = None,
    historical_log: list = None,
) -> dict:
    """Run missing info gap check stage."""
    print("\n Missing Info Gap Check Agent...", flush=True)

    if base_filtering_output is None:
        base_filtering_output = {}
    if historical_log is None:
        historical_log = []

    template_path = PROMPT_TEMPLATES_DIR / "missing_info_and _coverage_prompt.md"
    if not template_path.exists():
        system_prompt = "You are a security risk assessment expert identifying critical information gaps."
        user_prompt = (
            f"Identify critical missing information in:\n\n{json.dumps(scenario_profile)}\n\n"
            f"Base filtering output:\n{json.dumps(base_filtering_output)}"
        )
    else:
        template = read_text(str(template_path))
        system_prompt, user_prompt = split_template(template)

        missing_info_question_bank = _load_question_bank()

        user_prompt = user_prompt.format(
            scenario_profile=json.dumps(scenario_profile, indent=2),
            base_filtering_output=json.dumps(base_filtering_output, indent=2),
            historical_log=json.dumps(historical_log, indent=2),
            missing_info_question_bank=missing_info_question_bank,
        )

    response = call_llm(user_prompt, system_prompt, model=MODEL_MISSING_INFO)

    try:
        gap_analysis = parse_json_safe(response)
    except Exception:
        gap_analysis = {
            "critical_missing_information": [],
            "non_critical_missing_information": [],
            "client_question_set": [],
            "workflow_state": {"can_proceed_to_validation": False, "loop_required": True},
        }

    # Ensure every NMI control has at least one question (fallback if LLM missed any)
    _ensure_nmi_coverage(gap_analysis, base_filtering_output)

    can_proceed = len(gap_analysis.get("critical_missing_information", [])) == 0
    gap_analysis["workflow_state"] = {
        "current_step": "missing_info_gap_check",
        "can_proceed_to_validation": can_proceed,
        "loop_required": not can_proceed,
    }

    return gap_analysis


def _ensure_nmi_coverage(gap_analysis: dict, base_filtering_output: dict) -> None:
    """For every NMI control not already covered, add a fallback question."""
    decisions = base_filtering_output.get("decisions", [])
    nmi_controls = [
        d for d in decisions if d.get("decision") == "Needs Clarification"
    ]
    if not nmi_controls:
        return

    existing_qs = gap_analysis.setdefault("client_question_set", [])

    # Build set of control IDs already covered by existing questions
    covered = set()
    for q in existing_qs:
        for ctrl in q.get("affected_controls_or_domains", []):
            covered.add(ctrl)

    for d in nmi_controls:
        cid = d.get("control_id", "")
        title = d.get("control_title", cid)

        def _str(val):
            if isinstance(val, list):
                return "; ".join(str(v) for v in val if v)
            return str(val) if val else ""

        missing = _str(d.get("missing_dependency")).strip()
        reason = _str(d.get("reason")).strip()

        if cid not in covered:
            # Build specific question from whatever the model flagged as missing
            if missing:
                question_text = (
                    f"For {cid} – {title}: the agent flagged a missing dependency: "
                    f'"{missing}". Can you clarify this for your environment?'
                )
            elif reason:
                question_text = (
                    f"For {cid} – {title}: {reason} "
                    f"Please provide the missing details so a decision can be made."
                )
            else:
                question_text = (
                    f"For {cid} – {title}: what additional context can you provide "
                    f"to determine whether this control applies to your environment?"
                )

            existing_qs.append({
                "question_id": f"Q_NMI_{cid.replace('-', '_')}_AUTO",
                "source": "nmi_control",
                "question": question_text,
                "expected_answer_type": "Free text",
                "decision_impact": f"Answer will determine whether {cid} is Primary Requirement, Secondary Recommendation, or Not Applicable.",
                "affected_controls_or_domains": [cid],
            })
            covered.add(cid)

    # If any NMI controls exist, mark as needing answers
    if nmi_controls and not gap_analysis.get("critical_missing_information"):
        gap_analysis.setdefault("critical_missing_information", []).append({
            "missing_information": f"{len(nmi_controls)} controls require clarification before a decision can be made.",
            "criticality": "High",
            "affected_controls": [d.get("control_id") for d in nmi_controls],
        })


def filter_unasked(gap_analysis: dict) -> list[dict]:
    """Extract questions to ask user."""
    return gap_analysis.get("client_question_set", [])
