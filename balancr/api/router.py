import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Dict
import io
from datetime import datetime
import uuid
from balancr.canonical import CanonicalTransaction, DiscrepancyCase, ReconciliationStatus, DiscrepancyType
from balancr.matching.engine import ReconciliationEngine
from balancr.normalizers.gateway_csv import GatewayCSVSource
from balancr.normalizers.bank_csv import BankCSVSource
from balancr.normalizers.ledger_db import LedgerDBSource
from balancr.agent import agent_app
from balancr.memory.store import get_memory_store
from balancr.api.models import ReconcileResponse, ReconciliationSummary, APIResponseCase, ManualResolutionRequest, WebhookTestRequest

router = APIRouter(prefix="/api")

# In-memory storage for cases during session
session_cases: Dict[str, DiscrepancyCase] = {}
# Keep track of matched pairs from last run for stats
last_run_matches_count = 0

@router.post("/reconcile", response_model=ReconcileResponse)
async def reconcile_files(
    gateway_file: UploadFile = File(...),
    bank_file: UploadFile = File(...),
    ledger_file: UploadFile = File(...)
):
    global last_run_matches_count, session_cases
    session_cases.clear()

    # Read uploaded bytes directly to memory strings
    try:
        gateway_content = (await gateway_file.read()).decode("utf-8")
        bank_content = (await bank_file.read()).decode("utf-8")
        ledger_content = (await ledger_file.read()).decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode files: {e}")

    # Use temporary file paths or write strings to temp directory to reuse normalizers
    # To be extremely clean, we can write a small helper to parse StringIO or save temporarily
    # Since normalizers take file paths, let's write to local scratch temporary files
    os.makedirs("tmp", exist_ok=True)
    g_path = "tmp/gateway_temp.csv"
    b_path = "tmp/bank_temp.csv"
    l_path = "tmp/ledger_temp.csv"

    with open(g_path, "w") as f:
        f.write(gateway_content)
    with open(b_path, "w") as f:
        f.write(bank_content)
    with open(l_path, "w") as f:
        f.write(ledger_content)

    try:
        gateway_source = GatewayCSVSource(g_path)
        bank_source = BankCSVSource(b_path)
        ledger_source = LedgerDBSource(l_path)

        gateway_txs = gateway_source.load_transactions()
        bank_txs = bank_source.load_transactions()
        ledger_txs = ledger_source.load_transactions()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV structures: {e}")
    finally:
        # Clean up temp files
        for p in [g_path, b_path, l_path]:
            if os.path.exists(p):
                os.remove(p)

    # Deterministic matching
    engine = ReconciliationEngine()
    matched_pairs, anomalies = engine.reconcile_3way(gateway_txs, bank_txs, ledger_txs)
    last_run_matches_count = len(matched_pairs)

    # LLM classification
    resolved_cases = []
    has_groq = bool(os.environ.get("GROQ_API_KEY"))
    if anomalies:
        if has_groq:
            initial_state = {
                "anomalies": anomalies,
                "resolved_cases": [],
                "current_index": 0,
                "memory_matches": [],
                "summary": ""
            }
            try:
                final_state = agent_app.invoke(initial_state)
                resolved_cases = final_state["resolved_cases"]
            except Exception:
                resolved_cases = anomalies
        else:
            resolved_cases = anomalies

    # Save to session storage
    for case in resolved_cases:
        session_cases[case.id] = case

    # Compile Summary
    total_matched = len(matched_pairs)
    total_anomalies = len(resolved_cases)
    resolved_ok = sum(1 for c in resolved_cases if c.status == ReconciliationStatus.MATCHED)
    match_rate = ((total_matched + resolved_ok) / (total_matched + total_anomalies)) * 100 if (total_matched + total_anomalies) > 0 else 100.0

    summary = ReconciliationSummary(
        total_processed=total_matched * 3 + sum(1 for c in resolved_cases if c.transaction_gateway or c.transaction_bank),
        exact_matches=total_matched,
        anomalies_count=total_anomalies,
        match_rate=round(match_rate, 2)
    )

    # Prepare response cases
    cases_response = []
    for c in resolved_cases:
        cases_response.append(
            APIResponseCase(
                id=c.id,
                status=c.status,
                discrepancy_type=c.discrepancy_type,
                explanation=c.explanation,
                resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
                gateway_tx=c.transaction_gateway.dict() if c.transaction_gateway else None,
                bank_tx=c.transaction_bank.dict() if c.transaction_bank else None
            )
        )

    return ReconcileResponse(
        success=True,
        summary=summary,
        cases=cases_response
    )

@router.get("/cases", response_model=List[APIResponseCase])
async def get_cases():
    cases_response = []
    for c in session_cases.values():
        cases_response.append(
            APIResponseCase(
                id=c.id,
                status=c.status,
                discrepancy_type=c.discrepancy_type,
                explanation=c.explanation,
                resolved_at=c.resolved_at.isoformat() if c.resolved_at else None,
                gateway_tx=c.transaction_gateway.dict() if c.transaction_gateway else None,
                bank_tx=c.transaction_bank.dict() if c.transaction_bank else None
            )
        )
    return cases_response

@router.post("/cases/{case_id}/resolve", response_model=APIResponseCase)
async def resolve_case(case_id: str, request: ManualResolutionRequest):
    if case_id not in session_cases:
        raise HTTPException(status_code=404, detail="Case not found in active session.")

    case = session_cases[case_id]
    
    # Update status to MATCHED if resolved as TIMING_MISMATCH, else DISCREPANCY
    status = ReconciliationStatus.DISCREPANCY
    if request.discrepancy_type == DiscrepancyType.TIMING_MISMATCH:
        status = ReconciliationStatus.MATCHED

    updated_case = DiscrepancyCase(
        id=case.id,
        transaction_gateway=case.transaction_gateway,
        transaction_bank=case.transaction_bank,
        status=status,
        discrepancy_type=request.discrepancy_type,
        explanation=request.explanation,
        resolved_at=datetime.now()
    )

    # Save update in-memory
    session_cases[case_id] = updated_case

    # Persist to ChromaDB vector store so agent learns this case outcome
    try:
        store = get_memory_store()
        store.add_resolved_case(updated_case)
    except Exception as e:
        print(f"[API] Failed to save manual resolution to ChromaDB: {e}")

    return APIResponseCase(
        id=updated_case.id,
        status=updated_case.status,
        discrepancy_type=updated_case.discrepancy_type,
        explanation=updated_case.explanation,
        resolved_at=updated_case.resolved_at.isoformat(),
        gateway_tx=updated_case.transaction_gateway.dict() if updated_case.transaction_gateway else None,
        bank_tx=updated_case.transaction_bank.dict() if updated_case.transaction_bank else None
    )

@router.post("/webhook/test")
async def test_webhook(request: WebhookTestRequest):
    from balancr.notifications import WebhookNotificationDispatcher
    dispatcher = WebhookNotificationDispatcher(request.webhook_url)
    
    dummy_case = DiscrepancyCase(
        id="test-webhook-case",
        transaction_gateway=None,
        transaction_bank=None,
        status=ReconciliationStatus.DISCREPANCY,
        discrepancy_type=DiscrepancyType.UNKNOWN,
        explanation="This is a test notification dispatched from the Balancr API."
    )
    
    success = dispatcher.send_alert(dummy_case)
    return {"success": success, "message": "Test webhook alert dispatched."}
