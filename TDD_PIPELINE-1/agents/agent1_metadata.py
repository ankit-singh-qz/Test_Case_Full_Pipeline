"""Sections 0+1 combined -- Metadata & Traceability. Tier 1 (parallel with 2, 4, 12)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You populate ONLY document metadata for a Technical Design Document.

RULES:
1. technical_artifact_id: derive from fdd_document_id (e.g. append "-TDD"
   to the FDD's own ID). If fdd_document_id is a placeholder like
   "FDD-DRAFT-UNASSIGNED", inherit that placeholder pattern -- do not
   invent a real-looking ID where the FDD didn't have one.
2. version is always "v0.1" for a first draft.
3. source_fdd_id and source_fdd_tier are copied verbatim from input.
4. status is always "Draft".

Output strict JSON: technical_artifact_id, version, source_fdd_id,
source_fdd_tier, status, decisions_made (array, normally empty -- this
agent has almost no room to make judgment calls). JSON only."""


def run(state: dict) -> dict:
    fdd_section1 = (state.get("fdd_sections") or {}).get("1") or {}
    payload = {
        "fdd_document_id": fdd_section1.get("document_id"),
        "fdd_tier": state.get("fdd_tier"),
        "raw_user_story": state.get("raw_user_story"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "1", "agent1_metadata", result)
