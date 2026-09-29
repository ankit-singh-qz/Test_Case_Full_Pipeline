"""Section 12 -- Non-Functional Requirements. Tier 4, optional."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """Only produce a target if business_objective or so_that clearly implies a
speed, scale, or retention expectation.

Never invent a specific quantitative figure (a SKU count, requests per
second, number of concurrent users, a percentage) that has no textual
basis in the input -- not even as a flagged assumption. A confident-
looking fabricated number is worse than no number: it will be read as a
real requirement.

If the story implies urgency or scale in general terms but gives no
number ("in real-time", "handle demand fluctuations", "at scale"), set
the corresponding field to null and add an assumption stating that a
stakeholder-defined numeric target is still required -- do not fill the
gap with an industry-standard-sounding default.

Only include a specific number if it is stated in the story, or if you
are citing a widely-recognized fixed standard unrelated to the story's
own scale (e.g. citing that GDPR requires breach notification within 72
hours) -- never a made-up capacity or volume figure.

Output strict JSON with keys: triggered (boolean), performance_target
(string or null), concurrency_note (string or null), retention_note
(string or null), assumptions_made (array). No prose outside the JSON."""


def run(state: dict) -> dict:
    section2 = state.get("sections", {}).get("2", {})
    payload = {
        "business_objective": section2.get("business_objective"),
        "so_that": (section2.get("parsed_clauses") or {}).get("so_that"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "12", "agent12_nfr", result)
