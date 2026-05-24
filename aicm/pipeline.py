"""Pipeline orchestrator for AICM workflow."""
import json
import threading
from typing import Optional
from aicm.io_utils import read_text, write_json, load_control_lookup
from aicm.preflight import (
    ask_preflight_questions_cli,
    filter_controls_by_preflight,
    PREFLIGHT_QUESTIONS,
)
from aicm.stages.input_structuring import run_input_structuring
from aicm.stages.base_filtering import run_base_filtering
from aicm.stages.missing_info import run_missing_info, filter_unasked


class PipelineSession:
    """Pipeline session with pause/resume support for web UI."""

    _registry = {}

    def __init__(self, session_id: str, discovery_note: str):
        self.session_id = session_id
        self.discovery_note = discovery_note
        self.preflight_answers = {}
        self.scenario_profile = {}
        self.filtered_controls = {}
        self.gap_analysis = {}
        self.pending_questions = []
        self.state = "preflight_questions"  # or: waiting_for_answers, running, complete
        self.pause_event = threading.Event()
        self.pause_event.set()  # Start in "running" state
        self.result = None
        PipelineSession._registry[session_id] = self

    @classmethod
    def get(cls, session_id: str) -> Optional["PipelineSession"]:
        """Retrieve session by ID."""
        return cls._registry.get(session_id)

    def set_state(self, state: str) -> None:
        """Update pipeline state."""
        self.state = state

    def pause(self) -> None:
        """Pause pipeline."""
        self.pause_event.clear()

    def resume(self) -> None:
        """Resume pipeline."""
        self.pause_event.set()

    def wait_if_paused(self) -> None:
        """Block if paused."""
        self.pause_event.wait()

    def get_snapshot(self) -> dict:
        """Get current state snapshot."""
        return {
            "state": self.state,
            "preflight_answers": self.preflight_answers,
            "pending_questions": self.pending_questions,
            "result": self.result,
        }


def _normalise_id(cid: str, lookup: dict) -> str | None:
    """Return the canonical control_id from lookup, trying common LLM prefixes."""
    if cid in lookup:
        return cid
    # Strip common hallucinated prefixes: "AICM-", "AICM_"
    for prefix in ("AICM-", "AICM_"):
        stripped = cid[len(prefix):] if cid.upper().startswith(prefix) else None
        if stripped and stripped in lookup:
            return stripped
    # Case-insensitive fallback
    upper = {k.upper(): k for k in lookup}
    return upper.get(cid.upper())


def _enrich_decisions(filtered_controls: dict) -> None:
    """Overwrite control_id, control_title and add control_description from master CSV."""
    lookup = load_control_lookup()
    if not lookup:
        return
    for d in filtered_controls.get("decisions", []):
        cid = d.get("control_id", "")
        canonical = _normalise_id(cid, lookup)
        if canonical:
            d["control_id"] = canonical          # fix hallucinated prefix
            d["control_title"] = lookup[canonical]["control_title"]
            d["control_description"] = lookup[canonical]["control_description"]


def run_pipeline_cli(discovery_note: str) -> dict:
    """Run full pipeline in CLI mode."""
    print("AICM Pipeline (CLI Mode)")

    # Pre-flight Q&A
    print("\nPre-flight Q&A:")
    preflight_answers = ask_preflight_questions_cli()

    # Input Structuring
    scenario_profile = run_input_structuring(discovery_note, preflight_answers)
    print("Scenario profile created")

    # Base Filtering
    filtered_controls = run_base_filtering(scenario_profile, preflight_answers)
    _enrich_decisions(filtered_controls)
    print(f"{len(filtered_controls.get('decisions', []))} controls assessed")

    # Missing Info Check
    gap_analysis = run_missing_info(
        scenario_profile,
        base_filtering_output=filtered_controls,
        historical_log=[],
    )
    critical_gaps = gap_analysis.get("critical_missing_information", [])
    if critical_gaps:
        print(f"\n{len(critical_gaps)} critical information gap(s) found")
        for gap in critical_gaps:
            print(f"  - {gap.get('missing_information', '?')}")

        questions = gap_analysis.get("client_question_set", [])
        print(f"\nPlease provide answers to {len(questions)} question(s):")
        for q in questions:
            answer = input(f"\n{q.get('question', '?')}: ").strip()

    return {
        "preflight_answers": preflight_answers,
        "scenario_profile": scenario_profile,
        "filtered_controls": filtered_controls,
        "gap_analysis": gap_analysis,
    }


def run_pipeline_bg(session: PipelineSession) -> None:
    """Run pipeline in background for web UI."""
    try:
        session.set_state("input_structuring")

        # Input Structuring
        session.scenario_profile = run_input_structuring(
            session.discovery_note, session.preflight_answers
        )

        session.set_state("base_filtering")

        # Base Filtering
        session.filtered_controls = run_base_filtering(
            session.scenario_profile, session.preflight_answers
        )
        _enrich_decisions(session.filtered_controls)

        session.set_state("missing_info_check")

        # Missing Info — pass base filtering output and historical log
        gap_analysis = run_missing_info(
            session.scenario_profile,
            base_filtering_output=session.filtered_controls,
            historical_log=session.gap_analysis.get("client_question_set", []),
        )
        session.gap_analysis = gap_analysis

        # Questions are surfaced in results — no mid-run pause
        session.pending_questions = gap_analysis.get("client_question_set", [])

        session.result = {
            "preflight_answers": session.preflight_answers,
            "scenario_profile": session.scenario_profile,
            "filtered_controls": session.filtered_controls,
            "gap_analysis": session.gap_analysis,
        }
        session.set_state("complete")  # set last so result is always ready when polled

    except Exception as e:
        print(f"Pipeline error: {e}", flush=True)
        session.result = {"error": str(e)}
        session.set_state("complete")
