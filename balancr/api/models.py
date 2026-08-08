from pydantic import BaseModel, Field
from typing import List, Optional, Any
from balancr.canonical import ReconciliationStatus, DiscrepancyType

class ReconciliationSummary(BaseModel):
    total_processed: int = Field(..., description="Total transactions processed")
    exact_matches: int = Field(..., description="Deterministic exact matches count")
    anomalies_count: int = Field(..., description="Total anomalies identified")
    match_rate: float = Field(..., description="Matching efficiency rate")

class APIResponseCase(BaseModel):
    id: str
    status: ReconciliationStatus
    discrepancy_type: Optional[DiscrepancyType] = None
    explanation: Optional[str] = None
    resolved_at: Optional[str] = None
    gateway_tx: Optional[dict] = None
    bank_tx: Optional[dict] = None

class ReconcileResponse(BaseModel):
    success: bool
    summary: ReconciliationSummary
    cases: List[APIResponseCase]

class ManualResolutionRequest(BaseModel):
    discrepancy_type: DiscrepancyType = Field(..., description="New discrepancy category classification")
    explanation: str = Field(..., description="Reasoning and notes justifying this resolution")

class WebhookTestRequest(BaseModel):
    webhook_url: str = Field(..., description="External HTTP POST target URL to send the test alert payload")
