"""Application persistence: investigation history, findings, workspace ownership and memory job ownership.

Two implementations share one interface:

* PostgresStore: durable, used when DATABASE_URL is set. Schema changes are versioned SQL
  files in app/db/migrations, applied at startup inside one transaction under an advisory
  lock, so several instances starting together cannot race.
* InMemoryStore: process-local, bounded, for development and tests. Nothing survives a
  restart, and `durable` says so.

Ownership is the Walrus namespace derived from the workspace key (never the key itself).
Every read and delete is filtered by that namespace.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

logger = logging.getLogger("trace.store")

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATION_LOCK_ID = 4_172_301_977  # arbitrary constant for pg_advisory_xact_lock
MAX_HISTORY = 100
MEMORY_MAX_JOBS = 10_000
MEMORY_MAX_INVESTIGATIONS_PER_WORKSPACE = 50


class StoreUnavailable(RuntimeError):
    """The persistence layer could not complete a request. Contains no connection details."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _text(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass(frozen=True)
class InvestigationRecord:
    """What TRACE keeps about one analysis. Built from the API response, validated once here."""

    id: str
    namespace: str
    address: str
    network: str
    checkpoint_height: int | None
    balance_sui: Decimal | None
    activity_count: int
    history_truncated: bool
    status: str
    partial_reasons: list[str]
    rule_version: str
    memory_rule_version: str | None
    memory_status: str
    baseline: dict[str, Any]
    findings: list[dict[str, Any]]

    @classmethod
    def from_analysis(cls, namespace: str, result: dict[str, Any]) -> "InvestigationRecord":
        snapshot, analysis, memory = result["snapshot"], result["analysis"], result.get("memory") or {}
        findings = []
        for f in analysis.get("anomalies") or []:
            amount = _decimal(f.get("amount_sui"))
            digest = f.get("transaction_digest")
            if amount is None or not isinstance(digest, str):
                continue
            findings.append({
                "transaction_digest": digest,
                "direction": f.get("direction") if f.get("direction") in ("in", "out") else None,
                "amount_sui": amount,
                "threshold_sui": _decimal(f.get("threshold_sui")),
                "robust_z": f.get("robust_z") if isinstance(f.get("robust_z"), (int, float)) else None,
                "severity": f.get("severity", "medium"),
                "severity_without_memory": f.get("severity_without_memory"),
                "state": f.get("state") or "open",
                "confidence": f.get("confidence") if isinstance(f.get("confidence"), (int, float)) else None,
                "counterparty": f.get("counterparty") if isinstance(f.get("counterparty"), str) else None,
                "rule_version": f.get("rule_version") or analysis.get("rule_version") or "unknown",
                "memory_ids": [c["memory_id"] for c in f.get("memory_context") or [] if isinstance(c.get("memory_id"), str)],
            })
        return cls(
            id=str(result["wallet_id"]),
            namespace=namespace,
            address=result["address"],
            network=str(snapshot.get("network") or "unknown"),
            checkpoint_height=snapshot.get("checkpoint_height"),
            balance_sui=_decimal(snapshot.get("balance")),
            activity_count=int(snapshot.get("activity_count") or 0),
            history_truncated=bool(analysis.get("history_truncated")),
            status=analysis.get("status", "complete"),
            partial_reasons=list(analysis.get("partial_reasons") or []),
            rule_version=analysis.get("rule_version", "unknown"),
            memory_rule_version=memory.get("rule_version") if memory.get("changed_result") else None,
            memory_status=memory.get("status", "unknown"),
            baseline=analysis.get("baseline") or {},
            findings=findings,
        )


def _summary(record: InvestigationRecord, created_at: datetime) -> dict[str, Any]:
    severities = [f["severity"] for f in record.findings]
    return {
        "investigation_id": record.id,
        "address": record.address,
        "created_at": _iso(created_at),
        "network": record.network,
        "checkpoint_height": record.checkpoint_height,
        "balance_sui": _text(record.balance_sui),
        "activity_count": record.activity_count,
        "status": record.status,
        "partial_reasons": record.partial_reasons,
        "rule_version": record.rule_version,
        "memory_status": record.memory_status,
        "anomaly_count": len(record.findings),
        "highest_severity": next((s for s in ("high", "medium", "low") if s in severities), None),
    }


def _finding_out(f: dict[str, Any]) -> dict[str, Any]:
    return {**f, "amount_sui": _text(f["amount_sui"]), "threshold_sui": _text(f.get("threshold_sui"))}


class InMemoryStore:
    durable = False
    backend = "process_memory"

    def __init__(self) -> None:
        self._jobs: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._investigations: dict[str, OrderedDict[str, tuple[InvestigationRecord, datetime]]] = {}

    async def startup(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def record_job(self, job_id: str, namespace: str, memory_type: str) -> None:
        existing = self._jobs.get(job_id)
        if existing and existing["namespace"] != namespace:
            raise StoreUnavailable("job id collision across workspaces")
        self._jobs[job_id] = existing or {"namespace": namespace, "memory_type": memory_type, "status": "pending", "blob_id": None}
        self._jobs.move_to_end(job_id)
        while len(self._jobs) > MEMORY_MAX_JOBS:
            self._jobs.popitem(last=False)

    async def job_owner(self, job_id: str) -> str | None:
        job = self._jobs.get(job_id)
        return job["namespace"] if job else None

    async def update_job(self, job_id: str, namespace: str, status: str, blob_id: str | None) -> None:
        job = self._jobs.get(job_id)
        if job and job["namespace"] == namespace:
            job.update(status=status, blob_id=blob_id)

    async def forget_jobs(self, namespace: str) -> int:
        doomed = [k for k, v in self._jobs.items() if v["namespace"] == namespace]
        for key in doomed:
            del self._jobs[key]
        return len(doomed)

    async def save_investigation(self, record: InvestigationRecord) -> str:
        bucket = self._investigations.setdefault(record.namespace, OrderedDict())
        bucket[record.id] = (record, _now())
        while len(bucket) > MEMORY_MAX_INVESTIGATIONS_PER_WORKSPACE:
            bucket.popitem(last=False)
        return record.id

    async def list_investigations(self, namespace: str, address: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        rows = [(r, at) for r, at in self._investigations.get(namespace, {}).values() if address is None or r.address == address]
        rows.sort(key=lambda item: item[1], reverse=True)
        return [_summary(r, at) for r, at in rows[:limit]]

    async def get_investigation(self, namespace: str, investigation_id: str) -> dict[str, Any] | None:
        item = self._investigations.get(namespace, {}).get(investigation_id)
        if not item:
            return None
        record, at = item
        return {**_summary(record, at), "baseline": record.baseline, "findings": [_finding_out(f) for f in record.findings]}

    async def delete_investigations(self, namespace: str) -> int:
        return len(self._investigations.pop(namespace, {}))

    async def recent_findings(self, namespace: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = sorted(self._investigations.get(namespace, {}).values(), key=lambda item: item[1], reverse=True)
        out = []
        for record, at in rows:
            for f in record.findings:
                out.append({**_finding_out(f), "investigation_id": record.id, "address": record.address, "created_at": _iso(at)})
        return out[:limit]


class PostgresStore:
    durable = True
    backend = "postgresql"

    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 5, command_timeout: float = 5.0) -> None:
        self._dsn = dsn
        self._min, self._max, self._timeout = min_size, max_size, command_timeout
        self._pool = None

    async def startup(self) -> None:
        import asyncpg

        try:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=self._min, max_size=self._max,
                                                   command_timeout=self._timeout, timeout=10)
            await self.migrate()
        except Exception as exc:
            await self.close()
            raise StoreUnavailable(f"database startup failed ({type(exc).__name__})") from None

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def migrate(self) -> list[str]:
        applied_now = []
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock($1)", MIGRATION_LOCK_ID)
            await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            done = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.stem in done:
                    continue
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", path.stem)
                applied_now.append(path.stem)
        if applied_now:
            logger.info("database migrations applied: %s", ", ".join(applied_now))
        return applied_now

    def _require_pool(self):
        if self._pool is None:
            raise StoreUnavailable("database is not connected")
        return self._pool

    async def _run(self, operation):
        try:
            async with self._require_pool().acquire() as conn:
                return await operation(conn)
        except StoreUnavailable:
            raise
        except Exception as exc:  # driver/network errors: never leak DSNs or SQL
            raise StoreUnavailable(f"database request failed ({type(exc).__name__})") from None

    async def ping(self) -> bool:
        try:
            return await self._run(lambda conn: conn.fetchval("SELECT 1")) == 1
        except StoreUnavailable:
            return False

    @staticmethod
    async def _touch_workspace(conn, namespace: str) -> None:
        await conn.execute(
            "INSERT INTO workspaces (namespace) VALUES ($1) ON CONFLICT (namespace) DO UPDATE SET last_seen_at = now()",
            namespace,
        )

    async def record_job(self, job_id: str, namespace: str, memory_type: str) -> None:
        async def op(conn):
            async with conn.transaction():
                await self._touch_workspace(conn, namespace)
                owner = await conn.fetchval(
                    "INSERT INTO memory_jobs (job_id, namespace, memory_type) VALUES ($1, $2, $3) "
                    "ON CONFLICT (job_id) DO UPDATE SET updated_at = now() RETURNING namespace",
                    job_id, namespace, memory_type,
                )
                if owner != namespace:
                    raise StoreUnavailable("job id collision across workspaces")
        await self._run(op)

    async def job_owner(self, job_id: str) -> str | None:
        return await self._run(lambda conn: conn.fetchval("SELECT namespace FROM memory_jobs WHERE job_id = $1", job_id))

    async def update_job(self, job_id: str, namespace: str, status: str, blob_id: str | None) -> None:
        await self._run(lambda conn: conn.execute(
            "UPDATE memory_jobs SET status = $3, blob_id = $4, updated_at = now() WHERE job_id = $1 AND namespace = $2",
            job_id, namespace, status, blob_id,
        ))

    async def forget_jobs(self, namespace: str) -> int:
        result = await self._run(lambda conn: conn.execute("DELETE FROM memory_jobs WHERE namespace = $1", namespace))
        return int(result.split()[-1])

    async def save_investigation(self, record: InvestigationRecord) -> str:
        async def op(conn):
            async with conn.transaction():
                await self._touch_workspace(conn, record.namespace)
                await conn.execute(
                    "INSERT INTO investigations (id, namespace, address, network, checkpoint_height, balance_sui, activity_count, "
                    "history_truncated, status, partial_reasons, rule_version, memory_rule_version, memory_status, anomaly_count, baseline) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb)",
                    uuid.UUID(record.id), record.namespace, record.address, record.network, record.checkpoint_height,
                    record.balance_sui, record.activity_count, record.history_truncated, record.status, record.partial_reasons,
                    record.rule_version, record.memory_rule_version, record.memory_status, len(record.findings),
                    json.dumps(record.baseline),
                )
                if record.findings:
                    await conn.executemany(
                        "INSERT INTO findings (investigation_id, transaction_digest, direction, amount_sui, threshold_sui, robust_z, "
                        "severity, severity_without_memory, state, confidence, counterparty, rule_version, memory_ids) "
                        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13) ON CONFLICT (investigation_id, transaction_digest) DO NOTHING",
                        [(uuid.UUID(record.id), f["transaction_digest"], f["direction"], f["amount_sui"], f["threshold_sui"], f["robust_z"],
                          f["severity"], f["severity_without_memory"], f["state"], f["confidence"], f["counterparty"],
                          f["rule_version"], f["memory_ids"]) for f in record.findings],
                    )
            return record.id
        return await self._run(op)

    @staticmethod
    def _summary_row(row) -> dict[str, Any]:
        return {
            "investigation_id": str(row["id"]),
            "address": row["address"],
            "created_at": _iso(row["created_at"]),
            "network": row["network"],
            "checkpoint_height": row["checkpoint_height"],
            "balance_sui": _text(row["balance_sui"]),
            "activity_count": row["activity_count"],
            "status": row["status"],
            "partial_reasons": list(row["partial_reasons"]),
            "rule_version": row["rule_version"],
            "memory_status": row["memory_status"],
            "anomaly_count": row["anomaly_count"],
            "highest_severity": row["highest_severity"],
        }

    _SUMMARY_SQL = (
        "SELECT i.*, (SELECT f.severity FROM findings f WHERE f.investigation_id = i.id "
        "ORDER BY CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END LIMIT 1) AS highest_severity "
        "FROM investigations i"
    )

    async def list_investigations(self, namespace: str, address: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, MAX_HISTORY))

        async def op(conn):
            if address:
                return await conn.fetch(f"{self._SUMMARY_SQL} WHERE i.namespace = $1 AND i.address = $2 ORDER BY i.created_at DESC LIMIT $3", namespace, address, limit)
            return await conn.fetch(f"{self._SUMMARY_SQL} WHERE i.namespace = $1 ORDER BY i.created_at DESC LIMIT $2", namespace, limit)
        return [self._summary_row(r) for r in await self._run(op)]

    @staticmethod
    def _finding_row(row) -> dict[str, Any]:
        return {
            "transaction_digest": row["transaction_digest"],
            "direction": row["direction"],
            "amount_sui": _text(row["amount_sui"]),
            "threshold_sui": _text(row["threshold_sui"]),
            "robust_z": row["robust_z"],
            "severity": row["severity"],
            "severity_without_memory": row["severity_without_memory"],
            "state": row["state"],
            "confidence": row["confidence"],
            "counterparty": row["counterparty"],
            "rule_version": row["rule_version"],
            "memory_ids": list(row["memory_ids"]),
        }

    async def get_investigation(self, namespace: str, investigation_id: str) -> dict[str, Any] | None:
        async def op(conn):
            row = await conn.fetchrow(f"{self._SUMMARY_SQL} WHERE i.namespace = $1 AND i.id = $2", namespace, uuid.UUID(investigation_id))
            if row is None:
                return None
            findings = await conn.fetch(
                "SELECT * FROM findings WHERE investigation_id = $1 "
                "ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, amount_sui DESC", row["id"])
            baseline = row["baseline"]
            return {**self._summary_row(row), "baseline": json.loads(baseline) if isinstance(baseline, str) else baseline,
                    "findings": [self._finding_row(f) for f in findings]}
        return await self._run(op)

    async def delete_investigations(self, namespace: str) -> int:
        result = await self._run(lambda conn: conn.execute("DELETE FROM investigations WHERE namespace = $1", namespace))
        return int(result.split()[-1])

    async def recent_findings(self, namespace: str, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, MAX_HISTORY))
        rows = await self._run(lambda conn: conn.fetch(
            "SELECT f.*, i.id AS inv_id, i.address, i.created_at FROM findings f JOIN investigations i ON i.id = f.investigation_id "
            "WHERE i.namespace = $1 ORDER BY i.created_at DESC, f.id LIMIT $2", namespace, limit))
        return [{**self._finding_row(r), "investigation_id": str(r["inv_id"]), "address": r["address"], "created_at": _iso(r["created_at"])} for r in rows]


Store = InMemoryStore | PostgresStore


class _StoreHolder:
    """The active store. Replaced at startup when DATABASE_URL is configured."""

    current: Store = InMemoryStore()


store_holder = _StoreHolder()


def get_store() -> Store:
    return store_holder.current
