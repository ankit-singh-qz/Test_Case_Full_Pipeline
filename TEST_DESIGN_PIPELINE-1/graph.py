"""LangGraph wiring for the test_design pipeline. Same pattern as
fdd_pipeline/graph.py and tdd_pipeline/graph.py: graph nodes are
execution TIERS, each fanning its agents out across threads (network-
bound LLM calls) and merging results before the next tier starts.

    classify -> tier1 (4 agents) -> tier2 (3 agents)
             -> tier3 (10 agents) -> tier4 (2, fan-in)
             -> tier5 (1, solo, fan-in) -> assemble
"""
from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import StateGraph, END

import checkpoint
from state import TestDesignState
from orchestrator import classify_test_design, assemble_final_test_design
from agents import (
    agent1_metadata,
    agent2_purpose_scope,
    agent3_test_basis,
    agent4_issues,
    agent5_test_strategy,
    agent6_test_environment_data,
    agent7_field_level_design,
    agent8_traceability_matrix,
    agent9_entry_exit_criteria,
    agent10_next_steps,
    agent11_positive_testing,
    agent12_negative_testing,
    agent13_boundary_testing,
    agent14_data_validation,
    agent15_error_handling,
    agent16_performance_testing,
    agent17_security_testing,
    agent18_usability_testing,
    agent19_accessibility_testing,
    agent20_compatibility_testing,
)

TIER_STEPS = {
    "tier1": 4,
    "tier2": 3,
    "tier3": 10,
    "tier4": 2,
    "tier5": 1,
}

TIER3_AGENTS = [
    agent11_positive_testing,
    agent12_negative_testing,
    agent13_boundary_testing,
    agent14_data_validation,
    agent15_error_handling,
    agent16_performance_testing,
    agent17_security_testing,
    agent18_usability_testing,
    agent19_accessibility_testing,
    agent20_compatibility_testing,
]


def _section_id_for(fn) -> str:
    """The section number an agent module writes, read off its filename
    (agents/agent13_boundary_testing.py -> "13"). Used only to label a
    failure, so a best-effort parse is enough."""
    name = getattr(fn, "__name__", "").rsplit(".", 1)[-1]
    digits = ""
    for char in name[len("agent") :] if name.startswith("agent") else name:
        if not char.isdigit():
            break
        digits += char
    return digits or name


def _run_parallel(fns, state: dict) -> dict:
    """Run several agent.run(state) calls concurrently and merge their
    partial state updates into one dict. Each fn receives the SAME
    pre-tier state -- agents in the same tier never see each other's
    output, by design (that's what makes them safe to parallelize).

    An agent that exhausts its retries records the failure in its own
    section and the tier carries on. It used to raise straight out of
    fut.result(), which threw away every other call in the run -- up to
    nineteen successful, paid-for responses discarded because the
    twentieth hit a Bedrock outage."""
    if not fns:
        return {
            "test_sections": dict(state.get("test_sections", {})),
            "assumptions_pool": list(state.get("assumptions_pool", [])),
        }

    merged_sections = dict(state.get("test_sections", {}))
    merged_pool = list(state.get("assumptions_pool", []))
    failures = []

    with ThreadPoolExecutor(max_workers=len(fns)) as pool:
        futures = {pool.submit(fn.run, state): fn for fn in fns}
        for fut, fn in futures.items():
            try:
                partial = fut.result()
            except Exception as exc:
                section_id = _section_id_for(fn)
                label = f"{type(exc).__name__}: {exc}"
                failures.append(f"section {section_id} ({label})")
                merged_sections[section_id] = {
                    "error": label,
                    "note": (
                        "This agent did not complete. The section is empty "
                        "rather than absent so the rest of the document still "
                        "assembles; re-run to fill it in."
                    ),
                }
                continue
            merged_sections.update(partial.get("test_sections", {}))
            merged_pool.extend(partial.get("assumptions_pool", []))

    if failures:
        print("Tier finished with failures: " + "; ".join(failures), flush=True)

    return {"test_sections": merged_sections, "assumptions_pool": merged_pool}


def _resumable(tier: str, state: dict, run):
    """Replay a tier from the checkpoint when this run's inputs already
    produced it, otherwise run it and record the result."""
    key = state.get("checkpoint_key") or ""
    done = checkpoint.load(key)
    if tier in done:
        cached = done[tier]
        sections = cached.get("test_sections") or {}
        print(
            f"Resuming: {tier} already completed for these inputs "
            f"({len(sections)} sections); skipping its LLM calls.",
            flush=True,
        )
        for _ in range(TIER_STEPS.get(tier, 0)):
            print("@@DESIGN_STEP", flush=True)
        return cached
    update = run()
    checkpoint.record(key, tier, update)
    return update


def classify_node(state: TestDesignState) -> dict:
    return classify_test_design(state.get("fdd_sections", {}), state.get("fdd_tier", "medium"))


def tier1_node(state: TestDesignState) -> dict:
    """4 agents, always run, parallel: Metadata, Purpose & Scope, Issues,
    Field-Level Design."""
    return _resumable(
        "tier1",
        state,
        lambda: _run_parallel(
            [agent1_metadata, agent2_purpose_scope, agent4_issues, agent7_field_level_design],
            state,
        ),
    )


def tier2_node(state: TestDesignState) -> dict:
    """3 agents, parallel: Test Basis, Test Strategy, Environment & Data."""
    return _resumable(
        "tier2",
        state,
        lambda: _run_parallel(
            [agent3_test_basis, agent5_test_strategy, agent6_test_environment_data],
            state,
        ),
    )


def tier3_node(state: TestDesignState) -> dict:
    """10 agents, parallel -- one per requested testing technique. All
    ten always run; a technique with no basis in the input self-reports
    applicable: false rather than being skipped (same pattern as
    fdd_pipeline's optional agents)."""
    return _resumable("tier3", state, lambda: _run_parallel(TIER3_AGENTS, state))


def tier4_node(state: TestDesignState) -> dict:
    """2 agents, parallel, fan-in from all of tier 3: Traceability
    Matrix, Entry/Exit/Suspension Criteria."""
    return _resumable(
        "tier4",
        state,
        lambda: _run_parallel(
            [agent8_traceability_matrix, agent9_entry_exit_criteria], state
        ),
    )


def tier5_node(state: TestDesignState) -> dict:
    """1 agent, solo, always last: Next Steps -- fan-in reviewer reading
    Agent 8 and Agent 9's finished output, same role as fdd_pipeline's
    Agent 8 / tdd_pipeline's Agent 16."""
    return _resumable(
        "tier5", state, lambda: _run_parallel([agent10_next_steps], state)
    )


def assemble_node(state: TestDesignState) -> dict:
    """Deterministic, no LLM call -- see orchestrator.assemble_final_test_design."""
    return {"final_document": assemble_final_test_design(state)}


def build_graph():
    g = StateGraph(TestDesignState)

    g.add_node("classify", classify_node)
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
