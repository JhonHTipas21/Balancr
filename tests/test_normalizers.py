import pytest
import pandas as pd
from datetime import datetime
from balancr.normalizers.gateway_csv import GatewayCSVSource
from balancr.normalizers.bank_csv import BankCSVSource

def test_gateway_csv_source_success(tmp_path):
    # Create a mock gateway CSV file
    csv_file = tmp_path / "gateway_test.csv"
    data = {
        "transaction_id": ["tx_01", "tx_02"],
        "amount": [150.50, "$3,200.00"],
        "currency": ["usd", "COP"],
        "created_at": ["2026-08-01 10:00:00", "2026-08-02T15:30:00Z"],
        "reference": ["ref_100", "ref_200"]
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)

    source = GatewayCSVSource(str(csv_file))
    txs = source.load_transactions()

    assert len(txs) == 2
    assert txs[0].id == "tx_01"
    assert txs[0].amount == 150.50
    assert txs[0].currency == "USD"
    assert txs[0].reference == "ref_100"
    assert isinstance(txs[0].date, datetime)
    assert txs[0].date.day == 1

    assert txs[1].id == "tx_02"
    assert txs[1].amount == 3200.00
    assert txs[1].currency == "COP"
    assert txs[1].reference == "ref_200"

def test_gateway_csv_source_missing_column(tmp_path):
    csv_file = tmp_path / "gateway_invalid.csv"
    data = {
        "transaction_id": ["tx_01"],
        # "amount" column is missing
        "currency": ["USD"],
        "created_at": ["2026-08-01 10:00:00"],
        "reference": ["ref_100"]
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)

    source = GatewayCSVSource(str(csv_file))
    with pytest.raises(ValueError, match="Required header"):
        source.load_transactions()

def test_bank_csv_source_success(tmp_path):
    csv_file = tmp_path / "bank_test.csv"
    data = {
        "bank_tx_id": ["b_tx_01"],
        "value": ["-150.50"],
        "currency": ["USD"],
        "transaction_date": ["2026-08-03"],
        "bank_reference": ["ref_100"]
    }
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False)

    source = BankCSVSource(str(csv_file))
    txs = source.load_transactions()

    assert len(txs) == 1
    assert txs[0].id == "b_tx_01"
    assert txs[0].amount == -150.50
    assert txs[0].currency == "USD"
    assert txs[0].reference == "ref_100"
    assert txs[0].date.day == 3
