import pytest
from datetime import datetime, timedelta
from balancr.canonical import CanonicalTransaction, DiscrepancyType, ReconciliationStatus
from balancr.matching.engine import ReconciliationEngine

@pytest.fixture
def base_date():
    return datetime(2026, 8, 1, 12, 0, 0)

def test_reconcile_exact_match(base_date):
    engine = ReconciliationEngine(exact_date_tolerance_days=1)
    
    g_tx = CanonicalTransaction(
        id="g_1", amount=150.0, currency="USD", date=base_date, reference="REF_123", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=-150.0, currency="USD", date=base_date, reference="REF_123", source="bank"
    )
    
    matched, discrepancies = engine.reconcile([g_tx], [b_tx])
    
    assert len(matched) == 1
    assert matched[0] == (g_tx, b_tx)
    assert len(discrepancies) == 0

def test_reconcile_timing_mismatch(base_date):
    engine = ReconciliationEngine(exact_date_tolerance_days=1, timing_date_tolerance_days=3)
    
    # 2 days difference -> timing mismatch
    g_tx = CanonicalTransaction(
        id="g_1", amount=150.0, currency="USD", date=base_date, reference="REF_123", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=150.0, currency="USD", date=base_date + timedelta(days=2), reference="REF_123", source="bank"
    )
    
    matched, discrepancies = engine.reconcile([g_tx], [b_tx])
    
    assert len(matched) == 0
    assert len(discrepancies) == 1
    assert discrepancies[0].discrepancy_type == DiscrepancyType.TIMING_MISMATCH
    assert discrepancies[0].status == ReconciliationStatus.DISCREPANCY
    assert "2 days" in discrepancies[0].explanation

def test_reconcile_partial_amount(base_date):
    engine = ReconciliationEngine()
    
    g_tx = CanonicalTransaction(
        id="g_1", amount=150.0, currency="USD", date=base_date, reference="REF_123", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=140.0, currency="USD", date=base_date, reference="REF_123", source="bank"
    )
    
    matched, discrepancies = engine.reconcile([g_tx], [b_tx])
    
    assert len(matched) == 0
    assert len(discrepancies) == 1
    assert discrepancies[0].discrepancy_type == DiscrepancyType.PARTIAL_AMOUNT
    assert "Amount mismatch" in discrepancies[0].explanation

def test_reconcile_duplicates(base_date):
    engine = ReconciliationEngine()
    
    g_tx1 = CanonicalTransaction(
        id="g_1", amount=100.0, currency="USD", date=base_date, reference="DUP_REF", source="gateway"
    )
    g_tx2 = CanonicalTransaction(
        id="g_2", amount=100.0, currency="USD", date=base_date, reference="DUP_REF", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=100.0, currency="USD", date=base_date, reference="DUP_REF", source="bank"
    )
    
    matched, discrepancies = engine.reconcile([g_tx1, g_tx2], [b_tx])
    
    assert len(matched) == 0
    assert len(discrepancies) == 1
    assert discrepancies[0].discrepancy_type == DiscrepancyType.DUPLICATE
    assert "Duplicate references" in discrepancies[0].explanation

def test_reconcile_missing_counterpart(base_date):
    engine = ReconciliationEngine()
    
    g_tx = CanonicalTransaction(
        id="g_1", amount=150.0, currency="USD", date=base_date, reference="ONLY_GATEWAY", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=200.0, currency="USD", date=base_date, reference="ONLY_BANK", source="bank"
    )
    
    matched, discrepancies = engine.reconcile([g_tx], [b_tx])
    
    assert len(matched) == 0
    assert len(discrepancies) == 2
    
    # Check that they are classified as missing counterparts
    disc_types = [d.discrepancy_type for d in discrepancies]
    assert DiscrepancyType.MISSING_COUNTERPART in disc_types
    assert discrepancies[0].status == ReconciliationStatus.UNMATCHED
