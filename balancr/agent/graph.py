import json
import re
from datetime import datetime
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from balancr.canonical import DiscrepancyCase, ReconciliationStatus, DiscrepancyType
from balancr.agent.state import AgentState
from balancr.agent.llm import call_llm_with_backoff
from balancr.agent.prompts import CLASSIFICATION_SYSTEM_PROMPT, CLASSIFICATION_USER_TEMPLATE

# Attempt import of memory store helper. If it fails, default to None.
try:
    from balancr.memory.store import get_memory_store
except ImportError:
    get_memory_store = lambda: None

def query_memory(state: AgentState) -> Dict[str, Any]:
    """
    Looks up historical similar cases in ChromaDB to serve as few-shot context.
    """
    idx = state["current_index"]
    anomalies = state["anomalies"]
    if idx >= len(anomalies):
        return {"memory_matches": []}
        
    anomaly = anomalies[idx]
    store = get_memory_store()
    matches = []
    
    if store:
        try:
            # Create a textual representation of the discrepancy to search vector space
            query_str = f"Type: {anomaly.discrepancy_type.value if anomaly.discrepancy_type else ''}. Info: {anomaly.explanation}"
            matches = store.find_similar_cases(query_str, n_results=2)
        except Exception as e:
            print(f"[Memory] Failed to query ChromaDB: {e}")
            
    return {"memory_matches": matches}

def classify_anomaly(state: AgentState) -> Dict[str, Any]:
    """
    Invokes the LLM to classify the current anomaly, parse its output, 
    and update the case record.
    """
    idx = state["current_index"]
    anomalies = state["anomalies"]
    if idx >= len(anomalies):
        return {"current_index": idx + 1}
        
    anomaly = anomalies[idx]
    
    # Format transaction properties for prompt injection
    g_info = "N/A"
    if anomaly.transaction_gateway:
        g_info = (
            f"ID: {anomaly.transaction_gateway.id}\n"
            f"Amount: {anomaly.transaction_gateway.amount} {anomaly.transaction_gateway.currency}\n"
            f"Date: {anomaly.transaction_gateway.date.isoformat()}\n"
            f"Reference: {anomaly.transaction_gateway.reference}"
        )
        
    b_info = "N/A"
    if anomaly.transaction_bank:
        b_info = (
            f"ID: {anomaly.transaction_bank.id}\n"
            f"Amount: {anomaly.transaction_bank.amount} {anomaly.transaction_bank.currency}\n"
            f"Date: {anomaly.transaction_bank.date.isoformat()}\n"
            f"Reference: {anomaly.transaction_bank.reference}"
        )
        
    # Format few-shot historical templates
    hist_list = state.get("memory_matches", [])
    hist_str = "No historical examples found."
    if hist_list:
        hist_parts = []
        for m in hist_list:
            hist_parts.append(
                f"- Case Description: {m.get('explanation', '')}\n"
                f"  Resolution Class: {m.get('discrepancy_type', '')}"
            )
        hist_str = "\n".join(hist_parts)
        
    user_prompt = CLASSIFICATION_USER_TEMPLATE.format(
        case_id=anomaly.id,
        discrepancy_type=anomaly.discrepancy_type.value if anomaly.discrepancy_type else "UNKNOWN",
        explanation=anomaly.explanation or "",
        gateway_info=g_info,
        bank_info=b_info,
        historical_examples=hist_str
    )
    
    messages = [
        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    
    # Safe fallback default values
    final_type = anomaly.discrepancy_type or DiscrepancyType.UNKNOWN
    final_explanation = anomaly.explanation or "Failed to classify via LLM."
    
    try:
        response_text = call_llm_with_backoff(messages)
        # Parse output JSON, stripping any potential markdown code blocks
        clean_text = response_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n", "", clean_text)
            clean_text = re.sub(r"\n```$", "", clean_text)
            
        parsed = json.loads(clean_text)
        type_str = parsed.get("discrepancy_type", "").upper()
        if type_str in DiscrepancyType.__members__:
            final_type = DiscrepancyType[type_str]
        final_explanation = parsed.get("explanation", final_explanation)
    except Exception as e:
        print(f"[Agent] Failed to classify or parse LLM response: {e}. Using fallback values.")
        
    # Standardize output status: timing mismatches verified by LLM are resolved as MATCHED.
    # Other discrepancies are marked as DISCREPANCY.
    resolved_status = ReconciliationStatus.DISCREPANCY
    if final_type == DiscrepancyType.TIMING_MISMATCH:
        resolved_status = ReconciliationStatus.MATCHED
        
    resolved_case = DiscrepancyCase(
        id=anomaly.id,
        transaction_gateway=anomaly.transaction_gateway,
        transaction_bank=anomaly.transaction_bank,
        status=resolved_status,
        discrepancy_type=final_type,
        explanation=final_explanation,
        resolved_at=datetime.now()
    )
    
    resolved_cases = list(state.get("resolved_cases", []))
    resolved_cases.append(resolved_case)
    
    # If the database client is active, add this resolved case to memory to help future runs
    store = get_memory_store()
    if store and resolved_case.status == ReconciliationStatus.MATCHED:
        try:
            store.add_resolved_case(resolved_case)
        except Exception as e:
            print(f"[Memory] Failed to save resolved case: {e}")
            
    return {
        "resolved_cases": resolved_cases,
        "current_index": idx + 1
    }

def should_continue(state: AgentState) -> str:
    """
    Decides whether to process the next anomaly or terminate the loop.
    """
    if state["current_index"] < len(state["anomalies"]):
        return "continue"
    return "end"

# Set up StateGraph
workflow = StateGraph(AgentState)
workflow.add_node("query_memory", query_memory)
workflow.add_node("classify_anomaly", classify_anomaly)

workflow.add_edge(START, "query_memory")
workflow.add_edge("query_memory", "classify_anomaly")
workflow.add_conditional_edges(
    "classify_anomaly",
    should_continue,
    {
        "continue": "query_memory",
        "end": END
    }
)

app = workflow.compile()
