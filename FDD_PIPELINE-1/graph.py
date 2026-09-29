"""LangGraph wiring for the FDD pipeline.

Graph nodes correspond to execution TIERS, not individual agents. Each tier
node fans its agents out across threads (these are network-bound LLM calls,
so a ThreadPoolExecutor is enough -- no need for async or multiprocessing)
and merges their results before the next tier starts. This keeps the graph
itself simple and readable while still giving genuine intra-tier
parallelism, and sidesteps LangGraph's more fiddly dynamic fan-in wiring
for a pipeline of this size.

    classify -> tier1 (2 agents) -> tier2 (2) -> tier3 (3)
             -> tier4 (0-5, optional) -> tier5 (1, fan-in) -> assemble
"""
from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import StateGraph, END

from state import StoryState
from orchestrator import classify_and_route, assemble_final_document
from agents import (
    agent1_metadata,
    agent2_executive_summary,
    agent3_conditions,
    agent4_functional_requirements,
    agent5_process_flow,
    agent6_data_fields,
    agent7_dependencies,
    agent8_gaps_assumptions_risks,
    agent9_error_handling,
    agent10_localization_compliance,
    agent11_acceptance_criteria,
    agent12_nfr,
    agent13_transition_cutover,
)

TIER4_AGENTS = {
    "9": agent9_error_handling,
    "10": agent10_localization_compliance,
    "11": agent11_acceptance_criteria,
    "12": agent12_nfr,
    "13": agent13_transition_cutover,
}


def _run_parallel(fns, state: dict) -> dict:
    """Run several agent.run(state) calls concurrently and merge their
    partial state updates into one dict. Each fn receives the SAME
    pre-tier state -- agents in the same tier never see each other's
    output, by design (that's what makes them safe to parallelize)."""
    if not fns:
        return {
            "sections": dict(state.get("sections", {})),
            "assumptions_pool": list(state.get("assumptions_pool", [])),
        }

    merged_sections = dict(state.get("sections", {}))
    merged_pool = list(state.get("assumptions_pool", []))

    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        futures = [pool.submit(fn, state) for fn in fns]
        for fut in futures:
            partial = fut.result()
            merged_sections.update(partial.get("sections", {}))
            merged_pool.extend(partial.get("assumptions_pool", []))

    return {"sections": merged_sections, "assumptions_pool": merged_pool}


def tier1_node(state: StoryState) -> dict:
    """2 agents, parallel: Metadata + Executive Summary."""
    return _run_parallel([agent1_metadata.run, agent2_executive_summary.run], state)


def tier2_node(state: StoryState) -> dict:
    """2 agents, parallel: Pre/Post Conditions + Functional Requirements."""
    return _run_parallel(
        [agent3_conditions.run, agent4_functional_requirements.run], state
    )


def tier3_node(state: StoryState) -> dict:
    """3 agents, parallel: Process Flow + Data Fields + Dependencies."""
    return _run_parallel(
        [agent5_process_flow.run, agent6_data_fields.run, agent7_dependencies.run],
        state,
    )


def tier4_node(state: StoryState) -> dict:
    """0-5 agents, parallel -- only the ones classify_and_route included."""
    included = set(state.get("included_sections", []))
    to_run = [mod.run for sid, mod in TIER4_AGENTS.items() if sid in included]

    result = _run_parallel(to_run, state)

    # Sections that were skipped entirely (not just "triggered: false" from
    # inside the agent, but never invoked at all) get an explicit stub so
    # the assembler can note "considered and excluded" rather than the
    # section simply being missing with no explanation.
    for sid in TIER4_AGENTS:
        if sid not in included:
            result["sections"].setdefault(sid, {"triggered": False})

    return result


def tier5_node(state: StoryState) -> dict:
    """1 agent, solo, always last: Gaps, Assumptions & Risks (fan-in)."""
    return agent8_gaps_assumptions_risks.run(state)


def assemble_node(state: StoryState) -> dict:
    """Deterministic, no LLM call -- see orchestrator.assemble_final_document."""
    return {"final_document": assemble_final_document(state)}


def build_graph():
    g = StateGraph(StoryState)

    g.add_node("classify", classify_and_route)
    g.add_node("tier1", tier1_node)
    g.add_node("tier2", tier2_node)
    g.add_node("tier3", tier3_node)
    g.add_node("tier4", tier4_node)
    g.add_node("tier5", tier5_node)
    g.add_node("assemble", assemble_node)

    g.set_entry_point("classify")
    g.add_edge("classify", "tier1")
    g.add_edge("tier1", "tier2")
    g.add_edge("tier2", "tier3")
    g.add_edge("tier3", "tier4")
    g.add_edge("tier4", "tier5")
    g.add_edge("tier5", "assemble")
    g.add_edge("assemble", END)

    return g.compile()
