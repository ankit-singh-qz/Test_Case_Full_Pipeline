"""Section 11 -- Resilience & Error Recovery, optional/required if FDD Section 9 triggered.
Tier 3 (runs after schema/architecture settle -- no actual data dependency on
Tier 1/2 output, but grouped here to keep resilience/kill-switch decisions
made after the rest of the design is stable)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """RULES:
1. applicable is true if error_matrix or exception_paths is non-empty.
2. Every mechanism must cite the specific fdd_scenario it responds to --
   don't add a generic circuit-breaker entry with no matching FDD scenario.
3. Retry counts, backoff intervals, and thresholds are your engineering
   decisions. Pick reasonable values, state them plainly, and log each one
   in decisions_made as a chosen default -- never imply the FDD dictated a
   specific number it didn't state.

Output strict JSON: applicable (boolean), mechanisms (array of
{fdd_scenario, mechanism, parameters}), decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section9 = fdd.get("9")
    section5 = fdd.get("5") or {}
    payload = {
        "error_matrix": (section9 or {}).get("error_matrix"),
        "exception_paths": section5.get("exception_paths"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "11", "agent11_resilience", result)
