"""
Nexus Data Bridge - FastAPI Gateway
Provides REST endpoints for Cloudflare Workers & Frontend UI
to query telemetry data, node health, and AutoML insights.
"""
import os
import json
import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Load environment configuration
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

# Rate limiting config
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # window in seconds

# Allowed CORS origins
ALLOWED_ORIGINS = [
    "https://nexus.53.workers.dev",
    "http://localhost:8787",  # wrangler dev
]

# Load nodes from config file
_nodes_config_path = os.path.join(os.path.dirname(__file__), "nodes.json")


def load_target_nodes() -> list:
    """Load target nodes from nodes.json config file."""
    try:
        with open(_nodes_config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"nodes.json not found, using empty list")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in nodes.json: {e}")
        return []


TARGET_NODES = load_target_nodes()

app = FastAPI(
    title="Nexus Data Bridge API",
    description="Internal API for Cloudflare Tunnel & Worker integration",
    version="1.0.0"
)

# Rate limiter storage: {ip: [(timestamp, count)]}
_rate_limit_store: dict = defaultdict(list)


def check_rate_limit(client_ip: str) -> bool:
    """Check if client is within rate limit. Returns True if allowed."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    
    # Clean old entries
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]
    
    # Check limit
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    
    # Record request
    _rate_limit_store[client_ip].append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""
    # Get client IP (trust X-Forwarded-For from Cloudflare)
    client_ip = request.headers.get("CF-Connecting-IP") or \
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or \
                request.client.host or "unknown"
    
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=429,
            content={"error": "Too many requests", "retry_after": RATE_LIMIT_WINDOW}
        )
    
    return await call_next(request)

# Enable CORS for Cloudflare Worker & local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Database connection pool (lazy initialization)
_db_pool: Optional[PooledDB] = None


def get_db_pool() -> PooledDB:
    """Get or create the database connection pool."""
    global _db_pool
    if _db_pool is None:
        host = os.getenv("MYSQL_HOST")
        port = int(os.getenv("MYSQL_PORT", "3306"))
        user = os.getenv("MYSQL_USER")
        password = os.getenv("MYSQL_PASSWORD")
        database = os.getenv("MYSQL_DATABASE", "nexus_db")
        
        if not all([host, user, password]):
            raise RuntimeError("Missing required environment variables: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD")
        
        _db_pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            maxcached=5,
            blocking=True,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            autocommit=True,
        )
        logger.info(f"Database connection pool initialized (host={host}, database={database})")
    
    return _db_pool


@contextmanager
def get_db_connection():
    """Context manager for database connections from the pool."""
    pool = get_db_pool()
    conn = pool.connection()
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health_check():
    """Health check endpoint for tunnel & latency monitoring."""
    db_ok = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                db_ok = True
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        db_ok = False

    return {
        "status": "online",
        "service": "Nexus Data Bridge Gateway",
        "node": "usa-ashburn",
        "database_status": "connected" if db_ok else "error",
        "timestamp": datetime.now().isoformat(),
        "tunnel_endpoint": "api-nexus.8n8m.cfd"
    }


@app.get("/api/nodes/summary")
def get_nodes_summary():
    """Returns the registered global nodes and geographic metadata."""
    return {
        "total_nodes": len(TARGET_NODES),
        "nodes": TARGET_NODES,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/metrics/latest")
def get_latest_metrics():
    """
    Returns the latest telemetry snapshot for every registered active node.
    Used for dashboard top cards, world map status, and fleet overview.
    """
    active_names = [n["name"] for n in TARGET_NODES]
    node_map = {n["name"]: n for n in TARGET_NODES}

    format_strings = ','.join(['%s'] * len(active_names))
    query = f"""
    SELECT t.*
    FROM vm_telemetry t
    INNER JOIN (
        SELECT node_name, MAX(id) AS max_id
        FROM vm_telemetry
        WHERE node_name IN ({format_strings})
        GROUP BY node_name
    ) latest ON t.id = latest.max_id
    ORDER BY t.node_name ASC;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(active_names))
                rows = cur.fetchall()

        enriched = []
        for r in rows:
            meta = node_map.get(r["node_name"], {})
            r["provider"] = meta.get("provider", "Cloud")
            r["lat"] = meta.get("lat", 0.0)
            r["lng"] = meta.get("lng", 0.0)
            if isinstance(r["recorded_at"], datetime):
                r["recorded_at"] = r["recorded_at"].isoformat()
            enriched.append(r)

        return {
            "status": "success",
            "count": len(enriched),
            "data": enriched,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching latest metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metrics/history")
def get_metrics_history(
    node: Optional[str] = Query(None, description="Filter by node name (e.g. jpa, usa)"),
    hours: int = Query(24, ge=1, le=168, description="History window in hours"),
    limit: int = Query(200, ge=10, le=1000, description="Max data points to return")
):
    """
    Returns time-series telemetry data for plotting ECharts performance waveforms.
    """
    params = [hours]
    where_clauses = ["recorded_at >= NOW() - INTERVAL %s HOUR"]

    if node:
        where_clauses.append("node_name = %s")
        params.append(node)

    query = f"""
    SELECT id, node_name, host_ip, region, cpu_usage_percent,
           mem_usage_percent, disk_usage_percent, net_in_bytes_sec,
           net_out_bytes_sec, scrape_duration_ms, status, recorded_at
    FROM vm_telemetry
    WHERE {' AND '.join(where_clauses)}
    ORDER BY recorded_at ASC
    LIMIT %s;
    """
    params.append(limit)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        for r in rows:
            if isinstance(r["recorded_at"], datetime):
                r["recorded_at"] = r["recorded_at"].isoformat()

        return {
            "status": "success",
            "node": node or "all",
            "hours": hours,
            "count": len(rows),
            "data": rows,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching metrics history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/diagnostics")
def get_ai_diagnostics():
    """
    Automated health heuristics & anomaly detection summary.
    """
    active_names = [n["name"] for n in TARGET_NODES]
    format_strings = ','.join(['%s'] * len(active_names))

    query = f"""
    SELECT t.node_name, t.status, t.cpu_usage_percent, t.mem_usage_percent,
           t.disk_usage_percent, t.scrape_duration_ms, t.recorded_at
    FROM vm_telemetry t
    INNER JOIN (
        SELECT node_name, MAX(id) AS max_id
        FROM vm_telemetry
        WHERE node_name IN ({format_strings})
        GROUP BY node_name
    ) latest ON t.id = latest.max_id;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(active_names))
                rows = cur.fetchall()

        total = len(rows)
        online = sum(1 for r in rows if r["status"] == "ONLINE")
        warnings = []

        for r in rows:
            if r["status"] != "ONLINE":
                warnings.append(f"Node {r['node_name']} is currently {r['status']}.")
            elif r["mem_usage_percent"] > 85.0:
                warnings.append(f"Node {r['node_name']} memory usage is high ({r['mem_usage_percent']}%).")
            elif r["disk_usage_percent"] > 85.0:
                warnings.append(f"Node {r['node_name']} disk usage is high ({r['disk_usage_percent']}%).")
            elif r["scrape_duration_ms"] > 800:
                warnings.append(f"Node {r['node_name']} latency is elevated ({r['scrape_duration_ms']}ms).")

        health_score = round((online / max(total, 1)) * 100, 1)
        if warnings:
            health_score = max(0, health_score - len(warnings) * 5)

        return {
            "fleet_health_score": health_score,
            "total_nodes": total,
            "online_nodes": online,
            "status": "HEALTHY" if health_score >= 80 else ("DEGRADED" if health_score >= 50 else "CRITICAL"),
            "anomalies_count": len(warnings),
            "diagnostics": warnings if warnings else ["All systems operational across Tokyo, Ashburn, Singapore, Beijing regions."],
            "evaluated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching AI diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
