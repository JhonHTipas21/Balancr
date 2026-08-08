import pytest
from fastapi.testclient import TestClient
from balancr.api.app import app
from balancr.canonical import DiscrepancyType
import json
import io

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_get_cases_empty():
    response = client.get("/api/cases")
    assert response.status_code == 200
    assert response.json() == []

def test_reconcile_endpoint():
    # Create dummy CSV data for testing
    gateway_csv = "transaction_id,amount,currency,created_at,reference\ng1,100,USD,2023-01-01,REF1\n"
    bank_csv = "bank_tx_id,value,currency,transaction_date,bank_reference\nb1,-100,USD,2023-01-01,REF1\n"
    ledger_csv = "ledger_tx_id,amount,currency,recorded_at,order_reference\nl1,100,USD,2023-01-01,REF1\n"

    response = client.post(
        "/api/reconcile",
        files={
            "gateway_file": ("gateway.csv", io.BytesIO(gateway_csv.encode("utf-8")), "text/csv"),
            "bank_file": ("bank.csv", io.BytesIO(bank_csv.encode("utf-8")), "text/csv"),
            "ledger_file": ("ledger.csv", io.BytesIO(ledger_csv.encode("utf-8")), "text/csv"),
        }
    )
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["summary"]["exact_matches"] == 1
    assert data["summary"]["anomalies_count"] == 0

def test_reconcile_with_anomaly():
    # Create dummy CSV data with a discrepancy
    gateway_csv = "transaction_id,amount,currency,created_at,reference\ng1,100,USD,2023-01-01,REF1\n"
    bank_csv = "bank_tx_id,value,currency,transaction_date,bank_reference\nb1,-90,USD,2023-01-01,REF1\n"
    ledger_csv = "ledger_tx_id,amount,currency,recorded_at,order_reference\nl1,100,USD,2023-01-01,REF1\n"

    response = client.post(
        "/api/reconcile",
        files={
            "gateway_file": ("gateway.csv", io.BytesIO(gateway_csv.encode("utf-8")), "text/csv"),
            "bank_file": ("bank.csv", io.BytesIO(bank_csv.encode("utf-8")), "text/csv"),
            "ledger_file": ("ledger.csv", io.BytesIO(ledger_csv.encode("utf-8")), "text/csv"),
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["summary"]["exact_matches"] == 0
    assert data["summary"]["anomalies_count"] == 1
    assert len(data["cases"]) == 1
    
    case_id = data["cases"][0]["id"]
    
    # Now test manual resolution
    resolve_response = client.post(
        f"/api/cases/{case_id}/resolve",
        json={
            "discrepancy_type": DiscrepancyType.PARTIAL_AMOUNT,
            "explanation": "Manually resolved."
        }
    )
    assert resolve_response.status_code == 200
    resolve_data = resolve_response.json()
    assert resolve_data["discrepancy_type"] == DiscrepancyType.PARTIAL_AMOUNT

def test_webhook_test():
    response = client.post(
        "/api/webhook/test",
        json={"webhook_url": "http://localhost:9999"} # Will likely fail connection but endpoint should work
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
