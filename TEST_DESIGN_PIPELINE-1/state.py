"""Shared state object passed through the LangGraph pipeline for
test_design_pipeline.

Deliberately NOT shared with fdd_pipeline/tdd_pipeline -- this pipeline is
decoupled and never imports from either. It reads their finished JSON
output as plain data (fdd_sections, tdd_sections), loaded from disk by
main.py.
"""
from typing import TypedDict, List, Dict, Any, Optional


class Assumption(TypedDict):
    source_agent: str
    assumption: str


class TestDesignState(TypedDict, total=False):
    fdd_tier: str
    fdd_sections: Dict[str, Any]
    tdd_included_sections: List[str]
    tdd_sections: Dict[str, Any]
    # Identifies this combination of input files so a killed run can
    # replay its finished tiers instead of paying for them again.
    checkpoint_key: str
    test_depth: str
    has_ui_signal: bool
    test_sections: Dict[str, Any]
    assumptions_pool: List[Assumption]
    final_document: str
