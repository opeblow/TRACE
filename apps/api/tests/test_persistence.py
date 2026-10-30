"""Investigation history, workspace isolation, memory job ownership, concurrency and error shape.

Runs against the in-process store by default. Set TRACE_TEST_DATABASE_URL to a disposable
PostgreSQL database to also run the same checks against PostgresStore.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from memwal.mock import MemWalMock

from app.db.store import InMemoryStore, InvestigationRecord, PostgresStore, store_holder
from app.main import _analysis_requests, app
from app.routers import wallets
from app.services.memory import MemoryService, build_envelope, encode, memory_service, workspace_namespace
from app.services.tatum import BalanceChange, ChainInfo, TransactionRecord, WalletFetch

client = TestClient(app)
WALLET = "0x" + "1" * 64
OTHER_WALLET = "0x" + "2" * 64
EXCHANGE = "0x" + "e" * 64
SUI = "0x2::sui::SUI"
WS_A = "persistA_" + "a" * 23
WS_B = "persistB_" + "b" * 23
PG_URL = os.environ.get("TRACE_TEST_DATABASE_URL", "")


def transfer(i: int, sui: int) -> TransactionRecord:
    mist = sui * 1_000_000_000
    return TransactionRecord(
        digest=f"Tx{i:040d}".replace("0", "z"), timestamp_ms=1_000 + i, checkpoint=i, status="success", sender=WALLET,
        balance_changes=[BalanceChange(WALLET, SUI, str(-mist)), BalanceChange(EXCHANGE, SUI, str(mist))],
    )


def scenario() -> WalletFetch:
    history = [transfer(i, 1) for i in range(1, 13)] + [transfer(20, 5_000)]
    return WalletFetch(ChainInfo("mainnet", "chain", 7), "9000000000", history, False)


@pytest.fixture(autouse=True)
def providers(monkeypatch):
    _analysis_requests.clear()
    walrus = MemWalMock.create(namespace="unused-default")
    monkeypatch.setattr(memory_service, "_client_factory", lambda _ns: walrus)
    monkeypatch.setattr(memory_service, "_local_jobs", type(memory_service._local_jobs)())
    monkeypatch.setattr(wallets.tatum_service, "api_key", "test-key")
    monkeypatch.setattr(wallets.tatum_service, "fetch_wallet", AsyncMock(return_value=scenario()))
    monkeypatch.setattr(store_holder, "current", InMemoryStore())
    yield walrus
    _analysis_requests.clear()


def analyze(workspace: str | None) -> dict:
    headers = {"X-Trace-Workspace": workspace} if workspace else {}
    response = client.post("/api/v1/wallets/analyze", json={"address": WALLET}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --- Investigation history ------------------------------------------------------

def test_analysis_is_saved_to_the_workspace_history():
    result = analyze(WS_A)
    assert result["history"]["saved"] is True and result["history"]["durable"] is False
    listing = client.get("/api/v1/investigations", headers={"X-Trace-Workspace": WS_A}).json()
    assert [i["investigation_id"] for i in listing["investigations"]] == [result["wallet_id"]]
    summary = listing["investigations"][0]
    assert summary["address"] == WALLET and summary["anomaly_count"] == 1 and summary["highest_severity"] == "high"
    detail = client.get(f"/api/v1/investigations/{result['wallet_id']}", headers={"X-Trace-Workspace": WS_A}).json()
    assert detail["findings"][0]["amount_sui"] == "5000"
    assert detail["baseline"]["rule_version"] == "amount-outlier-v2"


def test_analysis_without_workspace_is_not_saved():
    assert analyze(None)["history"] == {"saved": False, "reason": "no_workspace"}


def test_history_is_isolated_between_workspaces():
    result = analyze(WS_A)
    other = {"X-Trace-Workspace": WS_B}
    assert client.get("/api/v1/investigations", headers=other).json()["investigations"] == []
    assert client.get(f"/api/v1/investigations/{result['wallet_id']}", headers=other).status_code == 404
    assert client.request("DELETE", "/api/v1/investigations", json={"confirm": "DELETE"}, headers=other).json()["deleted"] == 0
    assert client.get(f"/api/v1/investigations/{result['wallet_id']}", headers={"X-Trace-Workspace": WS_A}).status_code == 200
    assert client.get("/api/v1/alerts", headers=other).json()["alerts"] == []
    assert len(client.get("/api/v1/alerts", headers={"X-Trace-Workspace": WS_A}).json()["alerts"]) == 1


def test_history_requires_a_valid_workspace_and_inputs():
    assert client.get("/api/v1/investigations").status_code == 400
    assert client.get("/api/v1/investigations", headers={"X-Trace-Workspace": "short"}).status_code == 400
    headers = {"X-Trace-Workspace": WS_A}
    assert client.get("/api/v1/investigations?address=0xnothex", headers=headers).status_code == 400
    assert client.get("/api/v1/investigations/not-a-uuid", headers=headers).status_code == 404
    assert client.get("/api/v1/investigations?limit=1000", headers=headers).status_code == 422


def test_deleting_history_requires_confirmation_and_removes_records():
    analyze(WS_A)
    headers = {"X-Trace-Workspace": WS_A}
    assert client.request("DELETE", "/api/v1/investigations", json={}, headers=headers).status_code == 422
    assert client.request("DELETE", "/api/v1/investigations", json={"confirm": "DELETE"}, headers=headers).json()["deleted"] == 1
    assert client.get("/api/v1/investigations", headers=headers).json()["investigations"] == []


def test_storage_failure_never_fails_the_analysis(monkeypatch):
    from app.db.store import StoreUnavailable

    broken = InMemoryStore()
    monkeypatch.setattr(broken, "save_investigation", AsyncMock(side_effect=StoreUnavailable("down")))
    monkeypatch.setattr(store_holder, "current", broken)
    result = analyze(WS_A)
    assert result["history"]["saved"] is False and result["history"]["reason"] == "storage_unavailable"
    assert result["analysis"]["anomaly_count"] == 1


# --- Memory job ownership ---------------------------------------------------------

class NamespacelessClient:
    """Provider that never reports a job's namespace, so TRACE must enforce ownership itself."""

    def __init__(self):
        self.jobs = {}

    async def remember(self, text, namespace=None, idempotency_key=None):
        job_id = f"job{len(self.jobs) + 1}"
        self.jobs[job_id] = namespace
        return SimpleNamespace(job_id=job_id)

    async def get_remember_status(self, job_id):
        if job_id not in self.jobs:
            return SimpleNamespace(status="not_found", namespace=None, blob_id=None)
        return SimpleNamespace(status="done", namespace=None, blob_id=f"blob-{job_id}")


def test_job_from_another_workspace_is_hidden_even_without_provider_namespace(monkeypatch):
    provider = NamespacelessClient()
    monkeypatch.setattr(memory_service, "_client_factory", lambda _ns: provider)
    accepted = client.post("/api/v1/memories", json={"memory_type": "counterparty_label", "wallet": WALLET, "subject": EXCHANGE,
                                                     "value": "Exchange", "consent": True}, headers={"X-Trace-Workspace": WS_A})
    job_id = accepted.json()["job_id"]
    assert client.get(f"/api/v1/memories/jobs/{job_id}", headers={"X-Trace-Workspace": WS_B}).status_code == 404
    mine = client.get(f"/api/v1/memories/jobs/{job_id}", headers={"X-Trace-Workspace": WS_A})
    assert mine.status_code == 200 and mine.json()["status"] == "succeeded"


def test_unknown_owner_and_no_provider_namespace_fails_closed(monkeypatch):
    provider = NamespacelessClient()
    provider.jobs["orphan"] = "someone-else"
    monkeypatch.setattr(memory_service, "_client_factory", lambda _ns: provider)
    assert client.get("/api/v1/memories/jobs/orphan", headers={"X-Trace-Workspace": WS_A}).status_code == 404


def test_job_ownership_survives_a_restart_through_the_store(monkeypatch):
    provider = NamespacelessClient()
    shared_store = InMemoryStore()
    monkeypatch.setattr(store_holder, "current", shared_store)
    first = MemoryService(client_factory=lambda _ns: provider)
    envelope = build_envelope("counterparty_label", WALLET, EXCHANGE, "Exchange")
    job_id = asyncio.run(first.write(WS_A, envelope))
    restarted = MemoryService(client_factory=lambda _ns: provider)  # empty in-process registry
    assert asyncio.run(restarted.job_status(WS_A, job_id))["status"] == "succeeded"
    assert asyncio.run(restarted.job_status(WS_B, job_id))["status"] == "not_found"


def test_concurrent_writes_each_get_an_owned_job(providers):
    service = MemoryService(client_factory=lambda _ns: providers)

    async def burst():
        envelopes = [build_envelope("counterparty_label", WALLET, "0x" + f"{i:064x}", f"label {i}") for i in range(1, 21)]
        return await asyncio.gather(*(service.write(WS_A, e) for e in envelopes))

    job_ids = asyncio.run(burst())
    assert len(set(job_ids)) == 20
    async def poll_all():
        return await asyncio.gather(*(service.job_status(WS_A, j) for j in job_ids))

    statuses = asyncio.run(poll_all())
    assert all(s["status"] == "succeeded" for s in statuses)
    assert len(asyncio.run(service.recall(WS_A, wallet=WALLET))) == 20


def test_duplicate_stored_records_are_recalled_once(providers):
    namespace = workspace_namespace(WS_A)
    text = encode(build_envelope("counterparty_label", WALLET, EXCHANGE, "Exchange"))

    async def store_twice():
        await providers.remember(text, namespace=namespace)
        await providers.remember(text, namespace=namespace)  # e.g. a retried request after a timeout

    asyncio.run(store_twice())
    assert len(asyncio.run(memory_service.recall(WS_A, wallet=WALLET))) == 1


def test_failed_job_is_reported_as_failed_not_saved(monkeypatch):
    provider = NamespacelessClient()

    async def failed(job_id):
        return SimpleNamespace(status="failed", namespace=None, blob_id=None)

    provider.get_remember_status = failed
    monkeypatch.setattr(memory_service, "_client_factory", lambda _ns: provider)
    accepted = client.post("/api/v1/memories", json={"memory_type": "counterparty_label", "wallet": WALLET, "subject": EXCHANGE,
                                                     "value": "Exchange", "consent": True}, headers={"X-Trace-Workspace": WS_A})
    status = client.get(f"/api/v1/memories/jobs/{accepted.json()['job_id']}", headers={"X-Trace-Workspace": WS_A}).json()
    assert status["status"] == "failed" and status["blob_id"] is None


def test_forget_reports_index_removal_not_blob_erasure():
    body = client.request("DELETE", "/api/v1/memories", json={"confirm": "DELETE"}, headers={"X-Trace-Workspace": WS_A}).json()
    assert body["index_removed"] is True and body["blobs_erased"] is False and body["chain_records_affected"] is False


# --- Error shape and input echo -------------------------------------------------

def test_validation_errors_are_structured_and_do_not_echo_input():
    secret_like = "my recovery phrase is " + "abandon " * 50
    response = client.post("/api/v1/memories", json={"memory_type": "counterparty_label", "wallet": WALLET, "subject": EXCHANGE,
                                                    "value": secret_like, "consent": True}, headers={"X-Trace-Workspace": WS_A})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_failed" and body["error"]["fields"][0]["field"] == "value"
    assert "abandon" not in response.text


def test_http_errors_share_the_envelope():
    response = client.get("/api/v1/memories/jobs/x", headers={"X-Trace-Workspace": "bad"})
    body = response.json()
    assert response.status_code == 400
    assert body["detail"] == body["error"]["message"] and body["error"]["code"] == "bad_request"
    assert body["error"]["retryable"] is False


# --- PostgreSQL (opt-in) ----------------------------------------------------------

def _record(namespace: str, address: str = WALLET) -> InvestigationRecord:
    result = analyze(None)
    result["wallet_id"] = str(uuid.uuid4())
    result["address"] = address
    return InvestigationRecord.from_analysis(namespace, result)


@pytest.mark.skipif(not PG_URL, reason="set TRACE_TEST_DATABASE_URL to a disposable PostgreSQL database")
def test_postgres_store_end_to_end():
    ns_a, ns_b = workspace_namespace(WS_A), workspace_namespace(WS_B)
    records = [_record(ns_a), _record(ns_a, OTHER_WALLET), _record(ns_b)]

    async def scenario_run():
        store = PostgresStore(PG_URL)
        await store.startup()
        try:
            assert await store.migrate() == []  # second run applies nothing
            await store.delete_investigations(ns_a)
            await store.delete_investigations(ns_b)
            await asyncio.gather(*(store.save_investigation(r) for r in records))  # concurrent transactions
            listed = await store.list_investigations(ns_a)
            assert {i["investigation_id"] for i in listed} == {records[0].id, records[1].id}
            assert [i["address"] for i in await store.list_investigations(ns_a, OTHER_WALLET)] == [OTHER_WALLET]
            detail = await store.get_investigation(ns_a, records[0].id)
            assert detail["findings"][0]["amount_sui"] == "5000" and detail["baseline"]["rule_version"] == "amount-outlier-v2"
            assert await store.get_investigation(ns_b, records[0].id) is None
            assert len(await store.recent_findings(ns_a)) == 2

            await store.record_job("pgjob1", ns_a, "counterparty_label")
            await store.record_job("pgjob1", ns_a, "counterparty_label")  # idempotent
            assert await store.job_owner("pgjob1") == ns_a
            from app.db.store import StoreUnavailable
            with pytest.raises(StoreUnavailable):
                await store.record_job("pgjob1", ns_b, "counterparty_label")
            await store.update_job("pgjob1", ns_a, "succeeded", "blob-1")
            assert await store.forget_jobs(ns_a) == 1

            assert await store.delete_investigations(ns_a) == 2
            assert await store.recent_findings(ns_a) == []  # findings cascade with their investigation
            assert len(await store.list_investigations(ns_b)) == 1
            await store.delete_investigations(ns_b)
            assert await store.ping() is True
        finally:
            await store.close()

    asyncio.run(scenario_run())
