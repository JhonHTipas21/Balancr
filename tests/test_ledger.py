import pytest
import pandas as pd
from datetime import datetime
from balancr.normalizers.ledger_db import LedgerDBSource

def test_ledger_csv_source_success(tmp_path):
    csv_file = tmp_path / "ledger_test.csv"
    data = {
        "ledger_tx_id": ["ld_01", "ld_02"],
        "amount": [120.00, "$4,500.50"],
        "currency": ["usd", "COP"],
        "recorded_at": ["2026-08-01 10:00:00", "2026-08-02 11:30:00"],
        "order_reference": ["ref_300", "ref_400"]
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)

    source = LedgerDBSource(str(csv_file))
    txs = source.load_transactions()

    assert len(txs) == 2
    assert txs[0].id == "ld_01"
    assert txs[0].amount == 120.00
    assert txs[0].currency == "USD"
    assert txs[0].reference == "ref_300"
    assert isinstance(txs[0].date, datetime)
    assert txs[0].date.day == 1

    assert txs[1].id == "ld_02"
    assert txs[1].amount == 4500.50
    assert txs[1].currency == "COP"
    assert txs[1].reference == "ref_400"

def test_ledger_csv_source_missing_column(tmp_path):
    csv_file = tmp_path / "ledger_invalid.csv"
    data = {
        "ledger_tx_id": ["ld_01"],
        "currency": ["USD"],
        "recorded_at": ["2026-08-01 10:00:00"],
        "order_reference": ["ref_300"]
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)

    source = LedgerDBSource(str(csv_file))
    with pytest.raises(ValueError, match="Required header"):
        source.load_transactions()
