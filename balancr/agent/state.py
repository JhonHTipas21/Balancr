from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from balancr.canonical import DiscrepancyCase

class AgentState(TypedDict):
    """
    State definition for the LangGraph agent workflow.
    Tracks state values across all node operations in the graph.
    """
    anomalies: List[DiscrepancyCase]
    resolved_cases: List[DiscrepancyCase]
    current_index: int
    memory_matches: List[Dict[str, Any]]
    summary: str
