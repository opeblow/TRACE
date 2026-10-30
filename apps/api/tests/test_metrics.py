"""Operational metrics: access control and bounded, non-identifying labels."""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.metrics import Metrics, metrics
from app.main import _analysis_requests, app
from app.routers import wallets
from app.services.tatum import TatumProviderError

client = TestClient(app)
WALLET = "0x" + "3" * 64
WORKSPACE = "metricsWS_" + "m" * 22


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    metrics.reset()
    _analysis_requests.clear()
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    yield
    _analysis_requests.clear()


def test_requests_are_counted_by_route_template_not_raw_path():
    client.get(f"/api/v1/investigations/{'1' * 8}-0000-0000-0000-000000000000", headers={"X-Trace-Workspace": WORKSPACE})
    body = client.get("/metrics").text
    assert 'route="/api/v1/investigations/{investigation_id}"' in body and 'status="404"' in body
    assert "11111111" not in body and WORKSPACE not in body
    assert "trace_http_request_duration_seconds_bucket" in body


def test_provider_failures_and_analysis_outcomes_are_counted(monkeypatch):
    monkeypatch.setattr(wallets.tatum_service, "api_key", "test-key")
    monkeypatch.setattr(wallets.tatum_service, "fetch_wallet", AsyncMock(side_effect=TatumProviderError("down")))
    assert client.post("/api/v1/wallets/analyze", json={"address": WALLET}).status_code == 502
    assert metrics.value("trace_provider_failures_total", provider="tatum", kind="request") == 1
    assert metrics.value("trace_analyses_total", outcome="provider_error") == 1
    assert WALLET not in client.get("/metrics").text


def test_metrics_token_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", "s3cret-token")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"}).status_code == 200


def test_metrics_hidden_in_production_without_token(monkeypatch):
    monkeypatch.setattr(settings, "TRACE_ENV", "production")
    assert client.get("/metrics").status_code == 404


def test_unknown_metric_names_are_rejected():
    with pytest.raises(KeyError):
        Metrics().inc("trace_made_up_total")
