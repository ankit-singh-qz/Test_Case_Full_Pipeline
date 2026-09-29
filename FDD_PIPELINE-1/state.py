"""Shared state object passed through the LangGraph pipeline."""
from typing import TypedDict, List, Dict, Any, Optional


class Assumption(TypedDict):
    source_agent: str
    assumption: str


class StoryState(TypedDict, total=False):
    raw_user_story: str
    ticket_metadata: Optional[dict]
    tier: str
    included_sections: List[str]
    sections: Dict[str, Any]
    assumptions_pool: List[Assumption]
    final_document: str
