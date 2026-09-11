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
    assert "timestamp" in data
    assert "tunnel_endpoint" in data


def test_nodes_summary_endpoint():
    """Verify /api/nodes/summary returns the registered nodes."""
    headers = {"X-Internal-Secret": os.getenv("INTERNAL_API_SECRET", "")} if os.getenv("INTERNAL_API_SECRET") else {}
    response = client.get("/api/nodes/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_nodes" in data
    assert "nodes" in data
    assert len(data["nodes"]) == data["total_nodes"]
    
    # Check that core nodes are present
    node_names = [n["name"] for n in data["nodes"]]
    assert "example-node-1" in node_names
    assert "example-node-6" in node_names
    assert "example-node-9" in node_names
    assert "example-node-10" in node_names


def test_cors_headers():
    """Verify CORS headers are present for cross-origin Worker requests."""
    response = client.get("/health", headers={"Origin": "https://service.example.com"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://service.example.com"


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
    assert response.json() == {"error": "Too many requests"}
    
    # Clean up
    _rate_limit_store.clear()
