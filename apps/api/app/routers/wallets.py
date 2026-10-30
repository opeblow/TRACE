import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.metrics import metrics
from app.db.store import InvestigationRecord, StoreUnavailable, get_store
from app.schemas.schemas import WalletAnalyzeRequest
from app.services.anomaly import RULE_VERSION, anomaly_service
from app.services.learning import MEMORY_RULE_VERSION, active_labels, apply_memory, sort_by_priority
from app.services.memory import MemoryRejected, MemoryUnavailable, RecalledMemory, memory_service, namespace_ref, workspace_namespace
from app.services.tatum import SOURCE, SUI_COIN_TYPE, TatumProviderError, TransactionRecord, canonical_coin_type, tatum_service

router = APIRouter()
logger = logging.getLogger("trace.wallets")
SUI_ADDRESS_PATTERN = re.compile(r"^0x[0-9a-fA-F]{64}$")
MIST_PER_SUI = Decimal("1000000000")
EXPECTED_CHAIN = "mainnet"
HISTORY_LIMIT = 150  # three provider pages; deeper history gives steadier baselines


def mist_to_sui(raw: str | int) -> str:
    """Exact decimal conversion from MIST (integer) to a SUI string; never uses floats."""
    value = Decimal(str(raw))
    if not value.is_finite() or value != value.to_integral_value():
        raise ValueError("Invalid MIST amount")
    text = format(value / MIST_PER_SUI, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def native_sui_balance(raw_mist: str | None) -> str | None:
    if raw_mist is None:
        return None
    if Decimal(str(raw_mist)) < 0:
        raise ValueError("Invalid total balance")
    return mist_to_sui(raw_mist)


def primary_counterparty(direction: str | None, sender: str | None, address: str, others: dict[str, Decimal]) -> str | None:
    """Best-supported counterparty from SUI balance changes; None when the chain data does not show one."""
    sender = sender.lower() if isinstance(sender, str) else None
    if direction == "out":
        receivers = [(amount, addr) for addr, amount in others.items() if amount > 0]
        return max(receivers)[1] if receivers else None
    if direction == "in":
        if sender and sender != address.lower():
            return sender
        payers = [(amount, addr) for addr, amount in others.items() if amount < 0]
        return min(payers)[1] if payers else None
    return None


def normalize_activity(transactions: list[TransactionRecord], address: str) -> list[dict]:
    """Net native-SUI change for the analysed address, per transaction, as exact decimal strings.

    Each item also carries `activity_kind` so the anomaly baseline can exclude movements
    that are only gas: "transfer", "gas_only", "no_sui_change" or "failed".
    `transfer_amount_sui` is the net change with the sender's gas fee removed (when Tatum reports it).
    """
    sui_type = canonical_coin_type(SUI_COIN_TYPE)
    normalized = []
    for tx in transactions:
        item = {
            "digest": tx.digest,
            "timestamp_ms": tx.timestamp_ms,
            "checkpoint": tx.checkpoint,
            "status": tx.status,
            "direction": None,
            "amount_sui": None,
            "transfer_amount_sui": None,
            "gas_fee_sui": None,
            "activity_kind": "no_sui_change",
            "counterparty": None,
        }
        if tx.status == "failure":
            item["activity_kind"] = "failed"
            normalized.append(item)
            continue
        net_mist = Decimal(0)
        has_address_change = False
        others: dict[str, Decimal] = {}
        for change in tx.balance_changes:
            if canonical_coin_type(change.coin_type) != sui_type:
                continue
            if change.address.lower() != address.lower():
                try:
                    others[change.address.lower()] = others.get(change.address.lower(), Decimal(0)) + Decimal(change.amount)
                except InvalidOperation:
                    pass
                continue
            amount = Decimal(change.amount)
            if not amount.is_finite() or amount != amount.to_integral_value():
                raise ValueError("Invalid balance change amount")
            net_mist += amount
            has_address_change = True
        is_sender = isinstance(tx.sender, str) and tx.sender.lower() == address.lower()
        if has_address_change:
            item["amount_sui"] = mist_to_sui(net_mist)
            transfer_mist = net_mist
            if is_sender and tx.gas_fee_mist is not None:
                transfer_mist = net_mist + tx.gas_fee_mist
                item["gas_fee_sui"] = mist_to_sui(Decimal(tx.gas_fee_mist))
            item["transfer_amount_sui"] = mist_to_sui(transfer_mist)
            item["direction"] = "in" if net_mist > 0 else "out" if net_mist < 0 else "none"
            if is_sender and tx.gas_fee_mist is not None and transfer_mist == 0:
                item["activity_kind"] = "gas_only"
            elif net_mist != 0:
                item["activity_kind"] = "transfer"
        item["counterparty"] = primary_counterparty(item["direction"], tx.sender, address, others)
        normalized.append(item)
    return normalized


async def recall_for_analysis(workspace: str | None, address: str) -> tuple[str, list[RecalledMemory], str | None]:
    """Recall this workspace's memories for the wallet. Never fails the analysis (PRD Journey D)."""
    if not workspace:
        return "no_workspace", [], None
    try:
        namespace = workspace_namespace(workspace)
    except MemoryRejected:
        return "no_workspace", [], None
    if not memory_service.configured:
        return "not_configured", [], namespace_ref(namespace)
    try:
        return "recalled", await memory_service.recall(workspace, wallet=address), namespace_ref(namespace)
    except (MemoryUnavailable, asyncio.TimeoutError):
        return "unavailable", [], namespace_ref(namespace)


async def save_history(workspace: str | None, result: dict, request_id: str) -> dict:
    """Keep a record of this investigation for the workspace. Never fails the analysis."""
    if not workspace:
        return {"saved": False, "reason": "no_workspace"}
    try:
        namespace = workspace_namespace(workspace)
    except MemoryRejected:
        return {"saved": False, "reason": "no_workspace"}
    store = get_store()
    try:
        investigation_id = await store.save_investigation(InvestigationRecord.from_analysis(namespace, result))
    except StoreUnavailable:
        logger.warning("investigation history not saved request_id=%s", request_id)
        return {"saved": False, "reason": "storage_unavailable", "durable": store.durable}
    return {"saved": True, "investigation_id": investigation_id, "durable": store.durable}


MEMORY_MESSAGES = {
    "no_workspace": "Stateless analysis: no memory workspace was provided.",
    "not_configured": "Stateless analysis: Walrus Memory is not configured on this server.",
    "unavailable": "Stateless analysis: Walrus Memory could not be reached, so saved context was not retrieved.",
    "none": "No saved memories for this wallet yet. Labels and alert feedback you confirm will be stored in Walrus Memory.",
    "recalled": "Memories were recalled from Walrus Memory but did not match any current finding.",
    "used": "Recalled memory changed this result. Compare with the memory-free result below.",
}


@router.post("/wallets/analyze")
async def analyze_wallet(request: Request, payload: WalletAnalyzeRequest, x_trace_workspace: str | None = Header(default=None)):
    address = payload.address.strip()
    if not SUI_ADDRESS_PATTERN.fullmatch(address):
        raise HTTPException(status_code=400, detail="Enter a valid Sui address (0x followed by 64 hexadecimal characters).")
    address = address.lower()

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    if not tatum_service.api_key:
        raise HTTPException(status_code=503, detail="Wallet analysis is not configured. Contact the service operator.")

    memory_task = asyncio.create_task(recall_for_analysis(x_trace_workspace, address))
    try:
        try:
            fetched = await tatum_service.fetch_wallet(address, limit=HISTORY_LIMIT)
        except TatumProviderError as exc:
            metrics.inc("trace_provider_failures_total", provider="tatum", kind="request")
            metrics.inc("trace_analyses_total", outcome="provider_error")
            logger.warning("wallet analysis provider failure request_id=%s error=%s", request_id, exc)
            raise HTTPException(status_code=502, detail=f"Wallet data provider is unavailable. Reference: {request_id}") from None

        if fetched.chain.chain != EXPECTED_CHAIN:
            metrics.inc("trace_provider_failures_total", provider="tatum", kind="wrong_network")
            metrics.inc("trace_analyses_total", outcome="provider_error")
            logger.warning("provider network mismatch request_id=%s chain=%s", request_id, fetched.chain.chain)
            raise HTTPException(status_code=502, detail=f"Wallet data provider did not confirm Sui Mainnet. Reference: {request_id}")

        try:
            balance = native_sui_balance(fetched.sui_balance_mist)
        except (InvalidOperation, TypeError, ValueError):
            logger.warning("wallet balance normalization failure request_id=%s", request_id)
            raise HTTPException(status_code=502, detail=f"Wallet balance response could not be interpreted. Reference: {request_id}") from None

        try:
            transactions = normalize_activity(fetched.transactions, address)
        except (InvalidOperation, TypeError, ValueError):
            logger.warning("wallet activity normalization failure request_id=%s", request_id)
            raise HTTPException(status_code=502, detail=f"Wallet activity response could not be interpreted. Reference: {request_id}") from None

        baseline = anomaly_service.establish_baseline(transactions)
        stateless_anomalies = sort_by_priority(anomaly_service.detect_anomalies(transactions, baseline))
        memory_status, memories, memory_ns_ref = await memory_task
        anomalies, effects, used_ids = apply_memory(stateless_anomalies, memories)
        labels = active_labels(memories)
        for item in transactions:
            label = labels.get(item.get("counterparty") or "")
            item["counterparty_label"] = label.envelope.value if label else None
        if memory_status == "recalled":
            memory_status = "used" if effects else ("recalled" if memories else "none")
        wallet_id = str(uuid.uuid4())
        fetched_at = datetime.now(timezone.utc).isoformat()
        partial_reasons = []
        if fetched.has_more:
            partial_reasons.append("provider_has_more_history")
        if baseline.get("status") == "thin_history":
            partial_reasons.append("insufficient_interpretable_history")
        if baseline.get("uninterpretable_count", 0) > 0:
            partial_reasons.append("some_transactions_lack_native_sui_balance_changes")
        partial = bool(partial_reasons)

        result = {
            "wallet_id": wallet_id,
            "address": address,
            "snapshot": {
                "wallet_id": wallet_id,
                "address": address,
                "balance": balance,
                "balance_unit": "SUI",
                "fetched_at": fetched_at,
                "network": fetched.chain.chain,
                "checkpoint_height": fetched.chain.checkpoint_height,
                "sources": [SOURCE],
                "activity_count": len(transactions),
            },
            "analysis": {
                "baseline": baseline,
                "anomalies": anomalies,
                "anomaly_count": len(anomalies),
                "status": "partial" if partial else "complete",
                "activity_status": "available" if transactions else "empty",
                "history_truncated": fetched.has_more,
                "partial_reasons": partial_reasons,
                "rule_version": RULE_VERSION,
            },
            "activity": {"items": transactions, "has_more": fetched.has_more},
            "evidence": [evidence for anomaly in anomalies for evidence in anomaly["evidence"]],
            "memory": {
                "status": memory_status,
                "message": MEMORY_MESSAGES[memory_status],
                "namespace_ref": memory_ns_ref,
                "rule_version": MEMORY_RULE_VERSION,
                "recalled_count": len(memories),
                "changed_result": bool(effects),
                "memories": [
                    {
                        "memory_id": m.memory_id,
                        "memory_type": m.envelope.memory_type,
                        "subject": m.envelope.subject,
                        "value": m.envelope.value,
                        "reason": m.envelope.reason,
                        "created_at": m.envelope.created_at,
                        "verified": m.envelope.verified,
                        "used": m.memory_id in used_ids,
                    }
                    for m in memories
                ],
                "effects": effects,
                "stateless": {"anomalies": stateless_anomalies},
            },
        }
        result["history"] = await save_history(x_trace_workspace, result, request_id)
        metrics.inc("trace_analyses_total", outcome=result["analysis"]["status"])
        metrics.inc("trace_memory_recall_total", status=memory_status)
        metrics.inc("trace_history_saves_total", outcome="saved" if result["history"]["saved"] else result["history"]["reason"])
        return result

    finally:
        if not memory_task.done():
            memory_task.cancel()

@router.get("/wallets/{wallet_id}/activity")
async def get_activity(wallet_id: str, cursor: str | None = None, limit: int = 50):
    raise HTTPException(status_code=501, detail="Activity pagination is not implemented; this demo only returns the first analysis page")
