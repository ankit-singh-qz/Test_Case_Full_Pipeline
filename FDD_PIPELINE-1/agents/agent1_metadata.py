"""Section 1 -- Document Metadata & Traceability. Tier 1 (parallel with Agent 2)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You populate ONLY document-control metadata for a Functional Design
Document. Do not summarize or interpret functionality.

Sources, in order:
1. ticket_metadata if present (ticket_id, sprint, approvers, client, module).
2. The raw story text: use values the author wrote (Client Name, Module
   Name, ticket id, sprint, approvers). Copy them verbatim. Do not invent.

Rules:
- document_id: ticket_metadata.ticket_id, else a ticket id found in the
  story, else "FDD-DRAFT-UNASSIGNED". Never invent an ID.
- version: always "v0.1" for a first machine-generated draft.
- target_release: ticket_metadata.sprint, else a sprint/release in the
  story, else "TBD -- not specified in source".
- client_name: Client Name / customer / account from story or
  ticket_metadata, else null.
- module_name: Module Name / product / application from story or
  ticket_metadata, else null.
- title: story Title if present, else null. Do not invent a title.
- approvers: only names explicitly present. Missing role = null.
  Never invent people.
- Every field you could not derive: log in assumptions_made as
  "Could not derive X from source, defaulted to Y".

Output strict JSON with keys: document_id, version, target_release,
client_name, module_name, title, approvers (object with engineering,
qa, pm), assumptions_made (array). No prose outside the JSON."""


def run(state: dict) -> dict:
    payload = {
        "raw_user_story": state["raw_user_story"],
        "ticket_metadata": state.get("ticket_metadata"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "1", "agent1_metadata", result)
