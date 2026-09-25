"""
Unit tests for FastAPI data-bridge endpoints
"""
import sys
import os
from contextlib import contextmanager

import pytest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from fastapi.testclient import TestClient
import api
import api_config
import api_security
import api_telemetry
from api import app, _rate_limit_store

client = TestClient(app)

TEST_NODES = [
    {"name": "test-a", "host": "192.0.2.10", "region": "test-1"},
    {"name": "test-b", "host": "192.0.2.11", "region": "test-2"},
]
TEST_INTERNAL_SECRET = "modo-test-only-secret"


@pytest.fixture(autouse=True)
def isolated_api_config(monkeypatch):
    """Keep API tests independent from local or production node files."""
    @contextmanager
    def unavailable_database():
        raise RuntimeError("database access disabled in unit tests")
        yield

    monkeypatch.setattr(api_config, "TARGET_NODES", TEST_NODES)
    monkeypatch.setattr(api_config, "INTERNAL_API_SECRET", TEST_INTERNAL_SECRET)
    monkeypatch.setattr(api_security, "rate_limit_last_sweep", 0.0)
    monkeypatch.setattr(api_telemetry, "get_db_connection", unavailable_database)
    _rate_limit_store.clear()
    yield
    _rate_limit_store.clear()


def test_health_endpoint():
    """Verify /health returns 200 with standard schema."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "MODO Data Bridge Gateway"
    assert "node" in data
    assert "timestamp" in data


def test_nodes_summary_endpoint():
    """Verify /api/nodes/summary reflects the injected test configuration."""
    headers = {"X-Internal-Secret": TEST_INTERNAL_SECRET}
    response = client.get("/api/nodes/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_nodes"] == len(TEST_NODES)
    assert len(data["nodes"]) == len(TEST_NODES)

    node_names = [n["name"] for n in data["nodes"]]
    assert node_names == ["test-a", "test-b"]
    assert all("host" not in node for node in data["nodes"])


def test_cors_headers():
    """Verify CORS headers are present for cross-origin Worker requests."""
    allowed_origin = api.ALLOWED_ORIGINS[0]
    response = client.get("/health", headers={"Origin": allowed_origin})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == allowed_origin


def test_rate_limit():
    """Verify rate limiting returns 429 when exceeded."""
    # Clear rate limit store and use a smaller limit for testing
    _rate_limit_store.clear()

    # Manually fill the rate limit store to simulate hitting the limit
    test_ip = "test-rate-limit-ip"
    import time
    now = time.time()
    _rate_limit_store[test_ip] = [now] * 60  # Fill with 60 timestamps

    # Next request should be rate limited
    response = client.get("/health", headers={"X-Forwarded-For": test_ip})
    assert response.status_code == 429
    assert "retry_after" in response.json()

    # Clean up
    _rate_limit_store.clear()


def test_rate_limit_sweep_removes_inactive_clients(monkeypatch):
    """A global sweep must remove clients that never make another request."""
    clock = [1_000.0]
    monkeypatch.setattr(api_security.time, "time", lambda: clock[0])
    monkeypatch.setattr(api_security, "RATE_LIMIT_WINDOW", 60)
    monkeypatch.setattr(api_security, "RATE_LIMIT_SWEEP_INTERVAL", 10)
    monkeypatch.setattr(api_security, "rate_limit_last_sweep", 0.0)

    for index in range(1_000):
        assert api.check_rate_limit(f"198.18.{index // 256}.{index % 256}") is True
    assert len(_rate_limit_store) == 1_000

    clock[0] += 61
    assert api.check_rate_limit("203.0.113.10") is True
    assert list(_rate_limit_store) == ["203.0.113.10"]


def test_rate_limit_store_respects_capacity(monkeypatch):
    """The client map remains bounded even when all buckets are still active."""
    clock = [2_000.0]
    monkeypatch.setattr(api_security.time, "time", lambda: clock[0])
    monkeypatch.setattr(api_security, "RATE_LIMIT_MAX_CLIENTS", 3)
    monkeypatch.setattr(api_security, "RATE_LIMIT_SWEEP_INTERVAL", 3_600)
    monkeypatch.setattr(api_security, "rate_limit_last_sweep", clock[0])

    for index in range(4):
        clock[0] += 1
        assert api.check_rate_limit(f"203.0.113.{index}") is True

    assert len(_rate_limit_store) == 3
    assert "203.0.113.0" not in _rate_limit_store
    assert "203.0.113.3" in _rate_limit_store


def test_dashboard_overview_keeps_partial_results(monkeypatch):
    """One failed component must not discard the rest of the dashboard."""
    monkeypatch.setattr(api, "get_latest_metrics", lambda: {"status": "success", "data": []})
    monkeypatch.setattr(api, "get_ai_diagnostics", lambda: {"status": "HEALTHY"})
    monkeypatch.setattr(api, "get_anomaly_dashboard", lambda: {"status": "success", "data": []})
    monkeypatch.setattr(api, "get_heatwave_status", lambda: {"status": "success"})
    monkeypatch.setattr(api, "get_hourly_analytics", lambda node, hours: {"status": "success", "data": []})

    def fail_forecast():
        raise RuntimeError("simulated component failure")

    monkeypatch.setattr(api, "get_latency_forecast", fail_forecast)
    result = api.get_dashboard_overview()

    assert result["status"] == "partial"
    assert result["failed_components"] == ["forecast"]
    assert result["data"]["nodes"]["status"] == "success"
    assert result["data"]["forecast"] == {
        "status": "error",
        "message": "Component unavailable",
    }


def test_three_dashboard_tabs_stay_under_rate_limit(monkeypatch):
    """Three tabs refreshing five times each remain below the one-minute quota."""
    monkeypatch.setattr(api, "get_latest_metrics", lambda: {"status": "success", "data": []})
    monkeypatch.setattr(api, "get_ai_diagnostics", lambda: {"status": "HEALTHY"})
    monkeypatch.setattr(api, "get_anomaly_dashboard", lambda: {"status": "success", "data": []})
    monkeypatch.setattr(api, "get_heatwave_status", lambda: {"status": "success"})
    monkeypatch.setattr(api, "get_hourly_analytics", lambda node, hours: {"status": "success", "data": []})
    monkeypatch.setattr(api, "get_latency_forecast", lambda: {"status": "success", "data": []})
    headers = {
        "X-Internal-Secret": TEST_INTERNAL_SECRET,
        "X-MODO-Client-IP": "198.51.100.20",
    }

    responses = [client.get("/api/dashboard/overview", headers=headers) for _ in range(15)]

    assert all(response.status_code == 200 for response in responses)


def test_public_schemas_drop_private_and_unknown_fields():
    from public_data import public_node, public_metric
    assert public_node({"name": "demo", "host": "192.0.2.1", "password": "test"}) == {"name": "demo"}
    assert public_metric({"node_name": "demo", "host_ip": "192.0.2.1", "future_secret": "test"}) == {"node_name": "demo"}
