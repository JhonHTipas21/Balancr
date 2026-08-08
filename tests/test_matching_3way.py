import pytest
from datetime import datetime, timedelta
from balancr.canonical import CanonicalTransaction, DiscrepancyType, ReconciliationStatus
from balancr.matching.engine import ReconciliationEngine

@pytest.fixture
def base_date():
    return datetime(2026, 8, 1, 12, 0, 0)

def test_reconcile_3way_exact_match(base_date):
    engine = ReconciliationEngine(exact_date_tolerance_days=1)
    
    g_tx = CanonicalTransaction(
        id="g_1", amount=100.0, currency="USD", date=base_date, reference="REF_99", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=-100.0, currency="USD", date=base_date, reference="REF_99", source="bank"
    )
    l_tx = CanonicalTransaction(
        id="l_1", amount=100.0, currency="USD", date=base_date, reference="REF_99", source="ledger"
    )
    
    matched, discrepancies = engine.reconcile_3way([g_tx], [b_tx], [l_tx])
    
    assert len(matched) == 1
    assert matched[0] == (g_tx, b_tx, l_tx)
    assert len(discrepancies) == 0

def test_reconcile_3way_timing_mismatch(base_date):
    engine = ReconciliationEngine(exact_date_tolerance_days=1, timing_date_tolerance_days=3)
    
    # 2 days lag on bank -> timing mismatch
    g_tx = CanonicalTransaction(
        id="g_1", amount=100.0, currency="USD", date=base_date, reference="REF_99", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=-100.0, currency="USD", date=base_date + timedelta(days=2), reference="REF_99", source="bank"
    )
    l_tx = CanonicalTransaction(
        id="l_1", amount=100.0, currency="USD", date=base_date, reference="REF_99", source="ledger"
    )
    
    matched, discrepancies = engine.reconcile_3way([g_tx], [b_tx], [l_tx])
    
    assert len(matched) == 0
    assert len(discrepancies) == 1
    assert discrepancies[0].discrepancy_type == DiscrepancyType.TIMING_MISMATCH
    assert "Timing mismatch" in discrepancies[0].explanation

def test_reconcile_3way_partial_amount(base_date):
    engine = ReconciliationEngine()
    
    g_tx = CanonicalTransaction(
        id="g_1", amount=100.0, currency="USD", date=base_date, reference="REF_99", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=-95.0, currency="USD", date=base_date, reference="REF_99", source="bank"
    )
    l_tx = CanonicalTransaction(
        id="l_1", amount=100.0, currency="USD", date=base_date, reference="REF_99", source="ledger"
    )
    
    matched, discrepancies = engine.reconcile_3way([g_tx], [b_tx], [l_tx])
    
    assert len(matched) == 0
    assert len(discrepancies) == 1
    assert discrepancies[0].discrepancy_type == DiscrepancyType.PARTIAL_AMOUNT

def test_reconcile_3way_missing_ledger(base_date):
    engine = ReconciliationEngine()
    
    # Gateway and Bank match, Ledger missing
    g_tx = CanonicalTransaction(
        id="g_1", amount=100.0, currency="USD", date=base_date, reference="REF_99", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=-100.0, currency="USD", date=base_date, reference="REF_99", source="bank"
    )
    
    matched, discrepancies = engine.reconcile_3way([g_tx], [b_tx], [])
    
    assert len(matched) == 0
    assert len(discrepancies) == 1
    assert discrepancies[0].discrepancy_type == DiscrepancyType.MISSING_COUNTERPART
    assert "missing counterpart in Ledger" in discrepancies[0].explanation

def test_reconcile_3way_duplicates(base_date):
    engine = ReconciliationEngine()
    
    g_tx1 = CanonicalTransaction(
        id="g_1", amount=100.0, currency="USD", date=base_date, reference="DUP", source="gateway"
    )
    g_tx2 = CanonicalTransaction(
        id="g_2", amount=100.0, currency="USD", date=base_date, reference="DUP", source="gateway"
    )
    b_tx = CanonicalTransaction(
        id="b_1", amount=-100.0, currency="USD", date=base_date, reference="DUP", source="bank"
    )
    l_tx = CanonicalTransaction(
        id="l_1", amount=100.0, currency="USD", date=base_date, reference="DUP", source="ledger"
    )
    
    matched, discrepancies = engine.reconcile_3way([g_tx1, g_tx2], [b_tx], [l_tx])
    
    assert len(matched) == 0
    assert len(discrepancies) == 1
    assert discrepancies[0].discrepancy_type == DiscrepancyType.DUPLICATE
