"""Pre-flight Q&A logic for AICM orchestrator."""
from aicm.io_utils import read_csv_rows


PREFLIGHT_QUESTIONS = [
    {
        "id": "Q1",
        "question": "Does the AI system process personal, sensitive, or confidential data?",
        "type": "yes_no",
        "affects_controls": ["DSP", "IAM", "LOG"],
    },
    {
        "id": "Q2",
        "question": "Is the AI system currently in production (vs prototype/pilot)?",
        "type": "yes_no",
        "affects_controls": ["LOG", "BCR", "TVM"],
    },
    {
        "id": "Q3",
        "question": "Does your organization train or fine-tune models (vs only consuming API models)?",
        "type": "yes_no",
        "affects_controls": ["MDS", "DSP"],
    },
]


def ask_preflight_questions_cli() -> dict:
    """Ask preflight questions interactively."""
    answers = {}
    for q in PREFLIGHT_QUESTIONS:
        while True:
            response = input(f"\n{q['question']} (yes/no): ").strip().lower()
            if response in ["yes", "no", "y", "n", "unknown", "u"]:
                answers[q["id"]] = response
                break
            print("Please answer: yes, no, or unknown")
    return answers


def filter_controls_by_preflight(control_data: list[dict], preflight_answers: dict) -> list[dict]:
    """Filter controls based on preflight answers."""
    filtered = []
    for control in control_data:
        control_id = control.get("Control ID", "")

        # If Q1 (data sensitivity) is "no", remove data protection controls
        if preflight_answers.get("Q1") == "no":
            if any(ctrl_id in control_id for ctrl_id in ["DSP"]):
                continue

        # If Q2 (production) is "no", remove production/monitoring controls
        if preflight_answers.get("Q2") == "no":
            if any(ctrl_id in control_id for ctrl_id in ["LOG", "BCR"]):
                continue

        # If Q3 (training) is "no", remove model security controls
        if preflight_answers.get("Q3") == "no":
            if any(ctrl_id in control_id for ctrl_id in ["MDS"]):
                continue

        filtered.append(control)

    return filtered
