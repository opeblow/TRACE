from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.memory import (
    MemoryRejected,
    MemoryUnavailable,
    build_envelope,
    memory_service,
    namespace_ref,
    workspace_namespace,
)

router = APIRouter()

UNAVAILABLE = "Walrus Memory is unavailable right now. Nothing was saved. Reference: {request_id}"


class MemoryWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_type: Literal["counterparty_label", "alert_feedback", "investigation_summary"]
    wallet: str = Field(..., max_length=66)
    subject: str = Field("", max_length=128)
    value: str = Field("", max_length=400)
    reason: str = Field("", max_length=400)
    consent: bool = Field(..., description="The user explicitly asked TRACE to remember this.")


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet: str = Field(..., max_length=66)
    label: Literal["expected", "needs_review", "incorrect"]
    reason: str = Field("", max_length=400)
    consent: bool


class ForgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal["DELETE"]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def require_workspace(workspace: str | None) -> str:
    if not workspace:
        raise HTTPException(status_code=400, detail="Memory requires a workspace key (X-Trace-Workspace header).")
    try:
        workspace_namespace(workspace)
    except MemoryRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return workspace


def require_configured(request: Request) -> None:
    if not memory_service.configured:
        raise HTTPException(status_code=503, detail=UNAVAILABLE.format(request_id=_request_id(request)))


async def submit_memory(request: Request, workspace: str, memory_type: str, wallet: str, subject: str, value: str, reason: str, consent: bool, idempotency_key: str | None):
    if consent is not True:
        raise HTTPException(status_code=400, detail="TRACE only remembers what you explicitly confirm.")
    require_configured(request)
    try:
        envelope = build_envelope(memory_type, wallet, subject, value, reason)
        job_id = await memory_service.write(workspace, envelope, idempotency_key)
    except MemoryRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except MemoryUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE.format(request_id=_request_id(request))) from None
    return {
        "job_id": job_id,
        "status": "pending",
        "memory_type": envelope.memory_type,
        "message": "Accepted by Walrus Memory. Not saved until the job completes.",
        "status_url": f"/api/v1/memories/jobs/{job_id}",
    }


@router.get("/memories")
async def list_memories(request: Request, wallet: str | None = None, x_trace_workspace: str | None = Header(default=None)):
    workspace = require_workspace(x_trace_workspace)
    require_configured(request)
    try:
        memories = await memory_service.recall(workspace, wallet=wallet.lower() if wallet else None)
    except (MemoryUnavailable, TimeoutError):
        raise HTTPException(status_code=503, detail=UNAVAILABLE.format(request_id=_request_id(request))) from None
    return {
        "available": True,
        "namespace_ref": namespace_ref(workspace_namespace(workspace)),
        "storage": "Walrus Memory (Mainnet relayer)",
        "memories": [
            {
                "memory_id": m.memory_id,
                **m.envelope.to_dict(),
                "stored_at": m.stored_at,
            }
            for m in reversed(memories)
        ],
    }


@router.post("/memories", status_code=202)
async def create_memory(request: Request, payload: MemoryWriteRequest, x_trace_workspace: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
    workspace = require_workspace(x_trace_workspace)
    return await submit_memory(request, workspace, payload.memory_type, payload.wallet, payload.subject, payload.value, payload.reason, payload.consent, idempotency_key)


@router.get("/memories/jobs/{job_id}")
async def get_memory_job(request: Request, job_id: str, x_trace_workspace: str | None = Header(default=None)):
    workspace = require_workspace(x_trace_workspace)
    require_configured(request)
    try:
        status = await memory_service.job_status(workspace, job_id)
    except MemoryUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE.format(request_id=_request_id(request))) from None
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Memory job not found for this workspace.")
    return status


@router.delete("/memories")
async def forget_memories(request: Request, payload: ForgetRequest, x_trace_workspace: str | None = Header(default=None)):
    workspace = require_workspace(x_trace_workspace)
    require_configured(request)
    try:
        deleted = await memory_service.forget_all(workspace)
    except MemoryUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE.format(request_id=_request_id(request))) from None
    return {
        "deleted": deleted,
        "message": "Removed from TRACE's Walrus Memory index for this workspace. Encrypted blobs already written to "
                   "Walrus are not erased by this action, and public blockchain records are never affected.",
    }
