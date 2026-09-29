"""Shared helper every TDD agent uses to merge its output back into state.

Mirrors fdd_pipeline/agents/common.py's merge_section exactly, but pools
into tdd_decisions_pool/decision instead of assumptions_pool/assumption --
this pipeline's equivalent concept, just named for what it actually holds
(engineering decisions the FDD didn't dictate, not gaps in the story).
"""


def merge_section(state: dict, section_id: str, agent_name: str, result: dict) -> dict:
    sections = dict(state.get("tdd_sections", {}))
    sections[section_id] = result

    pool = list(state.get("tdd_decisions_pool", []))
    for decision in result.get("decisions_made", []) or []:
        pool.append({"source_agent": agent_name, "decision": decision})

    return {"tdd_sections": sections, "tdd_decisions_pool": pool}
