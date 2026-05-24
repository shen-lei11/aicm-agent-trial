"""File I/O utilities for AICM orchestrator."""
import json
import csv
from pathlib import Path
from datetime import datetime
from aicm.config import DATA_FILES_DIR, TEST_OUTPUTS_DIR


def read_text(file_path: str, max_chars: int = None) -> str:
    """Read text file, optionally truncated to max_chars."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if max_chars and len(content) > max_chars:
        content = content[:max_chars] + "\n[...truncated for context efficiency]"
    return content


def read_csv_rows(file_path: str) -> list[dict]:
    """Read CSV file and return list of dicts."""
    rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def read_json(file_path: str) -> dict:
    """Read JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(file_path: str, data: dict) -> None:
    """Write JSON file."""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_control_lookup() -> dict:
    """Return {control_id: {title, description}} from master controls CSV."""
    path = DATA_FILES_DIR / "aicm_controls_master.csv"
    if not path.exists():
        return {}
    lookup = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("control_id", "").strip()
            if cid:
                lookup[cid] = {
                    "control_title": row.get("control_title", "").strip(),
                    "control_description": row.get("control_specification", "").strip(),
                }
    return lookup


def verify_inventory() -> bool:
    """Verify control inventory files exist."""
    required = [
        DATA_FILES_DIR / "aicm_base_controls_proper.csv",
        DATA_FILES_DIR / "missing_info_question_bank.csv",
    ]
    missing = [str(f) for f in required if not f.exists()]
    if missing:
        print(f"Warning: Missing inventory files: {missing}")
        return False
    return True


def save_iteration(iteration_num: int, data: dict) -> str:
    """Save iteration output to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = TEST_OUTPUTS_DIR / f"run_{iteration_num:03d}_{timestamp}.json"
    write_json(str(filename), data)
    return str(filename)
