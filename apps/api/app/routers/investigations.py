"""Investigation history for the caller's workspace.

There are no user accounts yet. Ownership is the workspace (X-Trace-Workspace header):
every query is filtered by the namespace derived from it, so one workspace can never
list, read or delete another's history. A record from another workspace is reported
exactly like a record that does not exist.
"""
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.db.store import StoreUnavailable, get_store
from app.routers.memories import require_workspace
from app.services.memory import workspace_namespace

router = APIRouter()
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{64}$")
UNAVAILABLE = "Investigation history is unavailable right now. Reference: {request_id}"


class DeleteHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal["DELETE"]


def _unavailable(request: Request) -> HTTPException:
    return HTTPException(status_code=503, detail=UNAVAILABLE.format(request_id=getattr(request.state, "request_id", "unknown")))


@router.get("/investigations")
async def list_investigations(
    request: Request,
    address: str | None = Query(default=None, max_length=66),
    limit: int = Query(default=20, ge=1, le=100),
    x_trace_workspace: str | None = Header(default=None),
):
    namespace = workspace_namespace(require_workspace(x_trace_workspace))
    if address is not None and not ADDRESS.fullmatch(address):
        raise HTTPException(status_code=400, detail="address must be 0x followed by 64 hexadecimal characters.")
    store = get_store()
    try:
        items = await store.list_investigations(namespace, address.lower() if address else None, limit)
    except StoreUnavailable:
        raise _unavailable(request) from None
    return {"durable": store.durable, "storage": store.backend, "investigations": items}


@router.get("/investigations/{investigation_id}")
async def get_investigation(request: Request, investigation_id: str, x_trace_workspace: str | None = Header(default=None)):
    namespace = workspace_namespace(require_workspace(x_trace_workspace))
    try:
        canonical = str(uuid.UUID(investigation_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Investigation not found for this workspace.") from None
    try:
        item = await get_store().get_investigation(namespace, canonical)
    except StoreUnavailable:
        raise _unavailable(request) from None
    if item is None:
        raise HTTPException(status_code=404, detail="Investigation not found for this workspace.")
    return item


@router.delete("/investigations")
async def delete_investigations(request: Request, payload: DeleteHistoryRequest, x_trace_workspace: str | None = Header(default=None)):
    namespace = workspace_namespace(require_workspace(x_trace_workspace))
    try:
        deleted = await get_store().delete_investigations(namespace)
    except StoreUnavailable:
        raise _unavailable(request) from None
    return {"deleted": deleted, "message": "Investigation history for this workspace was permanently deleted from TRACE's database."}
