"""
Nexus Data Bridge - FastAPI Gateway
Provides REST endpoints for Cloudflare Workers & Frontend UI
to query telemetry data, node health, and AutoML insights.
"""
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pymysql
from dotenv import load_dotenv

# Load environment configuration
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv()

app = FastAPI(
    title="Nexus Data Bridge API",
    description="Internal API for Cloudflare Tunnel & Worker integration",
    version="1.0.0"
)

# Enable CORS for Cloudflare Worker & local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    """Create and return a MySQL connection."""
    host = os.getenv("MYSQL_HOST")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQL_DATABASE", "nexus_db")
    
    if not all([host, user, password]):
        raise RuntimeError("Missing required environment variables: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD")
    
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )

@app.get("/health")
def health_check():
    """Health check endpoint for tunnel & latency monitoring."""
    db_ok = False
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            db_ok = True
        conn.close()
    except Exception as e:
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
    from ingest import TARGET_NODES
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
    from ingest import TARGET_NODES
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
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, tuple(active_names))
            rows = cur.fetchall()
        conn.close()

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
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        conn.close()

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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ai/diagnostics")
def get_ai_diagnostics():
    """
    Automated health heuristics & anomaly detection summary.
    """
    from ingest import TARGET_NODES
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
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, tuple(active_names))
            rows = cur.fetchall()
        conn.close()

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
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
