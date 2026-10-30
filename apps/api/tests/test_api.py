import asyncio
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import grpc
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.main import _analysis_requests, app
from app.routers import wallets
from app.routers.wallets import mist_to_sui, native_sui_balance, normalize_activity
from app.services.anomaly import AnomalyDetectionService
from app.services.tatum import (
    BalanceChange,
    ChainInfo,
    TatumProviderError,
    TatumService,
    TransactionRecord,
    WalletFetch,
    canonical_coin_type,
    message_class,
    parse_transaction,
)

client = TestClient(app)
VALID_ADDRESS = "0x" + "1" * 64
LONG_SUI = "0x" + "0" * 63 + "2::sui::SUI"
API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    _analysis_requests.clear()
    yield
    _analysis_requests.clear()


def tx(digest, mist, status="success", address=VALID_ADDRESS, coin_type=LONG_SUI, timestamp_ms=1_000):
    return TransactionRecord(
        digest=digest,
        timestamp_ms=timestamp_ms,
        checkpoint=1,
        status=status,
        sender=address,
        balance_changes=[BalanceChange(address=address, coin_type=coin_type, amount=str(mist))],
    )


def mainnet_fetch(transactions, balance="1500000000", has_more=False, chain="mainnet"):
    return WalletFetch(
        chain=ChainInfo(chain=chain, chain_id="test-chain", checkpoint_height=42),
        sui_balance_mist=balance,
        transactions=transactions,
        has_more=has_more,
    )


def use_fetch(monkeypatch, result=None, error=None):
    monkeypatch.setattr(wallets.tatum_service, "api_key", "test-key")
    mock = AsyncMock(return_value=result, side_effect=error)
    monkeypatch.setattr(wallets.tatum_service, "fetch_wallet", mock)
    return mock


# --- Health, security headers, and honest capability reporting ---------------

def test_health_reports_capabilities_with_security_headers():
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["capabilities"]["walrus_memory"] in ("configured", "not_configured")
        assert data["capabilities"]["authentication"] == "not_implemented"
        assert data["capabilities"]["wallet_data_source"] == "tatum_sui_grpc"
        assert "key" not in str(data).lower().replace("tatum_credentials_present", "")
        assert response.headers.get("x-request-id")
        assert response.headers.get("cache-control") == "no-store"
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_readiness_depends_on_provider_credentials(monkeypatch):
    # Independent of any local .env: CI has no Tatum key, developer machines may.
    monkeypatch.setattr("app.main.settings.TATUM_MAINNET_API_KEY", "test-key")
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True

    monkeypatch.setattr("app.main.settings.TATUM_MAINNET_API_KEY", "")
    not_ready = client.get("/ready")
    assert not_ready.status_code == 503
    assert not_ready.json()["checks"]["tatum_credentials"] is False
    assert "test-key" not in not_ready.text


def test_alert_history_is_not_claimed_and_memory_needs_a_workspace():
    alerts = client.get("/api/v1/alerts")
    assert alerts.status_code == 200
    assert alerts.json()["available"] is False
    assert client.get("/api/v1/memories").status_code == 400
    assert client.post("/api/v1/memories", json={"type": "label", "summary": "test"}).status_code == 422
    assert client.post("/api/v1/alerts/missing/feedback", json={"wallet": VALID_ADDRESS, "label": "expected", "consent": True}).status_code == 400
    identity = client.get("/api/v1/me")
    assert identity.status_code == 501
    assert "no user identity" in identity.json()["detail"]


def test_untrusted_hosts_and_origins_are_rejected():
    assert client.get("/ready", headers={"Host": "evil.example"}).status_code == 400
    assert client.post("/api/v1/wallets/analyze", json={"address": "x"}, headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/health", headers={"Host": "10.0.0.5:10000"}).status_code == 200  # platform probe
    preflight = client.options(
        "/api/v1/wallets/analyze",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in preflight.headers


# --- Input validation (FR-01) -------------------------------------------------

@pytest.mark.parametrize("address", [
    "0x123",
    "0x" + "g" * 64,
    "1" * 66,
    "0x" + "1" * 65,
    "0x" + "1" * 63,
    "<script>alert(1)</script>",
    "0x" + "1" * 64 + "\x00",
])
def test_analysis_rejects_invalid_address_before_provider_call(monkeypatch, address):
    provider = use_fetch(monkeypatch)
    response = client.post("/api/v1/wallets/analyze", json={"address": address})
    assert response.status_code == 400
    provider.assert_not_awaited()


def test_analysis_rejects_unknown_fields_and_bad_json(monkeypatch):
    provider = use_fetch(monkeypatch)
    assert client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS, "admin": True}).status_code == 422
    bad = client.post("/api/v1/wallets/analyze", content=b"{nope", headers={"content-type": "application/json"})
    assert bad.status_code == 422
    provider.assert_not_awaited()


def test_analysis_requires_provider_configuration(monkeypatch):
    monkeypatch.setattr(wallets.tatum_service, "api_key", "")
    response = client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS})
    assert response.status_code == 503


# --- Normalization, provenance, and decimal safety (FR-03, FR-04) ------------

def test_analysis_normalizes_balance_and_marks_thin_history_partial(monkeypatch):
    use_fetch(monkeypatch, mainnet_fetch([tx("digest-1", 250_000_000)]))
    response = client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS.upper().replace("0X", "0x")})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["address"] == VALID_ADDRESS
    assert result["snapshot"]["balance"] == "1.5"
    assert result["snapshot"]["balance_unit"] == "SUI"
    assert result["snapshot"]["network"] == "mainnet"
    assert result["snapshot"]["checkpoint_height"] == 42
    assert result["snapshot"]["sources"] == ["tatum_sui_grpc"]
    assert result["analysis"]["status"] == "partial"
    assert result["analysis"]["baseline"]["status"] == "thin_history"
    item = result["activity"]["items"][0]
    assert item["amount_sui"] == "0.25"
    assert item["direction"] == "in"
    assert result["evidence"] == []


def test_amounts_are_exact_decimal_strings():
    assert mist_to_sui(1) == "0.000000001"
    assert mist_to_sui(-123_456_789_012) == "-123.456789012"
    assert mist_to_sui(10**28) == "10000000000000000000"
    assert mist_to_sui(0) == "0"
    assert native_sui_balance(None) is None
    with pytest.raises(ValueError):
        native_sui_balance("-1")
    with pytest.raises(ValueError):
        mist_to_sui("NaN")
    with pytest.raises(ValueError):
        mist_to_sui("1.5")


def test_long_and_short_sui_coin_types_are_equivalent():
    assert canonical_coin_type(LONG_SUI) == "0x2::sui::SUI"
    assert canonical_coin_type("0x2::sui::SUI") == "0x2::sui::SUI"
    assert canonical_coin_type("0xABC::x::Y") == "0xabc::x::Y"
    assert canonical_coin_type("not-a-type") == "not-a-type"


def test_activity_normalization_handles_failures_other_coins_and_other_owners():
    other = "0x" + "2" * 64
    items = normalize_activity([
        tx("in", 2_000_000_000),
        tx("out", -500_000_000, coin_type="0x2::sui::SUI"),
        tx("failed", -100, status="failure"),
        tx("usdc", 99, coin_type="0xdba3::usdc::USDC"),
        tx("someone-else", 99, address=other),
        TransactionRecord(digest="no-changes", timestamp_ms=None, checkpoint=None, status=None, sender=None),
    ], VALID_ADDRESS)
    by_digest = {item["digest"]: item for item in items}
    assert by_digest["in"]["amount_sui"] == "2" and by_digest["in"]["direction"] == "in"
    assert by_digest["out"]["amount_sui"] == "-0.5" and by_digest["out"]["direction"] == "out"
    for digest in ("failed", "usdc", "someone-else", "no-changes"):
        assert by_digest[digest]["amount_sui"] is None, digest
    assert by_digest["no-changes"]["timestamp_ms"] is None


def test_activity_normalization_rejects_non_integer_amounts():
    for bad in ("Infinity", "1.5", "abc"):
        with pytest.raises(Exception):
            normalize_activity([tx("bad", bad)], VALID_ADDRESS)


def test_malformed_provider_amount_returns_safe_502(monkeypatch):
    use_fetch(monkeypatch, mainnet_fetch([tx("bad", "Infinity")]))
    response = client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS})
    assert response.status_code == 502
    assert "Reference:" in response.json()["detail"]


def test_non_mainnet_provider_is_refused(monkeypatch):
    use_fetch(monkeypatch, mainnet_fetch([], chain="testnet"))
    response = client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS})
    assert response.status_code == 502
    assert "Mainnet" in response.json()["detail"]


def test_provider_errors_are_redacted_and_have_reference(monkeypatch):
    use_fetch(monkeypatch, error=TatumProviderError("private provider detail"))
    monkeypatch.setattr(wallets.tatum_service, "api_key", "super-secret-test-key")
    response = client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS})
    assert response.status_code == 502
    assert "Reference:" in response.json()["detail"]
    assert "super-secret-test-key" not in response.text
    assert "private provider detail" not in response.text


def test_bounded_history_is_reported_as_partial(monkeypatch):
    history = [tx(f"d{i}", 1_000_000_000) for i in range(12)]
    use_fetch(monkeypatch, mainnet_fetch(history, has_more=True))
    result = client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS}).json()
    assert result["activity"]["has_more"] is True
    assert result["analysis"]["history_truncated"] is True
    assert "provider_has_more_history" in result["analysis"]["partial_reasons"]


# --- Anomaly rule (FR-06, FR-07) ---------------------------------------------

def test_anomaly_service_requires_interpretable_history_and_evidence():
    service = AnomalyDetectionService()
    too_short = service.establish_baseline([{"amount_sui": "-1"}] * 9)
    assert too_short["status"] == "thin_history"
    assert service.detect_anomalies([{"amount_sui": "-999", "digest": "x"}], too_short) == []
    history = [{"amount_sui": "-1.0", "digest": f"normal-{i}"} for i in range(10)]
    baseline = service.establish_baseline(history)
    finding = service.detect_anomalies(history + [{"amount_sui": "-4", "digest": "outlier"}], baseline)
    assert baseline["status"] == "established"
    assert baseline["directions"]["out"]["spread_floor_applied"] is True
    assert len(finding) == 1
    assert finding[0]["evidence"][0]["ref"] == "outlier"
    assert finding[0]["evidence"][0]["source"] == "tatum_sui_grpc"
    assert finding[0]["amount_sui"] == "4"
    assert finding[0]["direction"] == "out"
    assert finding[0]["rule_version"] == "amount-outlier-v2"
    assert 0 < finding[0]["confidence"] <= 1
    assert finding[0]["uncertainty"] == round(1 - finding[0]["confidence"], 2)
    assert len(finding[0]["confidence_factors"]) == 2
    assert "not evidence of malicious activity" in finding[0]["rationale"]


def test_gas_only_transactions_do_not_distort_the_baseline():
    service = AnomalyDetectionService()
    gas_only = [{"amount_sui": "-0.002", "transfer_amount_sui": "0", "activity_kind": "gas_only", "direction": "out", "digest": f"g{i}"} for i in range(40)]
    transfers = [{"amount_sui": f"-{v}", "direction": "out", "activity_kind": "transfer", "digest": f"t{i}"} for i, v in enumerate([5, 6, 5, 7, 6, 5, 6, 7, 5, 6])]
    baseline = service.establish_baseline(gas_only + transfers)
    assert baseline["excluded"]["gas_only"] == 40
    assert baseline["directions"]["out"]["sample_count"] == 10
    assert baseline["directions"]["out"]["median_sui"] == "6"
    # An ordinary 7 SUI transfer must not be flagged just because gas payments are tiny.
    assert service.detect_anomalies(gas_only + transfers, baseline) == []


def test_incoming_and_outgoing_have_separate_baselines():
    service = AnomalyDetectionService()
    incoming = [{"amount_sui": "0.5", "direction": "in", "digest": f"i{i}"} for i in range(12)]
    outgoing = [{"amount_sui": f"-{v}", "direction": "out", "digest": f"o{i}"} for i, v in enumerate([50, 55, 48, 52, 51, 49, 53, 50, 54, 47])]
    baseline = service.establish_baseline(incoming + outgoing)
    assert baseline["assessed_directions"] == ["in", "out"]
    # Normal outgoing amounts are 100x incoming ones but are judged against outgoing history only.
    assert service.detect_anomalies(incoming + outgoing, baseline) == []
    spike = {"amount_sui": "40", "direction": "in", "digest": "big-in"}
    found = service.detect_anomalies([spike], baseline)
    assert [f["transaction_digest"] for f in found] == ["big-in"]
    assert found[0]["severity"] == "high"


def test_direction_with_thin_history_is_not_assessed():
    service = AnomalyDetectionService()
    history = [{"amount_sui": "1", "direction": "in", "digest": f"i{i}"} for i in range(10)]
    baseline = service.establish_baseline(history + [{"amount_sui": "-500", "direction": "out", "digest": "only-out"}])
    assert baseline["directions"]["out"]["status"] == "thin_history"
    assert service.detect_anomalies([{"amount_sui": "-500", "direction": "out", "digest": "only-out"}], baseline) == []


def test_severity_bands_follow_robust_z():
    service = AnomalyDetectionService()
    history = [{"amount_sui": str(v), "direction": "in", "digest": f"n{i}"} for i, v in enumerate([8, 9, 10, 11, 12, 10, 9, 11, 10, 10])]
    baseline = service.establish_baseline(history)
    stats = baseline["directions"]["in"]
    medium_at = stats["medium_threshold_sui"]
    high_at = stats["high_threshold_sui"]
    below = service.detect_anomalies([{"amount_sui": "11.9", "direction": "in", "digest": "below"}], baseline)
    medium = service.detect_anomalies([{"amount_sui": medium_at, "direction": "in", "digest": "m"}], baseline)
    high = service.detect_anomalies([{"amount_sui": high_at, "direction": "in", "digest": "h"}], baseline)
    assert below == []
    assert medium[0]["severity"] == "medium" and medium[0]["robust_z"] == 4.0
    assert high[0]["severity"] == "high" and high[0]["confidence"] > medium[0]["confidence"]


def test_smaller_than_usual_movements_are_never_flagged():
    service = AnomalyDetectionService()
    history = [{"amount_sui": "100", "direction": "in", "digest": f"n{i}"} for i in range(10)]
    baseline = service.establish_baseline(history)
    assert service.detect_anomalies([{"amount_sui": "0.0001", "direction": "in", "digest": "tiny"}], baseline) == []


def test_normalize_activity_separates_gas_from_transfers():
    gas_only = TransactionRecord(digest="gas", timestamp_ms=1, checkpoint=1, status="success", sender=VALID_ADDRESS,
                                 balance_changes=[BalanceChange(VALID_ADDRESS, LONG_SUI, "-2000000")], gas_fee_mist=2_000_000)
    paid = TransactionRecord(digest="pay", timestamp_ms=1, checkpoint=1, status="success", sender=VALID_ADDRESS,
                             balance_changes=[BalanceChange(VALID_ADDRESS, LONG_SUI, "-5002000000"), BalanceChange("0x" + "b" * 64, LONG_SUI, "5000000000")],
                             gas_fee_mist=2_000_000)
    received = tx("recv", 3_000_000_000)
    failed = tx("fail", -1_000_000, status="failure")
    items = {i["digest"]: i for i in normalize_activity([gas_only, paid, received, failed], VALID_ADDRESS)}
    assert items["gas"]["activity_kind"] == "gas_only"
    assert items["gas"]["gas_fee_sui"] == "0.002"
    assert items["pay"]["activity_kind"] == "transfer"
    assert items["pay"]["amount_sui"] == "-5.002"
    assert items["pay"]["transfer_amount_sui"] == "-5"
    assert items["recv"]["activity_kind"] == "transfer" and items["recv"]["direction"] == "in"
    assert items["fail"]["activity_kind"] == "failed"


def test_anomaly_severity_and_end_to_end_evidence(monkeypatch):
    history = [tx(f"normal-{i}", 1_000_000_000) for i in range(10)] + [tx("whale", 500_000_000_000)]
    use_fetch(monkeypatch, mainnet_fetch(history))
    result = client.post("/api/v1/wallets/analyze", json={"address": VALID_ADDRESS}).json()
    assert result["analysis"]["anomaly_count"] == 1
    finding = result["analysis"]["anomalies"][0]
    assert finding["severity"] == "high"
    assert finding["transaction_digest"] == "whale"
    assert result["evidence"][0]["ref"] == "whale"


def test_anomaly_ignores_garbage_values():
    service = AnomalyDetectionService()
    junk = [{"amount_sui": v, "digest": "x"} for v in (None, True, "nan", "abc", {}, [])]
    assert service.establish_baseline(junk)["sample_count"] == 0


# --- Rate limiting and request bounds ----------------------------------------

def test_demo_analysis_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(wallets.tatum_service, "api_key", "")
    statuses = [client.post("/api/v1/wallets/analyze", json={"address": "invalid"}).status_code for _ in range(11)]
    assert statuses[:10] == [400] * 10
    assert statuses[10] == 429


def test_analysis_body_limit_catches_chunked_requests():
    from app.main import AnalysisBodySizeMiddleware

    class NeverApp:
        async def __call__(self, *_args):
            raise AssertionError("oversized body reached the application")

    messages = iter([
        {"type": "http.request", "body": b"a" * 16_384, "more_body": True},
        {"type": "http.request", "body": b"b", "more_body": False},
    ])
    responses = []

    async def receive():
        return next(messages)

    async def send(message):
        responses.append(message)

    scope = {"type": "http", "method": "POST", "path": "/api/v1/wallets/analyze", "headers": []}
    middleware = AnalysisBodySizeMiddleware(NeverApp(), max_bytes=16_384)
    asyncio.run(middleware(scope, receive, send))
    assert responses[0]["status"] == 413
    assert any(key.lower() == b"x-request-id" for key, _ in responses[0]["headers"])


def test_oversized_content_length_is_rejected():
    response = client.post("/api/v1/wallets/analyze", content=b"x" * 20_000, headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_configured_redis_rate_limit_is_shared_and_fails_closed(monkeypatch):
    class FakeRedis:
        def __init__(self, fail=False):
            self.count = 0
            self.fail = fail
            self.keys = []

        async def eval(self, _script, key_count, key, ttl):
            assert key_count == 1
            assert ttl > 0
            assert "127.0.0.1" not in key
            self.keys.append(key)
            if self.fail:
                raise RedisError("unavailable")
            self.count += 1
            return self.count

    store = FakeRedis()
    monkeypatch.setattr(client.app.state, "redis", store, raising=False)
    monkeypatch.setattr("app.main.settings.ANALYSIS_RATE_LIMIT", 2)
    responses = [client.post("/api/v1/wallets/analyze", json={"address": "invalid"}) for _ in range(3)]
    assert [response.status_code for response in responses] == [400, 400, 429]
    assert len(set(store.keys)) == 1

    unavailable = FakeRedis(fail=True)
    monkeypatch.setattr(client.app.state, "redis", unavailable)
    response = client.post("/api/v1/wallets/analyze", json={"address": "invalid"})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "10"


# --- Startup guards -----------------------------------------------------------

def run_python(code, **env_overrides):
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", "")  # never reach a developer's local database from tests
    env.update(env_overrides)
    return subprocess.run([sys.executable, "-c", code], cwd=API_DIR, env=env, capture_output=True, text=True, timeout=30)


PROD_ENV = {
    "TRACE_ENV": "production",
    "TATUM_MAINNET_API_KEY": "prod-test-key-value",
    "REDIS_URL": "redis://127.0.0.1:1/0",
    "BACKEND_CORS_ORIGINS": "https://trace.example.com",
    "ALLOWED_HOSTS": "api.trace.example.com",
    "WALRUS_MEMORY_PRIVATE_KEY": "",
    "MEMWAL_ACCOUNT_ID": "",
    "MEMWAL_NAMESPACE_PREFIX": "trace-prod",
}


def test_production_refuses_incomplete_configuration_without_leaking_values():
    env = {**PROD_ENV, "TATUM_MAINNET_API_KEY": "", "REDIS_URL": "", "BACKEND_CORS_ORIGINS": "http://localhost:3000", "WALRUS_MEMORY_PRIVATE_KEY": "secret-walrus-value"}
    result = run_python("from app.main import app", **env)
    assert result.returncode != 0
    for expected in ("TATUM_MAINNET_API_KEY", "REDIS_URL", "BACKEND_CORS_ORIGINS", "half-configured"):
        assert expected in result.stderr
    assert "secret-walrus-value" not in result.stderr


def test_production_starts_with_complete_configuration_and_hides_docs():
    code = "from app.main import app; print([app.docs_url, app.openapi_url])"
    result = run_python(code, **PROD_ENV)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("[None, None]")


def test_production_fails_closed_when_rate_limit_store_is_down():
    code = "\n".join([
        "from fastapi.testclient import TestClient",
        "from app.main import app",
        "with TestClient(app, base_url='http://api.trace.example.com'):",
        "    pass",
    ])
    result = run_python(code, **PROD_ENV)
    assert result.returncode != 0
    assert "rate-limit store is unavailable" in result.stderr


def test_production_can_run_single_instance_without_redis():
    code = "\n".join([
        "from fastapi.testclient import TestClient",
        "from app.main import app",
        "with TestClient(app, base_url='http://api.trace.example.com') as c:",
        "    r = c.get('/ready')",
        "    print(r.status_code, c.get('/health').json()['capabilities']['distributed_rate_limiting'])",
    ])
    result = run_python(code, **{**PROD_ENV, "REDIS_URL": "", "RATE_LIMIT_STORE": "memory"})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("200 process_local")


def test_production_without_redis_needs_explicit_memory_store():
    result = run_python("from app.main import app", **{**PROD_ENV, "REDIS_URL": "", "RATE_LIMIT_STORE": "redis"})
    assert result.returncode != 0 and "RATE_LIMIT_STORE=memory" in result.stderr


def test_cors_origins_ignore_trailing_slashes():
    from app.core.config import Settings

    settings = Settings(_env_file=None, BACKEND_CORS_ORIGINS="https://a.pages.dev/, https://b.example.com//,")
    assert settings.cors_origins == ["https://a.pages.dev", "https://b.example.com"]


def test_unknown_environment_is_refused():
    result = run_python("from app.main import app", TRACE_ENV="staging-typo")
    assert result.returncode != 0 and "TRACE_ENV must be set" in result.stderr


def test_rate_limit_uses_proxy_appended_client_ip(monkeypatch):
    monkeypatch.setattr("app.main.settings.TRACE_ENV", "production")
    monkeypatch.setattr(wallets.tatum_service, "api_key", "")
    statuses = []
    for i in range(11):
        # An attacker rotates the spoofable first entry; the proxy-appended last entry stays the same.
        headers = {"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}
        statuses.append(client.post("/api/v1/wallets/analyze", json={"address": "invalid"}, headers=headers).status_code)
    assert statuses[-1] == 429


def test_unreachable_redis_falls_back_in_development_only():
    code = (
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "with TestClient(app) as c:\n"
        "    print(c.get('/health').json()['capabilities']['distributed_rate_limiting'])\n"
    )
    result = run_python(code, TRACE_ENV="development", REDIS_URL="redis://127.0.0.1:1/0")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("process_local")


# --- Tatum gRPC adapter contract (real sui.rpc.v2 schema) --------------------

def build_executed(digest="D1", seconds=1_700_000_000, nanos=123_000_000, success=True, changes=()):
    executed = message_class("ExecutedTransaction")()
    if digest is not None:
        executed.digest = digest
    executed.timestamp.seconds = seconds
    executed.timestamp.nanos = nanos
    executed.checkpoint = 99
    executed.effects.status.success = success
    executed.transaction.sender = VALID_ADDRESS
    for address, coin, amount in changes:
        change = executed.balance_changes.add()
        change.address, change.coin_type, change.amount = address, coin, amount
    return executed


def test_parse_transaction_reads_net_gas_fee():
    executed = build_executed(changes=[(VALID_ADDRESS, LONG_SUI, "-5")])
    executed.effects.gas_used.computation_cost = 1000
    executed.effects.gas_used.storage_cost = 3000
    executed.effects.gas_used.storage_rebate = 1500
    assert parse_transaction(executed).gas_fee_mist == 2500
    assert parse_transaction(build_executed(changes=[(VALID_ADDRESS, LONG_SUI, "-5")])).gas_fee_mist is None


def test_parse_transaction_contract():
    record = parse_transaction(build_executed(changes=[(VALID_ADDRESS, LONG_SUI, "-5"), (VALID_ADDRESS, LONG_SUI, None or "7")]))
    assert record.digest == "D1"
    assert record.timestamp_ms == 1_700_000_000_123
    assert record.checkpoint == 99
    assert record.status == "success"
    assert record.sender == VALID_ADDRESS
    assert [c.amount for c in record.balance_changes] == ["-5", "7"]
    assert parse_transaction(build_executed(success=False)).status == "failure"
    assert parse_transaction(build_executed(digest=None)) is None
    empty = message_class("ExecutedTransaction")(digest="D2")
    parsed = parse_transaction(empty)
    assert parsed.timestamp_ms is None and parsed.status is None and parsed.balance_changes == []


class FakeRpcError(grpc.RpcError):
    def __init__(self, code):
        self._code = code

    def code(self):
        return self._code

    def details(self):
        return "upstream says secret-key-is-not-safe-to-return"


class FakeChannel:
    """Mimics grpc.aio channel: unary_unary / unary_stream return async callables."""

    def __init__(self, transactions=(), end_reason=None, chain="mainnet", failures=None):
        self.transactions = list(transactions)
        self.end_reason = end_reason
        self.chain = chain
        self.failures = failures or {}
        self.calls = []

    def _maybe_fail(self, path):
        remaining = self.failures.get(path)
        if remaining:
            self.failures[path] = remaining[1:]
            raise FakeRpcError(remaining[0])

    def unary_unary(self, path, request_serializer, response_deserializer):
        async def call(request, metadata, timeout):
            self.calls.append((path, dict(metadata), request))
            request_serializer(request)
            self._maybe_fail(path)
            if path.endswith("GetServiceInfo"):
                return message_class("GetServiceInfoResponse")(chain=self.chain, chain_id="x", checkpoint_height=7)
            response = message_class("GetBalanceResponse")()
            response.balance.coin_type = LONG_SUI
            response.balance.balance = 2_500_000_000
            return response
        return call

    def unary_stream(self, path, request_serializer, response_deserializer):
        channel = self

        def call(request, metadata, timeout):
            channel.calls.append((path, dict(metadata), request))

            async def stream():
                channel._maybe_fail(path)
                for executed in channel.transactions:
                    yield message_class("ListTransactionsResponse")(transaction=executed)
                if channel.end_reason is not None:
                    response = message_class("ListTransactionsResponse")()
                    response.end.reason = channel.end_reason
                    yield response
            return stream()
        return call


def make_service(channel, key="test-key"):
    return TatumService(api_key=key, channel_factory=lambda: channel, retry_base_seconds=0)


def test_fetch_wallet_builds_bounded_descending_address_query():
    channel = FakeChannel([build_executed(digest=f"D{i}") for i in range(3)], end_reason=5)
    result = asyncio.run(make_service(channel).fetch_wallet(VALID_ADDRESS, limit=50))
    assert result.chain.chain == "mainnet"
    assert result.sui_balance_mist == "2500000000"
    assert [t.digest for t in result.transactions] == ["D0", "D1", "D2"]
    assert result.has_more is False
    for path, metadata, request in channel.calls:
        assert metadata == {"x-api-key": "test-key"}
        if path.endswith("ListTransactions"):
            assert request.options.limit == 50
            assert request.options.ordering == 1
            assert request.filter.terms[0].literals[0].affected_address.address == VALID_ADDRESS
            assert "balance_changes" in request.read_mask.paths
        if path.endswith("GetBalance"):
            assert request.owner == VALID_ADDRESS and request.coin_type == "0x2::sui::SUI"


@pytest.mark.parametrize("end_reason,count,expected", [(1, 2, True), (2, 2, True), (5, 2, False), (None, 2, True), (None, 1, False)])
def test_fetch_wallet_reports_more_history(end_reason, count, expected):
    channel = FakeChannel([build_executed(digest=f"D{i}") for i in range(count)], end_reason=end_reason)
    result = asyncio.run(make_service(channel).fetch_wallet(VALID_ADDRESS, limit=2))
    assert result.has_more is expected
    assert len(result.transactions) <= 2


def test_fetch_wallet_retries_transient_errors_then_succeeds():
    path = "/sui.rpc.v2.StateService/GetBalance"
    channel = FakeChannel(failures={path: [grpc.StatusCode.RESOURCE_EXHAUSTED, grpc.StatusCode.UNAVAILABLE]})
    result = asyncio.run(make_service(channel).fetch_wallet(VALID_ADDRESS))
    assert result.sui_balance_mist == "2500000000"
    assert sum(1 for p, *_ in channel.calls if p == path) == 3


def test_fetch_wallet_gives_up_after_bounded_retries_and_sanitizes():
    path = "/sui.rpc.v2.LedgerService/ListTransactions"
    channel = FakeChannel(failures={path: [grpc.StatusCode.UNAVAILABLE] * 10})
    with pytest.raises(TatumProviderError) as caught:
        asyncio.run(make_service(channel, key="super-secret").fetch_wallet(VALID_ADDRESS))
    assert sum(1 for p, *_ in channel.calls if p == path) == 3
    assert "secret" not in str(caught.value)


def test_fetch_wallet_does_not_retry_auth_errors():
    path = "/sui.rpc.v2.LedgerService/GetServiceInfo"
    channel = FakeChannel(failures={path: [grpc.StatusCode.UNAUTHENTICATED] * 3})
    with pytest.raises(TatumProviderError):
        asyncio.run(make_service(channel).fetch_wallet(VALID_ADDRESS))
    assert sum(1 for p, *_ in channel.calls if p == path) == 1


def test_fetch_wallet_requires_key_and_bounded_limit():
    with pytest.raises(TatumProviderError):
        asyncio.run(make_service(FakeChannel(), key="").fetch_wallet(VALID_ADDRESS))
    with pytest.raises(ValueError):
        asyncio.run(make_service(FakeChannel()).fetch_wallet(VALID_ADDRESS, limit=51))


# --- Live Mainnet integration (opt-in: TRACE_LIVE_TESTS=1) -------------------

@pytest.mark.skipif(os.environ.get("TRACE_LIVE_TESTS") != "1", reason="set TRACE_LIVE_TESTS=1 to call real Tatum Mainnet")
def test_live_tatum_mainnet_analysis():
    from app.core.config import settings

    if not settings.TATUM_MAINNET_API_KEY:
        pytest.skip("TATUM_MAINNET_API_KEY not configured")
    live = TatumService()
    address = os.environ.get("TRACE_LIVE_ADDRESS", "0x545b5ec1a8470d410bcb2ecaa700b5c0690a341943bcf5fcc708e3b0125fe817")
    result = asyncio.run(live.fetch_wallet(address, limit=20))
    assert result.chain.chain == "mainnet"
    assert result.sui_balance_mist is not None
    assert result.transactions, "expected recent activity for the live test address"
    stamps = [t.timestamp_ms for t in result.transactions if t.timestamp_ms]
    assert stamps == sorted(stamps, reverse=True), "transactions should be newest first"
    items = normalize_activity(result.transactions, address)
    assert any(item["amount_sui"] is not None for item in items)


# --- Deployment configuration ------------------------------------------------

def test_render_external_hostname_is_trusted_automatically():
    from app.core.config import Settings
    settings = Settings(_env_file=None, ALLOWED_HOSTS="api.example.com", RENDER_EXTERNAL_HOSTNAME="My-Service.onrender.com")
    assert settings.allowed_hosts == ["api.example.com", "my-service.onrender.com"]
    assert Settings(_env_file=None, ALLOWED_HOSTS="api.example.com").allowed_hosts == ["api.example.com"]


def test_database_url_forms_from_common_providers():
    from app.core.config import Settings
    dsn = lambda url: Settings(_env_file=None, DATABASE_URL=url).database_dsn  # noqa: E731
    assert dsn("postgresql+asyncpg://u:p@h/db") == "postgresql://u:p@h/db"
    assert dsn("postgresql://u:p@h/db?sslmode=require&channel_binding=require") == "postgresql://u:p@h/db?sslmode=require"
    assert dsn("postgres://u:p@h:5432/db") == "postgres://u:p@h:5432/db"
