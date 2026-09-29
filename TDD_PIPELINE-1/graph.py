"""LangGraph wiring for the TDD pipeline. Same pattern as fdd_pipeline/graph.py:
graph nodes are TIERS, each fanning its agents out across threads (network-
bound LLM calls) and merging results before the next tier starts.

    classify -> tier1 (4 agents) -> tier2 (0-8 agents, optional)
             -> tier3 (0-2 agents, optional) -> tier4 (1, fan-in) -> assemble
"""
from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import StateGraph, END

from state import TddState
from orchestrator import classify_tdd_sections, assemble_final_tdd
from agents import (
    agent1_metadata,
    agent2_architecture,
    agent3_tech_stack,
    agent4_data_model,
    agent5_api_contracts,
    agent6_sequence_design,
    agent7_background_jobs,
    agent8_caching,
    agent9_concurrency,
    agent10_async_events,
    agent11_resilience,
    agent12_security,
    agent13_observability,
    agent14_deployment,
    agent15_kill_switch,
    agent16_open_decisions,
)

TIER2_AGENTS = {
    "3": agent3_tech_stack,
    "5": agent5_api_contracts,
    "6": agent6_sequence_design,
    "7": agent7_background_jobs,
    "8": agent8_caching,
    "9": agent9_concurrency,
    "10": agent10_async_events,
    "13": agent13_observability,
    "14": agent14_deployment,
}

TIER3_AGENTS = {
    "11": agent11_resilience,
    "15": agent15_kill_switch,
}


def _run_parallel(fns, state: dict) -> dict:
    """Run several agent.run(state) calls concurrently and merge their
    partial state updates. Each fn receives the SAME pre-tier state."""
    if not fns:
        return {
            "tdd_sections": dict(state.get("tdd_sections", {})),
            "tdd_decisions_pool": list(state.get("tdd_decisions_pool", [])),
        }

    merged_sections = dict(state.get("tdd_sections", {}))
    merged_pool = list(state.get("tdd_decisions_pool", []))

    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        futures = [pool.submit(fn.run, state) for fn in fns]
        for fut in futures:
            partial = fut.result()
            merged_sections.update(partial.get("tdd_sections", {}))
            merged_pool.extend(partial.get("tdd_decisions_pool", []))

    return {"tdd_sections": merged_sections, "tdd_decisions_pool": merged_pool}


def classify_node(state: TddState) -> dict:
    return classify_tdd_sections(state.get("fdd_tier", "medium"), state.get("fdd_sections", {}))


def tier1_node(state: TddState) -> dict:
    """4 agents, always run, parallel: Metadata, Architecture, Data Model, Security."""
    return _run_parallel(
        [agent1_metadata, agent2_architecture, agent4_data_model, agent12_security], state
    )


def tier2_node(state: TddState) -> dict:
    """0-9 agents, parallel -- only the ones the orchestrator included."""
    included = set(state.get("tdd_included_sections", []))
    to_run = [mod for sid, mod in TIER2_AGENTS.items() if sid in included]
    result = _run_parallel(to_run, state)
    for sid in TIER2_AGENTS:
        if sid not in included:
            result["tdd_sections"].setdefault(sid, {"applicable": False})
    return result


def tier3_node(state: TddState) -> dict:
    """0-2 agents, parallel -- Resilience, Kill-Switch."""
    included = set(state.get("tdd_included_sections", []))
    to_run = [mod for sid, mod in TIER3_AGENTS.items() if sid in included]
    result = _run_parallel(to_run, state)
    for sid in TIER3_AGENTS:
        if sid not in included:
            result["tdd_sections"].setdefault(sid, {"applicable": False})
    return result


def tier4_node(state: TddState) -> dict:
    """1 agent, solo, always last: Open Technical Decisions (fan-in)."""
    return agent16_open_decisions.run(state)


def assemble_node(state: TddState) -> dict:
    """Deterministic, no LLM call -- see orchestrator.assemble_final_tdd."""
    return {"final_document": assemble_final_tdd(state)}


def build_graph():
    g = StateGraph(TddState)

    g.add_node("classify", classify_node)
    g.add_node("tier1", tier1_node)
    g.add_node("tier2", tier2_node)
    g.add_node("tier3", tier3_node)
    g.add_node("tier4", tier4_node)
    g.add_node("assemble", assemble_node)

    g.set_entry_point("classify")
    g.add_edge("classify", "tier1")
    g.add_edge("tier1", "tier2")
    g.add_edge("tier2", "tier3")
    g.add_edge("tier3", "tier4")
    g.add_edge("tier4", "assemble")
    g.add_edge("assemble", END)

    return g.compile()
