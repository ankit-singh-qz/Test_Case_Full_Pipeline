"""Non-LLM control logic: deterministic coverage counting and final
assembly. Neither function here calls a model -- same pattern as
fdd_pipeline/orchestrator.py, tdd_pipeline/orchestrator.py, and
test_design_pipeline/orchestrator.py.
"""
import json

from agents.common import as_issue_string

SECTION_TITLES = {
    "11": "Positive Testing (PT)",
    "12": "Negative Testing (NT)",
    "13": "Boundary Testing (BT)",
    "14": "Data Validation (DV)",
    "15": "Error Handling (EH)",
    "16": "Performance Testing (PERF)",
    "17": "Security Testing (SEC)",
    "18": "Usability Testing (USAB)",
    "19": "Accessibility Testing (ACC)",
    "20": "Compatibility Testing (COMP)",
}

SECTION_ORDER = list(SECTION_TITLES.keys())


def compute_coverage_summary(test_case_sections: dict) -> dict:
    """Walks every technique's test_cases and counts execution-ready vs.
    blocked, overall, per technique, and per blocking issue id (so it is
    obvious which open issue blocks the most test cases)."""
    by_technique = {}
    by_blocked_issue = {}
    ready_by_priority = {"P1": 0, "P2": 0, "P3": 0}
    total = 0
    ready = 0
    blocked = 0
    automatable = 0

    for section_id in SECTION_ORDER:
        section = test_case_sections.get(section_id) or {}
        cases = section.get("test_cases") or []
        section_total = len(cases)
        section_ready = 0
        section_blocked = 0

        for case in cases:
            if not isinstance(case, dict):
                continue
            if case.get("status") == "blocked":
                section_blocked += 1
                issue_id = as_issue_string(case.get("blocked_by_issue")) or "UNSPECIFIED"
                by_blocked_issue[issue_id] = by_blocked_issue.get(issue_id, 0) + 1
            else:
                section_ready += 1
                priority = case.get("priority") or "P2"
                ready_by_priority[priority] = ready_by_priority.get(priority, 0) + 1
                if case.get("automatable"):
                    automatable += 1

        by_technique[section_id] = {
            "title": SECTION_TITLES[section_id],
            "total": section_total,
            "ready": section_ready,
            "blocked": section_blocked,
        }
        total += section_total
        ready += section_ready
        blocked += section_blocked

    return {
        "total": total,
        "ready": ready,
        "blocked": blocked,
        "ready_automatable": automatable,
        "ready_by_priority": ready_by_priority,
        "by_technique": by_technique,
        "by_blocked_issue": by_blocked_issue,
    }


def assemble_final_test_cases(state: dict) -> str:
    """Deterministic renderer -- no LLM call. Coverage summary first
    (computed from the actual generated test cases, not hand-counted),
    then one '## <technique>' section per 11-20 in fixed order, each
    listing its test cases as JSON blocks (or an explicit N/A note with
    the carried-forward reason when a technique produced zero cases)."""
    test_case_sections = state.get("test_case_sections", {})
    summary = compute_coverage_summary(test_case_sections)

    lines = ["# Detailed Test Cases", ""]
    lines.append(
        f"**Coverage: {summary['total']} test cases total -- "
        f"{summary['ready']} execution-ready, {summary['blocked']} blocked "
        f"({summary['ready_automatable']} of the ready cases are automatable)**"
    )
    lines.append("")
    lines.append(
        f"Ready by priority: P1 {summary['ready_by_priority'].get('P1', 0)}, "
        f"P2 {summary['ready_by_priority'].get('P2', 0)}, "
        f"P3 {summary['ready_by_priority'].get('P3', 0)}"
    )
    lines.append("")
    for section_id in SECTION_ORDER:
        t = summary["by_technique"][section_id]
        lines.append(f"- {t['title']}: {t['total']} total ({t['ready']} ready, {t['blocked']} blocked)")
    lines.append("")
    if summary["by_blocked_issue"]:
        lines.append("**Blocked test cases by open issue:**")
        lines.append("")
        for issue_id, count in sorted(summary["by_blocked_issue"].items()):
            lines.append(f"- {issue_id}: {count} test case(s)")
        lines.append("")

    for section_id in SECTION_ORDER:
        title = SECTION_TITLES[section_id]
        data = test_case_sections.get(section_id)
        lines.append(f"## {section_id}. {title}")
        lines.append("")

        if data is None:
            lines.append("_This technique was never run._")
            lines.append("")
            continue

        cases = data.get("test_cases") or []
        if not cases:
            lines.append("_No test cases generated for this category._")
            assumptions = data.get("assumptions_made")
            if assumptions:
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps({"assumptions_made": assumptions}, indent=2, ensure_ascii=False))
                lines.append("```")
            lines.append("")
            continue

        lines.append("```json")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
