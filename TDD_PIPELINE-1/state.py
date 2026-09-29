"""Shared state object passed through the TDD LangGraph pipeline.

Deliberately NOT the same StoryState as fdd_pipeline -- this pipeline is
decoupled and never imports from fdd_pipeline. It reads the FDD's finished
output as plain data (fdd_sections), loaded from fdd_state.json by main.py.
"""
from typing import TypedDict, List, Dict, Any, Optional


class Decision(TypedDict):
    source_agent: str
    decision: str


class TddState(TypedDict, total=False):
    raw_user_story: Optional[str]
    fdd_tier: str
    fdd_sections: Dict[str, Any]
    tdd_included_sections: List[str]
    tdd_sections: Dict[str, Any]
    tdd_decisions_pool: List[Decision]
    final_document: str
