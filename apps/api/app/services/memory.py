"""Walrus Memory integration (official `memwal` SDK).

Isolation model (demo-mode boundary, PRD §4/§9): there are no user accounts yet,
so each browser holds an unguessable workspace key (128+ bits). Every memory for
that workspace lives in its own Walrus Memory namespace:

    <MEMWAL_NAMESPACE_PREFIX>-ws-<sha256(workspace key)[:32]>

The raw workspace key never leaves the API process, and namespace names cannot
be guessed from wallet addresses. All reads, job lookups, and deletes are checked
against the caller's namespace.

Memory text is untrusted on the way back in: it is parsed against a strict
schema and anything that does not validate is dropped, never interpreted.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from collections import OrderedDict

from app.core.config import settings
from app.db.store import StoreUnavailable, get_store

logger = logging.getLogger("trace.memory")

SCHEMA_VERSION = 1
JSON_MARKER = "\nTRACE_JSON "
MEMORY_TYPES = ("counterparty_label", "alert_feedback", "investigation_summary")
FEEDBACK_LABELS = ("expected", "needs_review", "incorrect")
WORKSPACE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22,64}$")
ADDRESS_PATTERN = re.compile(r"^0x[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,64}$")  # base58 transaction digest
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
MAX_LABEL_CHARS = 60
MAX_TEXT_CHARS = 280
RECALL_LIMIT = 100
RECALL_TIMEOUT_SECONDS = 8.0
LOCAL_JOB_REGISTRY_SIZE = 10_000

# Patterns that look like secrets. TRACE never stores these (PRD §9 "Sensitive information").
_SECRET_PATTERNS = [
    re.compile(r"suiprivkey", re.I),
    re.compile(r"-----BEGIN", re.I),
    re.compile(r"(?<!0x)(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", re.I),  # bare 32-byte hex without 0x (key format)
    re.compile(r"\b(seed\s*phrase|mnemonic|recovery\s*(phrase|code)|private\s*key|password|passphrase)\b", re.I),
    re.compile(r"^(?:[a-z]{3,8}[\s,]+){11,23}[a-z]{3,8}$", re.I),  # text that is only 12-24 short words (mnemonic shape)
]


class MemoryUnavailable(RuntimeError):
    """Walrus Memory is not configured or could not be reached. Contains no secrets."""


class MemoryRejected(ValueError):
    """User-supplied memory content failed validation. Message is safe to show."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_text(value: Any, field: str, max_chars: int, required: bool = True) -> str:
    """Normalize user text, reject secrets and control characters, bound length."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise MemoryRejected(f"{field} must be text.")
    text = unicodedata.normalize("NFKC", value)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch == " ")
    text = re.sub(r"\s+", " ", text).strip()
    if required and not text:
        raise MemoryRejected(f"{field} is required.")
    if len(text) > max_chars:
        raise MemoryRejected(f"{field} must be {max_chars} characters or fewer.")
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise MemoryRejected(f"{field} looks like it may contain a secret or recovery phrase. TRACE never stores those.")
    return text


def workspace_namespace(workspace: str) -> str:
    if not isinstance(workspace, str) or not WORKSPACE_PATTERN.fullmatch(workspace):
        raise MemoryRejected("A valid workspace key is required for memory.")
    digest = hashlib.sha256(workspace.encode("utf-8")).hexdigest()[:32]
    return f"{settings.MEMWAL_NAMESPACE_PREFIX}-ws-{digest}"


def namespace_ref(namespace: str) -> str:
    """Short, non-reversible reference that is safe to show in the UI and logs."""
    return namespace.rsplit("-", 1)[-1][:10]


@dataclass(frozen=True)
class MemoryEnvelope:
    memory_type: str
    wallet: str
    subject: str  # counterparty address, transaction digest, or wallet address
    value: str  # label, feedback label, or summary text
    reason: str
    created_at: str
    source_type: str = "user_confirmed"
    user_confirmed: bool = True
    verified: bool = False  # user assertions are never treated as independently verified
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_type": self.memory_type,
            "wallet": self.wallet,
            "subject": self.subject,
            "value": self.value,
            "reason": self.reason,
            "created_at": self.created_at,
            "source_type": self.source_type,
            "user_confirmed": self.user_confirmed,
            "verified": self.verified,
            "schema_version": self.schema_version,
        }


def build_envelope(memory_type: str, wallet: str, subject: str, value: str, reason: str = "") -> MemoryEnvelope:
    if memory_type not in MEMORY_TYPES:
        raise MemoryRejected("Unsupported memory type.")
    wallet = (wallet or "").strip().lower()
    if not ADDRESS_PATTERN.fullmatch(wallet):
        raise MemoryRejected("Wallet must be a valid Sui address.")
    subject = (subject or "").strip()
    if memory_type == "counterparty_label":
        subject = subject.lower()
        if not ADDRESS_PATTERN.fullmatch(subject) or subject == wallet:
            raise MemoryRejected("Counterparty must be a different valid Sui address.")
        # An empty label is allowed: it supersedes (removes) an earlier label.
        value = clean_text(value, "Label", MAX_LABEL_CHARS, required=False)
    elif memory_type == "alert_feedback":
        if not DIGEST_PATTERN.fullmatch(subject):
            raise MemoryRejected("Feedback must reference a valid transaction digest.")
        if value not in FEEDBACK_LABELS:
            raise MemoryRejected("Feedback must be expected, needs_review, or incorrect.")
    else:
        subject = wallet
        value = clean_text(value, "Summary", MAX_TEXT_CHARS)
    reason = clean_text(reason, "Reason", MAX_TEXT_CHARS, required=False)
    return MemoryEnvelope(memory_type=memory_type, wallet=wallet, subject=subject, value=value, reason=reason, created_at=utc_now())


def encode(envelope: MemoryEnvelope) -> str:
    """Readable sentence (for semantic search) plus a machine-readable JSON line."""
    short = lambda a: f"{a[:8]}…{a[-6:]}"  # noqa: E731
    if envelope.memory_type == "counterparty_label":
        sentence = (f"User labelled counterparty {short(envelope.subject)} as \"{envelope.value}\" for wallet {short(envelope.wallet)}."
                    if envelope.value else f"User removed the label for counterparty {short(envelope.subject)}.")
    elif envelope.memory_type == "alert_feedback":
        sentence = f"User marked the alert for transaction {envelope.subject[:10]}… on wallet {short(envelope.wallet)} as {envelope.value.replace('_', ' ')}."
    else:
        sentence = f"Investigation summary for wallet {short(envelope.wallet)}: {envelope.value}"
    return f"TRACE memory v{SCHEMA_VERSION}. {sentence}{JSON_MARKER}{json.dumps(envelope.to_dict(), sort_keys=True, separators=(',', ':'))}"


def decode(text: Any) -> MemoryEnvelope | None:
    """Strictly parse recalled text. Returns None for anything that does not validate."""
    if not isinstance(text, str) or JSON_MARKER not in text or len(text) > 4096:
        return None
    try:
        data = json.loads(text.rsplit(JSON_MARKER, 1)[1])
    except (ValueError, IndexError):
        return None
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return None
    try:
        rebuilt = build_envelope(data["memory_type"], data["wallet"], data["subject"], data["value"], data.get("reason", ""))
        created_at = data["created_at"]
        datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return None
    if data.get("user_confirmed") is not True or data.get("verified") is not False or data.get("source_type") != "user_confirmed":
        return None
    return MemoryEnvelope(**{**rebuilt.to_dict(), "created_at": str(created_at)})


@dataclass(frozen=True)
class RecalledMemory:
    memory_id: str  # Walrus blob ID
    envelope: MemoryEnvelope
    stored_at: str | None


def _audit(event: str, **fields: Any) -> None:
    """Non-secret audit event (PRD §9): no keys, no memory text, no workspace key."""
    logger.info("memory_audit %s", json.dumps({"event": event, "at": utc_now(), **fields}, sort_keys=True))


ClientFactory = Callable[[str], Any]


class MemoryService:
    def __init__(self, client_factory: ClientFactory | None = None):
        self._client_factory = client_factory
        # job_id -> namespace for jobs this process accepted. Backs up the durable store,
        # so ownership can still be checked when the database is briefly unreachable.
        self._local_jobs: OrderedDict[str, str] = OrderedDict()

    def _remember_owner(self, job_id: str, namespace: str) -> None:
        self._local_jobs[job_id] = namespace
        self._local_jobs.move_to_end(job_id)
        while len(self._local_jobs) > LOCAL_JOB_REGISTRY_SIZE:
            self._local_jobs.popitem(last=False)

    async def _job_owner(self, job_id: str) -> str | None:
        owner = self._local_jobs.get(job_id)
        if owner is not None:
            return owner
        try:
            return await get_store().job_owner(job_id)
        except StoreUnavailable:
            logger.warning("job ownership lookup unavailable; treating job as unknown")
            return None

    @property
    def configured(self) -> bool:
        return self._client_factory is not None or settings.memory_configured

    def _client(self, namespace: str):
        if self._client_factory is not None:
            return self._client_factory(namespace)
        if not self.configured:
            raise MemoryUnavailable("Walrus Memory is not configured")
        from memwal import MemWal

        return MemWal.create(
            key=settings.WALRUS_MEMORY_PRIVATE_KEY,
            account_id=settings.MEMWAL_ACCOUNT_ID,
            server_url=settings.MEMWAL_SERVER_URL or None,
            namespace=namespace,
        )

    async def _with_client(self, namespace: str, action):
        client = self._client(namespace)
        try:
            return await action(client)
        except (MemoryRejected, MemoryUnavailable):
            raise
        except Exception as exc:  # SDK and network errors: never echo details to callers
            raise MemoryUnavailable(f"Walrus Memory request failed ({type(exc).__name__})") from None
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                try:
                    await close(clear_keys=True)
                except TypeError:
                    await close()
                except Exception:  # pragma: no cover - best effort cleanup
                    pass

    async def write(self, workspace: str, envelope: MemoryEnvelope, idempotency_key: str | None = None) -> str:
        namespace = workspace_namespace(workspace)
        key = None
        if idempotency_key:
            if not JOB_ID_PATTERN.fullmatch(idempotency_key):
                raise MemoryRejected("Idempotency-Key must be 1-128 letters, digits, '-' or '_'.")
            key = hashlib.sha256(f"{namespace}:{idempotency_key}".encode()).hexdigest()

        async def action(client):
            accepted = await client.remember(encode(envelope), namespace=namespace, idempotency_key=key)
            return accepted.job_id

        job_id = await self._with_client(namespace, action)
        if not isinstance(job_id, str) or not JOB_ID_PATTERN.fullmatch(job_id):
            raise MemoryUnavailable("Walrus Memory returned an invalid job id")
        self._remember_owner(job_id, namespace)
        try:
            await get_store().record_job(job_id, namespace, envelope.memory_type)
        except StoreUnavailable:
            logger.warning("memory job ownership not persisted; using the in-process registry")
        _audit("write_accepted", memory_type=envelope.memory_type, job_id=job_id, namespace_ref=namespace_ref(namespace))
        return job_id

    async def job_status(self, workspace: str, job_id: str) -> dict[str, Any]:
        namespace = workspace_namespace(workspace)
        if not JOB_ID_PATTERN.fullmatch(job_id or ""):
            return {"job_id": job_id, "status": "not_found"}

        async def action(client):
            return await client.get_remember_status(job_id)

        # Every workspace shares one Walrus account, so the provider's own ownership check
        # cannot tell workspaces apart. TRACE checks the namespace itself: the provider's
        # reported namespace when present, and its own record of who submitted the job.
        owner = await self._job_owner(job_id)
        if owner is not None and owner != namespace:
            return {"job_id": job_id, "status": "not_found"}
        status = await self._with_client(namespace, action)
        if status.status == "not_found":
            return {"job_id": job_id, "status": "not_found"}
        if status.namespace is not None:
            if status.namespace != namespace:
                return {"job_id": job_id, "status": "not_found"}
        elif owner is None:
            # Neither the provider nor TRACE can show this job belongs to the caller: fail closed.
            return {"job_id": job_id, "status": "not_found"}
        state = {"done": "succeeded", "failed": "failed"}.get(status.status, "pending")
        if state in ("succeeded", "failed"):
            _audit(f"write_{state}", job_id=job_id, namespace_ref=namespace_ref(namespace))
            try:
                await get_store().update_job(job_id, namespace, state, status.blob_id if state == "succeeded" else None)
            except StoreUnavailable:
                logger.warning("memory job status not persisted")
        return {
            "job_id": job_id,
            "status": state,
            "provider_status": status.status,
            "blob_id": status.blob_id if state == "succeeded" else None,
            "error": "Walrus Memory reported the write as failed." if state == "failed" else None,
        }

    async def recall(self, workspace: str, wallet: str | None = None, query: str | None = None) -> list[RecalledMemory]:
        namespace = workspace_namespace(workspace)
        search = query or (f"TRACE memory labels and alert feedback for wallet {wallet}" if wallet else "TRACE memory")

        async def action(client):
            from memwal import RecallParams

            return await client.recall(RecallParams(query=search, limit=RECALL_LIMIT, namespace=namespace))

        result = await asyncio.wait_for(self._with_client(namespace, action), timeout=RECALL_TIMEOUT_SECONDS)
        memories = []
        dropped = 0
        seen: set[tuple] = set()
        for item in getattr(result, "results", []):
            envelope = decode(getattr(item, "text", None))
            blob_id = getattr(item, "blob_id", None)
            if envelope is None or not isinstance(blob_id, str) or not blob_id:
                dropped += 1
                continue
            if wallet and envelope.wallet != wallet.lower():
                continue
            # The same assertion stored twice (e.g. a retried write) is shown and applied once.
            identity = (envelope.memory_type, envelope.subject, envelope.value, envelope.reason, envelope.created_at)
            if identity in seen:
                continue
            seen.add(identity)
            memories.append(RecalledMemory(memory_id=str(item.blob_id), envelope=envelope, stored_at=getattr(item, "created_at", None)))
        memories.sort(key=lambda m: m.envelope.created_at)
        _audit("recall", namespace_ref=namespace_ref(namespace), returned=len(memories), dropped_invalid=dropped)
        return memories

    async def forget_all(self, workspace: str) -> int:
        namespace = workspace_namespace(workspace)

        async def action(client):
            return await client.forget_namespace(namespace)

        result = await self._with_client(namespace, action)
        for job_id in [k for k, v in self._local_jobs.items() if v == namespace]:
            del self._local_jobs[job_id]
        try:
            await get_store().forget_jobs(namespace)
        except StoreUnavailable:
            logger.warning("memory job records not cleared from the database")
        _audit("forget_namespace", namespace_ref=namespace_ref(namespace), deleted=result.deleted)
        return int(result.deleted)


memory_service = MemoryService()
