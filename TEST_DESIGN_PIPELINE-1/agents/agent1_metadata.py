"""Section 1 -- Document Metadata & Control. Tier 1, always runs."""
from llm import call_agent
from agents.common import CHAR_LIMIT_RULE, merge_section

SYSTEM_PROMPT = """You populate the document-control header for a Test Case Design Document
that sits downstream of an FDD and a TDD.

RULES:
1. document_id: derive from fdd_document_id by appending "-TESTDESIGN"
   (e.g. "FDD-DRAFT-UNASSIGNED" -> "FDD-DRAFT-UNASSIGNED-TESTDESIGN"). If
   fdd_document_id is null, use "TESTDESIGN-DRAFT-UNASSIGNED".
2. version always starts at "v0.1 (Draft)" -- this pipeline never knows
   about prior revisions of the test design itself.
3. source_fdd_id, source_fdd_version, source_tdd_id, source_tdd_version
   are copied verbatim from the inputs. Never invent one that is null in
   the input -- pass null through unchanged.
4. title is copied verbatim from fdd_title. Do not paraphrase it.
5. prepared_by and reviewed_by are always null -- this pipeline has no
   information about who will do either; do not guess a name or role.
6. client_name and module_name are copied verbatim from the inputs.

SELF-CHECK: did you invent any name, date, or ID that was not present in
the input? If so, replace it with null.

Output strict JSON: document_id, version, source_fdd_id,
source_fdd_version, source_tdd_id, source_tdd_version, client_name,
module_name, title, prepared_by, reviewed_by, assumptions_made (array).
JSON only."""


def run(state: dict) -> dict:
    fdd1 = (state.get("fdd_sections") or {}).get("1") or {}
    tdd1 = (state.get("tdd_sections") or {}).get("1") or {}
    payload = {
        "fdd_document_id": fdd1.get("document_id"),
        "fdd_version": fdd1.get("version"),
        "fdd_client_name": fdd1.get("client_name"),
        "fdd_module_name": fdd1.get("module_name"),
        "fdd_title": fdd1.get("title"),
        "tdd_technical_artifact_id": tdd1.get("technical_artifact_id"),
        "tdd_version": tdd1.get("version"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    return merge_section(state, "1", "agent1_metadata", result)
