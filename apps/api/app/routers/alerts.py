from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.db.store import StoreUnavailable, get_store
from app.services.memory import workspace_namespace

from app.routers.memories import FeedbackRequest, require_workspace, submit_memory

router = APIRouter()


@router.get("/alerts")
async def get_alerts(request: Request, limit: int = Query(default=50, ge=1, le=100), x_trace_workspace: str | None = Header(default=None)):
    """Finding history for this workspace, newest investigation first."""
    if not x_trace_workspace:
        return {"available": False, "reason": "a workspace key is required for alert history", "alerts": []}
    namespace = workspace_namespace(require_workspace(x_trace_workspace))
    store = get_store()
    try:
        alerts = await store.recent_findings(namespace, limit)
    except StoreUnavailable:
        raise HTTPException(status_code=503, detail=f"Alert history is unavailable right now. Reference: {getattr(request.state, 'request_id', 'unknown')}") from None
    return {"available": True, "durable": store.durable, "alerts": alerts}


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    raise HTTPException(status_code=404, detail="Alert history is not stored; findings are returned with each analysis.")


@router.post("/alerts/{alert_id}/feedback", status_code=202)
async def submit_feedback(
    request: Request,
    alert_id: str,
    payload: FeedbackRequest,
    x_trace_workspace: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
):
    """Alert IDs are transaction digests. Feedback is a user assertion stored as memory, never proof."""
    workspace = require_workspace(x_trace_workspace)
    return await submit_memory(request, workspace, "alert_feedback", payload.wallet, alert_id, payload.label, payload.reason, payload.consent, idempotency_key)
