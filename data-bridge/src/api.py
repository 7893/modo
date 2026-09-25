"""MODO FastAPI gateway composition root.

Request handlers live in focused modules; this file owns application wiring,
middleware, and the aggregated dashboard endpoint.
"""
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from public_data import public_node

import api_config
import api_security
from api_analytics import (
    get_anomaly_dashboard,
    get_fleet_health_report,
    get_heatwave_status,
    get_ml_features,
)
from api_diagnostics import get_ai_diagnostics
from api_forecast import get_latency_forecast
from api_maintenance import prune_old_data, weekly_retrain_loop
from api_telemetry import (
    get_hourly_analytics,
    get_latest_metrics,
    get_metrics_history,
    health_check,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
_retrain_thread_started = False


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    """Start process-local background services only when FastAPI starts."""
    global _retrain_thread_started
    enabled = os.getenv("AUTO_RETRAIN_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    if enabled and not _retrain_thread_started:
        threading.Thread(
            target=weekly_retrain_loop,
            name="weekly-retrain",
            daemon=True,
        ).start()
        _retrain_thread_started = True
    yield


app = FastAPI(
    title="MODO Core API Gateway",
    description="Internal API for Cloudflare Tunnel & Worker integration",
    version="1.0.0",
    lifespan=app_lifespan,
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply a bounded per-client request limit."""
    secret = api_config.INTERNAL_API_SECRET
    forwarded_by_worker = None
    if secret and request.headers.get("X-Internal-Secret") == secret:
        forwarded_by_worker = request.headers.get("X-MODO-Client-IP")

    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    peer = request.client.host if request.client else None
    client_ip = (
        forwarded_by_worker
        or request.headers.get("CF-Connecting-IP")
        or forwarded
        or peer
        or "unknown"
    )
    if not api_security.check_rate_limit(client_ip):
        logger.warning("Rate limit exceeded for %s", client_ip)
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too many requests",
                "retry_after": api_security.RATE_LIMIT_WINDOW,
            },
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=api_config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Internal-Secret"],
)


def get_nodes_summary():
    """Return registered nodes and geographic metadata."""
    return {
        "total_nodes": len(api_config.TARGET_NODES),
        "nodes": [public_node(node) for node in api_config.TARGET_NODES],
        "timestamp": datetime.now().isoformat(),
    }


def get_dashboard_overview():
    """Return a dashboard snapshot while preserving healthy components."""
    component_loaders = {
        "nodes": get_latest_metrics,
        "diagnostics": get_ai_diagnostics,
        "anomalies": get_anomaly_dashboard,
        "heatwave": get_heatwave_status,
        "hourly": lambda: get_hourly_analytics(node=None, hours=24),
        "forecast": get_latency_forecast,
    }
    components = {}
    failures = []
    for name, loader in component_loaders.items():
        try:
            components[name] = loader()
        except Exception:
            logger.exception("Dashboard component failed: %s", name)
            components[name] = {"status": "error", "message": "Component unavailable"}
            failures.append(name)

    return {
        "status": "partial" if failures else "success",
        "data": components,
        "failed_components": failures,
        "timestamp": datetime.now().isoformat(),
    }


app.add_api_route("/health", health_check, methods=["GET"])
app.add_api_route("/api/nodes/summary", get_nodes_summary, methods=["GET"])
app.add_api_route("/api/metrics/latest", get_latest_metrics, methods=["GET"])
app.add_api_route("/api/metrics/history", get_metrics_history, methods=["GET"])
app.add_api_route("/api/analytics/hourly", get_hourly_analytics, methods=["GET"])
app.add_api_route("/api/analytics/fleet", get_fleet_health_report, methods=["GET"])
app.add_api_route("/api/analytics/anomalies", get_anomaly_dashboard, methods=["GET"])
app.add_api_route("/api/analytics/ml-features", get_ml_features, methods=["GET"])
app.add_api_route("/api/analytics/heatwave-status", get_heatwave_status, methods=["GET"])
app.add_api_route("/api/ai/diagnostics", get_ai_diagnostics, methods=["GET"])
app.add_api_route("/api/analytics/latency-forecast", get_latency_forecast, methods=["GET"])
app.add_api_route("/api/dashboard/overview", get_dashboard_overview, methods=["GET"])
app.add_api_route("/api/maintenance/prune", prune_old_data, methods=["POST"])


@app.middleware("http")
async def verify_internal_secret(request: Request, call_next):
    """Protect private API routes; the public Worker injects the secret."""
    if request.url.path.startswith("/api/") and request.method != "OPTIONS":
        secret = request.headers.get("X-Internal-Secret")
        if not secret or secret != api_config.INTERNAL_API_SECRET:
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden: Invalid internal secret"},
            )
    return await call_next(request)


# Compatibility exports for operational scripts and existing tests.
ALLOWED_ORIGINS = api_config.ALLOWED_ORIGINS
_rate_limit_store = api_security.rate_limit_store
check_rate_limit = api_security.check_rate_limit


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
