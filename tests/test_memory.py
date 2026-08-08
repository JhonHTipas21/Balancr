import pytest
from datetime import datetime
from balancr.canonical import CanonicalTransaction, DiscrepancyCase, DiscrepancyType, ReconciliationStatus
from balancr.memory.store import ReconciliationMemory

def test_memory_add_and_query(tmp_path):
    # Initialize the memory store in a temporary directory
    store = ReconciliationMemory(persist_dir=str(tmp_path))
    
    # Verify count is initially 0
    assert store.collection.count() == 0
    
    # Create a mock resolved discrepancy case
    g_tx = CanonicalTransaction(
        id="gt_1", amount=150.0, currency="USD", date=datetime(2026, 8, 1, 10, 0), reference="REF_123", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="bt_1", amount=-150.0, currency="USD", date=datetime(2026, 8, 3, 10, 0), reference="REF_123", source="bank"
    )
    
    resolved_case = DiscrepancyCase(
        id="case_abc",
        transaction_gateway=g_tx,
        transaction_bank=b_tx,
        status=ReconciliationStatus.MATCHED,
        discrepancy_type=DiscrepancyType.TIMING_MISMATCH,
        explanation="Legitimate delay of 2 days over weekend.",
        resolved_at=datetime(2026, 8, 4, 9, 0)
    )
    
    # Add resolved case to database
    store.add_resolved_case(resolved_case)
    
    # Assert collection count is now 1
    assert store.collection.count() == 1
    
    # Query for similar cases
    similar = store.find_similar_cases("delay of 2 days", n_results=1)
    
    assert len(similar) == 1
    assert similar[0]["discrepancy_type"] == "TIMING_MISMATCH"
    assert "weekend" in similar[0]["explanation"]
    assert similar[0]["gateway_id"] == "gt_1"
    assert similar[0]["bank_id"] == "bt_1"
