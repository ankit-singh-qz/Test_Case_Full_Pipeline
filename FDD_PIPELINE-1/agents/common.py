"""Shared helper every agent uses to merge its output back into pipeline state."""


def merge_section(state: dict, section_id: str, agent_name: str, result: dict) -> dict:
    sections = dict(state.get("sections", {}))
    sections[section_id] = result

    pool = list(state.get("assumptions_pool", []))
    for assumption in result.get("assumptions_made", []) or []:
        pool.append({"source_agent": agent_name, "assumption": assumption})

    return {"sections": sections, "assumptions_pool": pool}
