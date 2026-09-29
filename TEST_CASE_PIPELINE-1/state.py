"""Shared state object passed through the Test Case LangGraph pipeline.

Decoupled from fdd_pipeline, tdd_pipeline, AND test_design_pipeline -- no
imports from any of them. main.py reads test_design_pipeline's stable
output/test_design_state.json file as plain data; this pipeline never
reads fdd_state.json or tdd_state.json (see README.md for why that's not
needed: test_design_state.json's sections 4/6/7/11-20 already carry every
concrete value -- field examples, data sets, issue text, even inline
quotes of the original FDD/TDD lines -- that expanding a scenario into
step-level test cases requires).
"""
from typing import TypedDict, List, Dict, Any


class TestCaseState(TypedDict, total=False):
    test_design_sections: Dict[str, Any]
    test_case_sections: Dict[str, Any]
    assumptions_pool: List[Dict[str, Any]]
    final_document: str
