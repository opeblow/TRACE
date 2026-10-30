from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class WalletAnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = Field(..., min_length=1, max_length=256, description="Sui wallet address")

class Evidence(BaseModel):
    evidence_id: str
    type: str  # tx, object, balance, rule
    ref: str
    source: str
    timestamp: Optional[str] = None

class Alert(BaseModel):
    alert_id: str
    wallet_id: str
    severity: str  # low, medium, high
    title: str
    rationale: str
    evidence: List[Evidence]
    uncertainty: float
    status: str = "open"
    created_at: datetime

class Memory(BaseModel):
    memory_id: str
    type: str  # preference, counterparty, alert_outcome, label
    summary: str
    provenance: str
    created_at: datetime
    consented: bool
    user_id: str

class WalletSnapshot(BaseModel):
    wallet_id: str
    address: str
    balance: Optional[str] = None
    fetched_at: datetime
    sources: List[str]
    activity_count: int = 0
