"""LangGraph wiring for the test_case pipeline. Same ThreadPoolExecutor
fan-out pattern as fdd_pipeline/tdd_pipeline/test_design_pipeline's
graph.py, but only two nodes -- there is no classify step (test_design_
pipeline already decided which techniques apply and which scenarios
exist; this pipeline only expands what's already there) and no fan-in
reviewer tier (no technique agent here depends on another's output, so
there is nothing for a reviewer to read across):

    tier1 (10 parallel agents, one per technique) -> assemble (deterministic)
"""
from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import StateGraph, END

from state import TestCaseState
from orchestrator import assemble_final_test_cases
from agents import (
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

TIER1_AGENTS = [
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
    pre-tier state -- every technique agent is independent by design,
    which is what makes this safe to parallelize.

    An agent that exhausts its retries records the failure in its own
    section and the tier carries on, rather than raising out of
    fut.result() and discarding every other technique's finished work."""
    merged_sections = dict(state.get("test_case_sections", {}))
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
                    "test_cases": [],
                    "assumptions_made": [
                        "This technique did not complete; re-run to fill it in."
                    ],
                }
                continue
            merged_sections.update(partial.get("test_case_sections", {}))
            merged_pool.extend(partial.get("assumptions_pool", []))

    if failures:
        print("Tier finished with failures: " + "; ".join(failures), flush=True)

    return {"test_case_sections": merged_sections, "assumptions_pool": merged_pool}


def tier1_node(state: TestCaseState) -> dict:
    """10 agents, parallel -- one per testing technique. All ten always
    run; an agent whose upstream section has zero scenarios short-
    circuits without an LLM call (see each agent's own run())."""
    return _run_parallel(TIER1_AGENTS, state)


def assemble_node(state: TestCaseState) -> dict:
    """Deterministic, no LLM call -- see orchestrator.assemble_final_test_cases."""
    return {"final_document": assemble_final_test_cases(state)}


def build_graph():
    g = StateGraph(TestCaseState)

    g.add_node("tier1", tier1_node)
    g.add_node("assemble", assemble_node)

    g.set_entry_point("tier1")
    g.add_edge("tier1", "assemble")
    g.add_edge("assemble", END)

    return g.compile()
