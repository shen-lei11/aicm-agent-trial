"""AICM Stage × Model Benchmark.

Tests each model independently on each pipeline stage with fixed canonical
inputs so scores reflect only that stage's model — not upstream quality.

Outputs:
  - Stage matrix: time + score per model per stage
  - Per-stage winner
  - Recommended multi-model pipeline config

Usage: python benchmark.py
"""
import sys
import io
import time
import json
import importlib
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Models to test — skips any not yet pulled
# ---------------------------------------------------------------------------
MODELS = [
    "qwen2.5-coder:1.5b",   # Micro — fast JSON
    "gemma4:e2b",            # Micro — 128K ctx, function-calling
    "llama3.2:3b",           # Mid — instruction-following
    "qwen2.5:3b",            # Mid — solid all-rounder
    "phi4-mini",             # Mid — high reasoning density
    "qwen3.5:4b",            # High — sweet-spot quality
    "qwen3.5:9b",            # Max — ceiling reasoning
]

DISCOVERY_NOTE = Path("Test_outputs/sample_discovery_note.txt").read_text(encoding="utf-8")

VALID_DECISIONS = {
    "Keep", "Proposed Remove", "Need More Info",
    "Baseline Only", "Manual Review Required",
}

EXPECTED_SCENARIO_KEYS = {
    "scenario_summary", "confirmed_facts", "inferred_facts",
    "unknowns", "dashboard_filter_signals",
}

# ---------------------------------------------------------------------------
# Canonical inputs — fixed so BF and MI scores are model-only, not chained
# ---------------------------------------------------------------------------
CANONICAL_SCENARIO = {
    "scenario_summary": (
        "Mid-size financial services firm deploying a customer-facing AI chatbot "
        "for loan pre-qualification using OpenAI GPT-4 via API. Customer PII and "
        "financial data are processed. No existing AI governance policy in place."
    ),
    "confirmed_facts": {
        "organization_type": "Financial Services",
        "ai_use_case": "Customer-facing chatbot for loan pre-qualification",
        "ai_model_provider": "OpenAI",
        "ai_model": "GPT-4",
        "deployment_method": "API integration",
        "data_types": ["Customer PII", "Financial data"],
        "existing_ai_policy": False,
        "customer_facing": True,
        "employee_count": "500-2000",
    },
    "inferred_facts": {
        "regulatory_exposure": "High — financial data + PII triggers GDPR/CCPA/FCRA",
        "bias_risk": "High — automated credit decisions",
        "third_party_risk": "High — OpenAI API dependency, no self-hosted model",
        "explainability_requirement": "High — regulatory mandates for credit decisions",
    },
    "unknowns": [
        "Audit logging capability",
        "Model output monitoring setup",
        "Human-in-the-loop for edge cases",
        "Data residency requirements",
        "Incident response plan for AI failures",
    ],
    "dashboard_filter_signals": {
        "sector": "Financial Services",
        "deployment_scope": "Customer-Facing",
        "risk_tier": "High",
        "data_sensitivity": "PII + Financial",
        "governance_maturity": "Low",
    },
}

# CANONICAL_FILTERING is generated at runtime from real CSV data — see _build_canonical_inputs()
CANONICAL_FILTERING: dict = {}


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def score_scenario_profile(profile: dict) -> dict:
    if not isinstance(profile, dict):
        return {"valid_json": False, "key_coverage": 0, "score": 0}
    data = profile.get("scenario_profile", profile)
    present = EXPECTED_SCENARIO_KEYS & data.keys()
    key_coverage = len(present) / len(EXPECTED_SCENARIO_KEYS)
    has_unknowns = bool(data.get("unknowns"))
    has_inferred = bool(data.get("inferred_facts"))
    has_summary = bool(data.get("scenario_summary", ""))
    score = round((key_coverage * 50) + (10 if has_unknowns else 0) +
                  (10 if has_inferred else 0) + (10 if has_summary else 0) + 20, 1)
    return {
        "valid_json": True,
        "key_coverage": round(key_coverage * 100),
        "has_unknowns": has_unknowns,
        "has_inferred": has_inferred,
        "has_summary": has_summary,
        "score": min(score, 100),
    }


def score_filtering(result: dict) -> dict:
    decisions = result.get("decisions", [])
    total = len(decisions)
    if total == 0:
        return {"total_controls": 0, "valid_decisions": 0, "validity_pct": 0,
                "decision_spread": {}, "score": 0}
    valid = [d for d in decisions
             if isinstance(d.get("decision"), str) and d.get("decision") in VALID_DECISIONS]
    spread = {}
    for d in decisions:
        dec = d.get("decision", "Unknown")
        spread[dec if isinstance(dec, str) else str(dec)] = spread.get(dec, 0) + 1
    validity_pct = round(len(valid) / total * 100, 1)
    fallback_pct = spread.get("Manual Review Required", 0) / total
    quality_bonus = round((1 - fallback_pct) * 30, 1)
    return {
        "total_controls": total,
        "valid_decisions": len(valid),
        "validity_pct": validity_pct,
        "decision_spread": spread,
        "score": round(min(validity_pct * 0.7 + quality_bonus, 100), 1),
    }


def score_missing_info(gap: dict) -> dict:
    questions = gap.get("client_question_set", [])
    critical = gap.get("critical_missing_information", [])
    q_count = len(questions)
    c_count = len(critical)
    # Quality: each question should have id, question text, decision_impact
    quality_fields = ["question_id", "question", "decision_impact"]
    quality_scores = []
    for q in questions:
        if isinstance(q, dict):
            present = sum(1 for f in quality_fields if q.get(f))
            quality_scores.append(present / len(quality_fields))
    avg_quality = round(sum(quality_scores) / len(quality_scores) * 100) if quality_scores else 0
    # Score: 40 pts for generating questions (capped at 8), 30 for quality, 30 for critical gaps
    q_score = min(40, q_count * 5)
    c_score = min(30, c_count * 10)
    score = round(q_score + (avg_quality * 0.3) + c_score, 1)
    return {
        "questions_generated": q_count,
        "critical_gaps": c_count,
        "question_quality_pct": avg_quality,
        "score": min(score, 100),
    }


# ---------------------------------------------------------------------------
# Canonical input builder — runs IS + BF once with a reference model so
# CANONICAL_SCENARIO and CANONICAL_FILTERING use real AICM control IDs
# ---------------------------------------------------------------------------

def _build_canonical_inputs(ref_model: str):
    """Run IS + BF once with ref_model to produce canonical inputs from real data."""
    global CANONICAL_SCENARIO, CANONICAL_FILTERING

    print(f"\n[Warmup] Building canonical inputs with {ref_model}...", flush=True)
    _switch_model_direct(ref_model)

    import aicm.stages.input_structuring as is_mod
    import aicm.stages.base_filtering as bf_mod
    importlib.reload(is_mod)
    importlib.reload(bf_mod)

    # IS: real discovery note → real scenario profile
    try:
        print(f"  [Warmup] Running Input Structuring...", flush=True)
        t0 = time.time()
        scenario = is_mod.run_input_structuring(DISCOVERY_NOTE, {})
        if isinstance(scenario, dict) and scenario:
            CANONICAL_SCENARIO = scenario
            print(f"  [Warmup] IS done in {round(time.time()-t0,1)}s — canonical scenario built", flush=True)
        else:
            print(f"  [Warmup] IS returned empty — keeping hardcoded canonical scenario", flush=True)
    except Exception as e:
        print(f"  [Warmup] IS failed ({e}) — keeping hardcoded canonical scenario", flush=True)

    # BF: canonical scenario → real control decisions using actual CSV
    try:
        print(f"  [Warmup] Running Base Filtering...", flush=True)
        t0 = time.time()
        filtering = bf_mod.run_base_filtering(CANONICAL_SCENARIO)
        if filtering.get("decisions"):
            CANONICAL_FILTERING = filtering
            n = len(filtering["decisions"])
            print(f"  [Warmup] BF done in {round(time.time()-t0,1)}s — {n} real controls as canonical", flush=True)
        else:
            print(f"  [Warmup] BF returned no decisions — MI stage will use empty filtering", flush=True)
    except Exception as e:
        print(f"  [Warmup] BF failed ({e}) — MI stage will use empty filtering", flush=True)

    print(f"[Warmup] Canonical inputs ready.\n", flush=True)


def _switch_model_direct(model: str):
    import aicm.config as cfg
    import aicm.ollama_client as client_mod
    cfg.MODEL = model
    client_mod.MODEL = model


# ---------------------------------------------------------------------------
# Model switcher
# ---------------------------------------------------------------------------

def _switch_model(model: str):
    _switch_model_direct(model)


def _available_models() -> set[str]:
    """Return set of model names currently pulled in Ollama."""
    try:
        import ollama
        models = ollama.list()
        names = set()
        for m in models.get("models", []):
            name = m.get("name", "") or m.get("model", "")
            names.add(name)
            # also add without digest suffix e.g. "qwen2.5-coder:1.5b"
            if ":" in name:
                names.add(name.split(":")[0] + ":" + name.split(":")[1].split("-")[0])
        return names
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# Per-stage runners (each uses fixed canonical input)
# ---------------------------------------------------------------------------

def run_is(model: str) -> dict:
    """Stage 1: Input Structuring — input: DISCOVERY_NOTE (same for all)."""
    _switch_model(model)
    # Force reimport to pick up model change
    import aicm.stages.input_structuring as mod
    importlib.reload(mod)
    t0 = time.time()
    try:
        profile = mod.run_input_structuring(DISCOVERY_NOTE, {})
        elapsed = round(time.time() - t0, 1)
        return {"elapsed_sec": elapsed, "scores": score_scenario_profile(profile), "raw": profile}
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        return {"elapsed_sec": elapsed, "error": str(e), "scores": {"score": 0}}


def run_bf(model: str) -> dict:
    """Stage 2: Base Filtering — input: CANONICAL_SCENARIO (fixed)."""
    _switch_model(model)
    import aicm.stages.base_filtering as mod
    importlib.reload(mod)
    t0 = time.time()
    try:
        result = mod.run_base_filtering(CANONICAL_SCENARIO)
        elapsed = round(time.time() - t0, 1)
        return {"elapsed_sec": elapsed, "scores": score_filtering(result), "raw": result}
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        return {"elapsed_sec": elapsed, "error": str(e), "scores": {"score": 0, "validity_pct": 0}}


def run_mi(model: str) -> dict:
    """Stage 3: Missing Info — input: CANONICAL_SCENARIO + CANONICAL_FILTERING (fixed)."""
    _switch_model(model)
    import aicm.stages.missing_info as mod
    importlib.reload(mod)
    t0 = time.time()
    try:
        gap = mod.run_missing_info(CANONICAL_SCENARIO, CANONICAL_FILTERING)
        elapsed = round(time.time() - t0, 1)
        return {"elapsed_sec": elapsed, "scores": score_missing_info(gap), "raw": gap}
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        return {"elapsed_sec": elapsed, "error": str(e), "scores": {"score": 0}}


# ---------------------------------------------------------------------------
# Matrix runner
# ---------------------------------------------------------------------------

def run_matrix(models: list[str]) -> list[dict]:
    """Run all three stages for every model, return list of model result dicts."""
    results = []
    for model in models:
        print(f"\n{'='*60}", flush=True)
        print(f"  Testing: {model}", flush=True)
        print(f"{'='*60}", flush=True)

        row = {"model": model, "is": {}, "bf": {}, "mi": {}, "skipped": False}

        print(f"  [IS] Input Structuring...", flush=True)
        row["is"] = run_is(model)
        _log_stage(row["is"], "IS")

        print(f"  [BF] Base Filtering...", flush=True)
        row["bf"] = run_bf(model)
        _log_stage(row["bf"], "BF")

        print(f"  [MI] Missing Info...", flush=True)
        row["mi"] = run_mi(model)
        _log_stage(row["mi"], "MI")

        row["total_elapsed_sec"] = round(
            row["is"].get("elapsed_sec", 0) +
            row["bf"].get("elapsed_sec", 0) +
            row["mi"].get("elapsed_sec", 0), 1
        )
        results.append(row)

    return results


def _log_stage(stage: dict, label: str):
    if "error" in stage:
        print(f"    [{label}] FAILED: {stage['error']}", flush=True)
    else:
        s = stage.get("scores", {})
        print(f"    [{label}] {stage['elapsed_sec']}s  score={s.get('score', '?')}", flush=True)


# ---------------------------------------------------------------------------
# Output printers
# ---------------------------------------------------------------------------

def _fmt(val, suffix=""):
    return f"{val}{suffix}" if val not in (None, "ERR", "") else "ERR"


def print_matrix_table(results: list[dict]):
    W = [20, 9, 9, 9, 9, 9, 9, 9, 10]
    headers = ["Model", "IS(s)", "IS Scr", "BF(s)", "BF Val%", "BF Scr", "MI(s)", "MI Scr", "Total(s)"]
    line = "-" * sum(W)

    print(f"\n{'='*sum(W)}", flush=True)
    print("  STAGE x MODEL MATRIX", flush=True)
    print(f"{'='*sum(W)}", flush=True)
    print("".join(h.ljust(w) for h, w in zip(headers, W)), flush=True)
    print(line, flush=True)

    for r in results:
        is_s = r.get("is", {})
        bf_s = r.get("bf", {})
        mi_s = r.get("mi", {})
        row = [
            r["model"][:19],
            _fmt(is_s.get("elapsed_sec"), "s"),
            _fmt(is_s.get("scores", {}).get("score")),
            _fmt(bf_s.get("elapsed_sec"), "s"),
            _fmt(bf_s.get("scores", {}).get("validity_pct"), "%"),
            _fmt(bf_s.get("scores", {}).get("score")),
            _fmt(mi_s.get("elapsed_sec"), "s"),
            _fmt(mi_s.get("scores", {}).get("score")),
            _fmt(r.get("total_elapsed_sec"), "s"),
        ]
        print("".join(str(v).ljust(w) for v, w in zip(row, W)), flush=True)

    print(f"{'='*sum(W)}", flush=True)
    print("IS=Input Structuring  BF=Base Filtering  MI=Missing Info", flush=True)
    print("Scores: IS=schema coverage+quality  BF=valid%+non-fallback  MI=question quality+critical gaps\n", flush=True)


def print_recommendations(results: list[dict]):
    """Print per-stage winners and recommended mixed pipeline."""
    valid = [r for r in results if not r.get("skipped")]
    if not valid:
        print("No valid results to recommend from.", flush=True)
        return

    def best_for(stage_key: str, score_key: str):
        scored = [(r, r.get(stage_key, {}).get("scores", {}).get(score_key, 0)) for r in valid]
        scored = [(r, s) for r, s in scored if s is not None]
        if not scored:
            return None, 0
        winner = max(scored, key=lambda x: x[1])
        return winner[0]["model"], winner[1]

    def fastest_for(stage_key: str):
        timed = [(r, r.get(stage_key, {}).get("elapsed_sec", 9999)) for r in valid]
        timed = [(r, t) for r, t in timed if "error" not in r.get(stage_key, {})]
        if not timed:
            return None, 0
        winner = min(timed, key=lambda x: x[1])
        return winner[0]["model"], winner[1]

    is_winner, is_score = best_for("is", "score")
    bf_winner, bf_score = best_for("bf", "score")
    mi_winner, mi_score = best_for("mi", "score")

    is_fastest, is_ft = fastest_for("is")
    bf_fastest, bf_ft = fastest_for("bf")
    mi_fastest, mi_ft = fastest_for("mi")

    print(f"\n{'='*60}", flush=True)
    print("  PER-STAGE WINNERS", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Input Structuring  — Best quality: {is_winner} (score {is_score})", flush=True)
    print(f"                       Fastest:       {is_fastest} ({is_ft}s)", flush=True)
    print(f"  Base Filtering     — Best quality: {bf_winner} (score {bf_score})", flush=True)
    print(f"                       Fastest:       {bf_fastest} ({bf_ft}s)", flush=True)
    print(f"  Missing Info       — Best quality: {mi_winner} (score {mi_score})", flush=True)
    print(f"                       Fastest:       {mi_fastest} ({mi_ft}s)", flush=True)

    # Recommended: best quality per stage
    rec_is_t = next((r["is"].get("elapsed_sec", 0) for r in valid if r["model"] == is_winner), 0)
    rec_bf_t = next((r["bf"].get("elapsed_sec", 0) for r in valid if r["model"] == bf_winner), 0)
    rec_mi_t = next((r["mi"].get("elapsed_sec", 0) for r in valid if r["model"] == mi_winner), 0)
    projected = round(rec_is_t + rec_bf_t + rec_mi_t, 1)

    print(f"\n{'='*60}", flush=True)
    print("  RECOMMENDED MULTI-MODEL PIPELINE (best quality)", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Stage 1  Input Structuring : {is_winner} (~{rec_is_t}s)", flush=True)
    print(f"  Stage 2  Base Filtering    : {bf_winner} (~{rec_bf_t}s)", flush=True)
    print(f"  Stage 3  Missing Info      : {mi_winner} (~{rec_mi_t}s)", flush=True)
    print(f"  Projected total per run    : ~{projected}s\n", flush=True)

    # Speed-first alternative (fastest that aren't ERR)
    fast_total = round(is_ft + bf_ft + mi_ft, 1)
    if {is_fastest, bf_fastest, mi_fastest} != {is_winner, bf_winner, mi_winner}:
        print(f"  SPEED-FIRST ALTERNATIVE", flush=True)
        print(f"  Stage 1  Input Structuring : {is_fastest} (~{is_ft}s)", flush=True)
        print(f"  Stage 2  Base Filtering    : {bf_fastest} (~{bf_ft}s)", flush=True)
        print(f"  Stage 3  Missing Info      : {mi_fastest} (~{mi_ft}s)", flush=True)
        print(f"  Projected total per run    : ~{fast_total}s\n", flush=True)


def print_decisions_by_model(results: list[dict]):
    """Print full BF control decisions per model."""
    for r in results:
        model = r["model"]
        decisions = r.get("bf", {}).get("raw", {}).get("decisions", [])
        gaps = r.get("mi", {}).get("raw", {})

        print(f"\n{'='*60}", flush=True)
        print(f"  CONTROL DECISIONS — {model}", flush=True)
        print(f"{'='*60}", flush=True)

        if not decisions:
            print("  No decisions captured.", flush=True)
        else:
            groups = {}
            for d in decisions:
                dec = d.get("decision", "Unknown")
                groups.setdefault(dec, []).append(d)
            order = ["Keep", "Baseline Only", "Need More Info", "Manual Review Required", "Proposed Remove"]
            for dec_type in order:
                items = groups.get(dec_type, [])
                if not items:
                    continue
                print(f"\n  [{dec_type}] ({len(items)})", flush=True)
                for d in items:
                    cid = d.get("control_id", "?")
                    title = d.get("control_title", "")
                    reason = d.get("reason", d.get("missing_dependency", ""))
                    conf = d.get("confidence", "")
                    tag = f" [{conf}]" if conf else ""
                    print(f"    {cid}{tag}  {title}", flush=True)
                    if reason:
                        print(f"      -> {reason}", flush=True)

        questions = gaps.get("client_question_set", []) if gaps else []
        if questions:
            print(f"\n  QUESTIONS GENERATED ({len(questions)}):", flush=True)
            for q in questions:
                print(f"    [{q.get('question_id','?')}] {q.get('question','')}", flush=True)
                print(f"      Impact: {q.get('decision_impact','')}", flush=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\nAICM Stage x Model Benchmark — {datetime.now().strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"Discovery note: {len(DISCOVERY_NOTE)} chars", flush=True)

    # Check which models are actually available
    available = _available_models()
    to_run = []
    skipped = []
    for m in MODELS:
        # Loose match: e.g. "qwen2.5-coder:1.5b" in available
        found = m in available or any(m in a for a in available)
        if found:
            to_run.append(m)
        else:
            skipped.append(m)

    if skipped:
        print(f"\nSkipping (not pulled): {', '.join(skipped)}", flush=True)
    print(f"Running {len(to_run)} models: {', '.join(to_run)}\n", flush=True)

    if not to_run:
        print("No models available. Run: ollama pull <model>", flush=True)
        sys.exit(1)

    # Use the most capable available model as reference for canonical inputs
    ref_preference = ["qwen3.5:4b", "qwen2.5:3b", "llama3.2:3b", "qwen2.5-coder:1.5b"]
    ref_model = next((m for m in ref_preference if m in to_run), to_run[0])
    _build_canonical_inputs(ref_model)

    all_results = run_matrix(to_run)

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"Test_outputs/benchmark_{ts}.json"
    Path(out_path).write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"\nFull results saved to {out_path}", flush=True)

    print_matrix_table(all_results)
    print_recommendations(all_results)
    print_decisions_by_model(all_results)
