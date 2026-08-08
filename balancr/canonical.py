from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    DISCREPANCY = "DISCREPANCY"
    UNMATCHED = "UNMATCHED"

class DiscrepancyType(str, Enum):
    DUPLICATE = "DUPLICATE"
    TIMING_MISMATCH = "TIMING_MISMATCH"
    PARTIAL_AMOUNT = "PARTIAL_AMOUNT"
    MISSING_COUNTERPART = "MISSING_COUNTERPART"
    UNKNOWN = "UNKNOWN"

class CanonicalTransaction(BaseModel):
    id: str = Field(..., description="Unique transaction ID from the source system")
    amount: float = Field(..., description="Transaction amount")
    currency: str = Field(..., description="Three-letter currency code (e.g. USD, COP)")
    date: datetime = Field(..., description="Transaction timestamp")
    reference: str = Field(..., description="Reconciliation reference ID (e.g. order_id or bank invoice number)")
    source: str = Field(..., description="Source name (e.g. gateway, bank, ledger)")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Raw transaction dictionary for auditing")

class DiscrepancyCase(BaseModel):
    id: str = Field(..., description="Unique case ID")
    transaction_gateway: Optional[CanonicalTransaction] = Field(None, description="Gateway transaction, if exists")
    transaction_bank: Optional[CanonicalTransaction] = Field(None, description="Bank transaction, if exists")
    status: ReconciliationStatus = Field(ReconciliationStatus.UNMATCHED, description="Current reconciliation status")
    discrepancy_type: Optional[DiscrepancyType] = Field(None, description="Classified discrepancy type")
    explanation: Optional[str] = Field(None, description="Explanatory notes or resolution justification")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
