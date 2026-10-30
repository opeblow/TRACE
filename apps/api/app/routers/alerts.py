from fastapi import APIRouter, Header, HTTPException, Request

from app.routers.memories import FeedbackRequest, require_workspace, submit_memory

router = APIRouter()


@router.get("/alerts")
async def get_alerts(wallet_id: str | None = None, status: str | None = None):
    # Findings are returned with each analysis. There is no server-side alert
    # history; user feedback on findings is stored in Walrus Memory instead.
    return {"available": False, "reason": "alerts are returned with each wallet analysis", "alerts": []}


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
