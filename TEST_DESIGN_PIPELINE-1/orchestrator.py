"""Non-LLM control logic: classification signals and final assembly.

Neither function here calls an LLM. classify_test_design derives two cheap
signals (test_depth echoes fdd_tier; has_ui_signal is read from the FDD's
own ui_copy_or_message/accessibility signals) that a couple of downstream
agents use to self-scope -- it never gates which of the 20 agents run
(every technique is always evaluated, even when a technique agent itself
concludes "not applicable, because..."). assemble_final_test_design is
pure string formatting plus a deterministic coverage count -- no model
call, same pattern as fdd_pipeline/orchestrator.py and
tdd_pipeline/orchestrator.py.
"""
import json

SECTION_TITLES = {
    "1": "Document Metadata & Control",
    "2": "Purpose & Scope",
    "3": "Test Basis",
    "4": "Issues in Source Documents",
    "5": "Test Strategy",
    "6": "Test Environment & Data",
    "7": "Field-Level Test Design",
    "8": "Traceability Matrix",
    "9": "Entry, Exit & Suspension Criteria",
    "10": "Next Steps",
    "11": "Positive Testing (PT) Scenarios",
    "12": "Negative Testing (NT) Scenarios",
    "13": "Boundary Testing (BT) Scenarios",
    "14": "Data Validation (DV) Scenarios",
    "15": "Error Handling (EH) Scenarios",
    "16": "Performance Testing (PERF) Scenarios",
    "17": "Security Testing (SEC) Scenarios",
    "18": "Usability Testing (USAB) Scenarios",
    "19": "Accessibility Testing (ACC) Scenarios",
    "20": "Compatibility Testing (COMP) Scenarios",
}

# Document reading order -- deliberately different from computation-tier
# order. Scenario sections (11-20) read right after strategy/environment;
# field-level design, traceability, and closing sections read last, same
# shape as the source sample doc's own structure.
RENDER_ORDER = [
    "1", "2", "3", "4", "5", "6",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "7", "8", "9", "10",
]

SCENARIO_SECTION_IDS = ["11", "12", "13", "14", "15", "16", "17", "18", "19", "20"]


def classify_test_design(fdd_sections: dict, fdd_tier: str) -> dict:
    """test_depth echoes fdd_tier (used only to phrase strategy/soak
    decisions, never to skip an agent). has_ui_signal is read from the
    FDD's own signals -- a non-null ui_copy_or_message on any requirement
    means a person reads that text on a screen (per fdd_pipeline's own
    Agent 4 rule); a triggered localization/compliance section with
    accessibility or localization notes is a secondary signal."""
    section4 = fdd_sections.get("4") or {}
    has_ui_signal = any(
        isinstance(r, dict) and r.get("ui_copy_or_message")
        for r in (section4.get("requirements") or [])
    )
    section10 = fdd_sections.get("10") or {}
    if not has_ui_signal and isinstance(section10, dict) and section10.get("triggered"):
        if section10.get("accessibility_notes") or section10.get("localization_notes"):
            has_ui_signal = True
    return {"test_depth": fdd_tier, "has_ui_signal": has_ui_signal}


def _coverage_summary(test_sections: dict) -> dict:
    counts = {"P1": 0, "P2": 0, "P3": 0}
    per_technique = {}
    for sid in SCENARIO_SECTION_IDS:
        scenarios = (test_sections.get(sid) or {}).get("scenarios") or []
        per_technique[SECTION_TITLES[sid]] = len(scenarios)
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                continue
            priority = scenario.get("priority", "P2")
            counts[priority] = counts.get(priority, 0) + 1
    total = sum(counts.values())
    return {"total": total, "by_priority": counts, "by_technique": per_technique}


def assemble_final_test_design(state: dict) -> str:
    """Deterministic renderer -- no LLM call. Walks test_sections in the
    fixed RENDER_ORDER, skipping a section only if it was never computed,
    and inserts an auto-computed coverage summary right after the cover
    line (mirrors the sample doc's own "Total: NN scenarios (X P1, Y P2,
    Z P3)" line, but computed from the actual generated scenarios instead
    of hand-counted)."""
    test_sections = state.get("test_sections", {})
    lines = ["# Test Case Design Document", ""]
    lines.append(f"*Generated draft -- FDD tier: **{state.get('fdd_tier', 'unknown')}***")
    lines.append("")

    summary = _coverage_summary(test_sections)
    lines.append(
        f"**Test scenario coverage: {summary['total']} scenarios "
        f"({summary['by_priority'].get('P1', 0)} P1, "
        f"{summary['by_priority'].get('P2', 0)} P2, "
        f"{summary['by_priority'].get('P3', 0)} P3)**"
    )
    lines.append("")
    for title, count in summary["by_technique"].items():
        lines.append(f"- {title}: {count} scenarios")
    lines.append("")

    for section_id in RENDER_ORDER:
        data = test_sections.get(section_id)
        title = SECTION_TITLES[section_id]
        if data is None:
            continue
        if data.get("applicable") is False:
            lines.append(f"## {section_id}. {title}")
            lines.append("")
            lines.append(
                "_Not applicable to this feature -- evaluated and excluded by its agent._"
            )
            lines.append("")
            continue

        lines.append(f"## {section_id}. {title}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
