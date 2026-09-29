"""Non-LLM control logic: tier classification, routing, and final assembly.

Neither function here calls an LLM -- classification is a cheap rule-based
scan of the story text, and assembly is pure string formatting over the
structured output the 13 agents already produced.
"""
import json
from pathlib import Path

from llm import call_agent
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SECTION_TITLES = {
    "1": "Document Metadata & Traceability",
    "2": "Executive Summary & Intent",
    "3": "Pre-/Post-Conditions",
    "4": "Functional Requirements",
    "5": "Process Flow & Logic States",
    "6": "Data & Field Specifications",
    "7": "Dependencies",
    "8": "Gaps, Assumptions & Risks",
    "9": "Error Handling Matrix",
    "10": "Localization & Compliance",
    "11": "Acceptance Criteria",
    "12": "Non-Functional Requirements",
    "13": "Transition & Cutover",
}


from llm import call_agent

CLASSIFIER_PROMPT = """You classify a single software user story into one of three complexity
tiers, so a downstream generation pipeline knows how many optional
Functional Design Document sections to run. You do not write any FDD
content yourself.

Classify as "small" only if the story is a single field or single-screen
change, with no new data entity, no lifecycle/status implied, no
financial or compliance-sensitive concern, and no explicit real-time or
performance expectation.

Classify as "medium" if the story introduces a new flow, touches 1-2
existing systems, implies an entity with states/statuses, or involves
approval/notification logic -- but has no external third-party
integration and no regulated data.

Classify as "large" if the story: introduces a new subsystem; involves
money, pricing, revenue, or financial calculations; involves PII, health,
or other regulated data; implies compliance/audit requirements; requires
an external third-party integration; or is domain language for a
revenue-, safety-, or compliance-critical system (e.g. airline dynamic
pricing, payments, healthcare, banking) even if it never uses those exact
words.

Do not rely on keyword matching. Read the story's actual functional
weight: a story that implies audit trails, financial calculations, or
regulatory review is "large" regardless of the specific words it uses.

Also decide, independently, whether each of these optional sections
applies to this story:
- needs_error_handling: does the story imply failure modes with real
  consequences (financial loss, compliance violation, data loss)?
- needs_compliance: does the story involve regulated data, multiple
  regions/currencies, or accessibility requirements?
- needs_nfr: does the story state or clearly imply a latency, throughput,
  or scale expectation?
- needs_cutover: only relevant if tier is "large" AND the story implies
  changing how existing data is stored or an existing system's behavior
  (not a purely additive new feature).

Output strict JSON with keys: tier ("small"|"medium"|"large"), reasoning
(one sentence), needs_error_handling (bool), needs_compliance (bool),
needs_nfr (bool), needs_cutover (bool). No prose outside the JSON."""


def classify_and_route(state: dict) -> dict:
    """LLM-based classifier. A rule-based keyword scan missed conceptually
    complex stories that don't happen to use trigger words -- e.g. an
    airline dynamic-pricing story with audit/compliance/real-time
    requirements, classified as "small" because it never said the literal
    word "integration" or "workflow". One classifier call is cheap
    relative to the 13 agents that follow it, and getting the tier wrong
    here cascades into every downstream section. Falls back to a
    deterministic keyword scan if the LLM call itself fails, so a
    transient API error can't silently kill the whole run.
    """
    try:
        result = call_agent(
            CLASSIFIER_PROMPT, {"raw_user_story": state["raw_user_story"]}
        )
        tier = result["tier"]

        included = ["1", "2", "3", "4", "5", "6", "7", "8", "11"]
        if tier in ("medium", "large") or result.get("needs_error_handling"):
            included.append("9")
        if result.get("needs_compliance"):
            included.append("10")
        if result.get("needs_nfr"):
            included.append("12")
        if tier == "large" and result.get("needs_cutover"):
            included.append("13")

        included = sorted(set(included), key=int)
        _announce_fdd_total(included, classifier_counted=True)
        return {"tier": tier, "included_sections": included}

    except Exception:
        return _fallback_classify(state)


def _fallback_classify(state: dict) -> dict:
    """Deterministic keyword scan -- used only if the LLM classifier call
    fails outright (network error, malformed response, etc). Defaults to
    "medium" rather than "small" when no signal is found, since silently
    dropping error handling for a real workflow is a more expensive
    mistake than running one section too many."""
    story = state["raw_user_story"].lower()

    large_signals = [
        "integration", "third-party", "third party", "payment", "pricing",
        "revenue", "credit card", "pii", "personal data", "health",
        "hipaa", "gdpr", "subsystem", "audit", "compliance", "financial",
    ]
    medium_signals = [
        "status", "state", "workflow", "flow", "approve", "reject",
        "notify", "queue", "real-time", "realtime",
    ]

    if any(sig in story for sig in large_signals):
        tier = "large"
    elif any(sig in story for sig in medium_signals):
        tier = "medium"
    else:
        tier = "medium"

    included = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "11"]

    compliance_signals = ["region", "currency", "gdpr", "hipaa", "pci", "accessib", "audit", "compliance"]
    if any(sig in story for sig in compliance_signals):
        included.append("10")

    nfr_signals = ["instant", "real-time", "realtime", "fast", "scale", "concurrent", "latency"]
    if any(sig in story for sig in nfr_signals):
        included.append("12")

    if tier == "large":
        included.append("13")

    included = sorted(set(included), key=int)
    _announce_fdd_total(included, classifier_counted=False)
    return {"tier": tier, "included_sections": included}


def _announce_fdd_total(included: list, classifier_counted: bool) -> None:
    """One line the website reads so the FDD bar can show a real percentage."""
    total = len(included) + (1 if classifier_counted else 0)
    print(f"@@FDD_TOTAL {total}", flush=True)


def assemble_final_document(state: dict) -> str:
    """Deterministic renderer -- no LLM call. Walks state['sections'] in
    fixed numeric document order (1 through 13), skipping any section that
    was never run for this tier, or that a Tier 4 agent itself marked as
    not applicable via triggered: false."""
    lines = ["# Functional Design Document", ""]
    lines.append(f"*Generated draft -- tier: **{state.get('tier', 'unknown')}***")
    lines.append("")

    for section_id in [str(i) for i in range(1, 14)]:
        data = state.get("sections", {}).get(section_id)
        if data is None:
            continue
        if data.get("triggered") is False:
            lines.append(f"## {section_id}. {SECTION_TITLES[section_id]}")
            lines.append("")
            lines.append("_Not applicable to this story -- evaluated and excluded by its agent._")
            lines.append("")
            continue

        lines.append(f"## {section_id}. {SECTION_TITLES[section_id]}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
