"""Non-LLM control logic: which TDD sections apply, and final assembly.

Neither function calls an LLM. classify_tdd_sections reads signals the FDD
pipeline already computed (tier, whether NFR/error-handling/compliance
sections were triggered) -- it does not re-read or re-classify the raw
story. assemble_final_tdd is pure string formatting, same pattern as
fdd_pipeline/orchestrator.py's assemble_final_document.
"""
import json

SECTION_TITLES = {
    "1": "Metadata & Traceability",
    "2": "Component Topology & Architecture",
    "3": "Tech Stack",
    "4": "Data Model & Schema",
    "5": "API & Integration Contracts",
    "6": "Sequence / Interaction Design",
    "7": "Background Jobs & Schedulers",
    "8": "Caching Strategy",
    "9": "Concurrency & Race Condition Handling",
    "10": "Async / Event Contracts",
    "11": "Resilience & Error Recovery",
    "12": "Security Architecture",
    "13": "Observability & Telemetry",
    "14": "Deployment & Rollout Plan",
    "15": "Kill-Switch Implementation",
    "16": "Open Technical Decisions",
}


def classify_tdd_sections(fdd_tier: str, fdd_sections: dict) -> dict:
    """Translate FDD signals into which TDD sections apply. The FDD pipeline
    already did the hard classification work -- this only routes based on
    what it found, and each gated agent re-checks its own trigger condition
    independently (defense in depth, same pattern as the FDD's own
    triggered: false agents)."""
    included = ["1", "2", "4", "12"]  # always required

    section12 = fdd_sections.get("12") or {}
    section9 = fdd_sections.get("9")
    section7 = fdd_sections.get("7") or {}
    section13 = fdd_sections.get("13")

    if fdd_tier in ("medium", "large"):
        included += ["5", "6", "13"]

    if section12.get("triggered"):
        included += ["3", "8"]

    if section9 and section9.get("triggered") is not False:
        included += ["9", "11"]

    if section7.get("external_dependencies"):
        included += ["10"]

    if fdd_tier in ("medium", "large") and section7.get("internal_dependencies"):
        included += ["7"]

    if fdd_tier == "large":
        # included += ["14"]  # Deployment & Rollout stays cut for now
        if section13 and section13.get("triggered") is not False:
            included += ["15"]

    included.append("16")  # always last, always runs

    included = sorted(set(included), key=int)
    print(f"@@TDD_TOTAL {len(included)}", flush=True)
    return {"tdd_included_sections": included}


def assemble_final_tdd(state: dict) -> str:
    """Deterministic renderer -- no LLM call. Walks tdd_sections in fixed
    numeric order, skipping any section not included for this run or that
    an agent itself marked applicable: false."""
    lines = ["# Technical Design Document", ""]
    lines.append(f"*Derived from FDD tier: **{state.get('fdd_tier', 'unknown')}***")
    lines.append("")

    for section_id in [str(i) for i in range(1, 17)]:
        data = state.get("tdd_sections", {}).get(section_id)
        if data is None:
            continue
        if data.get("applicable") is False:
            lines.append(f"## {section_id}. {SECTION_TITLES[section_id]}")
            lines.append("")
            lines.append("_Not applicable -- evaluated and excluded by its agent._")
            lines.append("")
            continue

        lines.append(f"## {section_id}. {SECTION_TITLES[section_id]}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
