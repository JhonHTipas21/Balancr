import pytest
from unittest.mock import patch
from datetime import datetime
from balancr.canonical import CanonicalTransaction, DiscrepancyCase, DiscrepancyType, ReconciliationStatus
from balancr.agent import agent_app

@pytest.fixture
def base_date():
    return datetime(2026, 8, 1, 12, 0, 0)

@patch("balancr.agent.graph.call_llm_with_backoff")
def test_agent_graph_execution_timing_mismatch(mock_llm, base_date):
    # Mock LLM to return a valid TIMING_MISMATCH JSON
    mock_llm.return_value = '{"discrepancy_type": "TIMING_MISMATCH", "explanation": "Valid timing delay over weekend."}'
    
    g_tx = CanonicalTransaction(
        id="gt_1", amount=150.0, currency="USD", date=base_date, reference="REF_123", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="bt_1", amount=-150.0, currency="USD", date=base_date, reference="REF_123", source="bank"
    )
    
    anomaly = DiscrepancyCase(
        id="case_1",
        transaction_gateway=g_tx,
        transaction_bank=b_tx,
        status=ReconciliationStatus.DISCREPANCY,
        discrepancy_type=DiscrepancyType.TIMING_MISMATCH,
        explanation="Date difference detected."
    )
    
    initial_state = {
        "anomalies": [anomaly],
        "resolved_cases": [],
        "current_index": 0,
        "memory_matches": [],
        "summary": ""
    }
    
    # Run the LangGraph application
    final_state = agent_app.invoke(initial_state)
    
    assert final_state["current_index"] == 1
    assert len(final_state["resolved_cases"]) == 1
    
    resolved = final_state["resolved_cases"][0]
    assert resolved.id == "case_1"
    assert resolved.discrepancy_type == DiscrepancyType.TIMING_MISMATCH
    assert resolved.status == ReconciliationStatus.MATCHED  # Timing mismatch verified is resolved as MATCHED
    assert resolved.explanation == "Valid timing delay over weekend."
    assert resolved.resolved_at is not None
    
    # Verify mock was called once
    mock_llm.assert_called_once()

@patch("balancr.agent.graph.call_llm_with_backoff")
def test_agent_graph_execution_partial_amount(mock_llm, base_date):
    # Mock LLM to return a PARTIAL_AMOUNT JSON
    mock_llm.return_value = '{"discrepancy_type": "PARTIAL_AMOUNT", "explanation": "Gateway processing fee of 5% applied."}'
    
    g_tx = CanonicalTransaction(
        id="gt_1", amount=100.0, currency="USD", date=base_date, reference="REF_123", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="bt_1", amount=-95.0, currency="USD", date=base_date, reference="REF_123", source="bank"
    )
    
    anomaly = DiscrepancyCase(
        id="case_2",
        transaction_gateway=g_tx,
        transaction_bank=b_tx,
        status=ReconciliationStatus.DISCREPANCY,
        discrepancy_type=DiscrepancyType.PARTIAL_AMOUNT,
        explanation="Amount mismatch."
    )
    
    initial_state = {
        "anomalies": [anomaly],
        "resolved_cases": [],
        "current_index": 0,
        "memory_matches": [],
        "summary": ""
    }
    
    final_state = agent_app.invoke(initial_state)
    
    assert final_state["current_index"] == 1
    assert len(final_state["resolved_cases"]) == 1
    
    resolved = final_state["resolved_cases"][0]
    assert resolved.discrepancy_type == DiscrepancyType.PARTIAL_AMOUNT
    assert resolved.status == ReconciliationStatus.DISCREPANCY  # Partial amount remains DISCREPANCY
    assert resolved.explanation == "Gateway processing fee of 5% applied."
