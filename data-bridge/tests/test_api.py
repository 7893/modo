"""
Unit tests for FastAPI data-bridge endpoints
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from fastapi.testclient import TestClient
from api import app, _rate_limit_store

client = TestClient(app)


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
    """Verify /api/nodes/summary returns the 10 registered nodes."""
    response = client.get("/api/nodes/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_nodes"] == 11
    assert len(data["nodes"]) == 11
    
    # Check that core nodes are present
    node_names = [n["name"] for n in data["nodes"]]
    assert "jpa" in node_names
    assert "usa" in node_names
    assert "sga" in node_names
    assert "cna" in node_names


def test_cors_headers():
    """Verify CORS headers are present for cross-origin Worker requests."""
    response = client.get("/health", headers={"Origin": "https://nexus.53.workers.dev"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://nexus.53.workers.dev"


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
