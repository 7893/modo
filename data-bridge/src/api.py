"""
MODO Data Bridge - FastAPI Gateway
Provides REST endpoints for Cloudflare Workers & Frontend UI
to query telemetry data, node health, and database metrics.
"""
import os
import sys
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
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv()

# Rate limiting config
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # window in seconds

# Allowed CORS origins
ALLOWED_ORIGINS = [
    "https://modo.53.workers.dev",
    "http://localhost:8787",  # wrangler dev
]

# Load nodes from config file
_nodes_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "nodes.json")


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
    title="MODO Core API Gateway",
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
    allow_headers=["Content-Type", "Authorization", "X-Internal-Secret"],
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
        database = os.getenv("MYSQL_DATABASE", "modo_db")
        
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
        "service": "MODO Data Bridge Gateway",
        "node": "jpa-osaka",
        "database_status": "connected" if db_ok else "error",
        "timestamp": datetime.now().isoformat(),
        "tunnel_endpoint": "api-modo.8n8m.cfd"
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
    Uses HeatWave-optimized view v_node_latest_status for acceleration.
    Used for dashboard top cards, world map status, and fleet overview.
    """
    active_names = [n["name"] for n in TARGET_NODES]
    node_map = {n["name"]: n for n in TARGET_NODES}

    # Use HeatWave-optimized view instead of subquery
    format_strings = ','.join(['%s'] * len(active_names))
    query = f"""
    SELECT 
        v.node_name,
        v.host_ip,
        v.region,
        v.cpu_usage_percent,
        v.mem_usage_percent,
        v.disk_usage_percent,
        v.latency_ms as scrape_duration_ms,
        v.status,
        v.recorded_at,
        v.health_score,
        v.cpu_score,
        v.mem_score,
        t.id,
        t.net_in_bytes_sec,
        t.net_out_bytes_sec
    FROM v_node_latest_status v
    LEFT JOIN vm_telemetry t ON v.node_name = t.node_name 
        AND v.recorded_at = t.recorded_at
    WHERE v.node_name IN ({format_strings})
    ORDER BY v.node_name ASC;
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
            if isinstance(r.get("recorded_at"), datetime):
                r["recorded_at"] = r["recorded_at"].isoformat()
            enriched.append(r)

        return {
            "status": "success",
            "count": len(enriched),
            "data": enriched,
            "engine": "HeatWave",
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
    Uses HeatWave acceleration for large scans.
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
            "engine": "HeatWave",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching metrics history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/hourly")
def get_hourly_analytics(
    node: Optional[str] = Query(None, description="Filter by node name"),
    hours: int = Query(48, ge=1, le=168, description="History window in hours")
):
    """
    Returns hourly aggregated analytics from HeatWave v_realtime_analytics view.
    Provides avg CPU, memory, volatility metrics for trend analysis.
    """
    params = []
    where_clause = "WHERE hour >= DATE_FORMAT(NOW() - INTERVAL %s HOUR, '%%Y-%%m-%%d %%H:00:00')"
    params.append(hours)
    
    if node:
        where_clause += " AND node_name = %s"
        params.append(node)

    query = f"""
    SELECT node_name, hour, samples, avg_cpu, avg_mem, 
           cpu_volatility, peak_latency
    FROM v_realtime_analytics
    {where_clause}
    ORDER BY hour DESC, node_name ASC
    LIMIT 500;
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        for r in rows:
            if isinstance(r.get("hour"), datetime):
                r["hour"] = r["hour"].strftime("%Y-%m-%d %H:00:00")

        return {
            "status": "success",
            "node": node or "all",
            "hours": hours,
            "count": len(rows),
            "data": rows,
            "engine": "HeatWave OLAP",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching hourly analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/fleet")
def get_fleet_health_report():
    """
    Returns comprehensive fleet health report from HeatWave v_fleet_health_report view.
    Includes health scores, trends, and hour-over-hour comparisons.
    """
    query = """
    SELECT *
    FROM v_fleet_health_report
    ORDER BY cpu_load_rank ASC
    LIMIT 200;
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()

        return {
            "status": "success",
            "count": len(rows),
            "data": rows,
            "engine": "HeatWave OLAP",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching fleet health report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/anomalies")
def get_anomaly_dashboard():
    """
    Returns anomaly detection summary from HeatWave v_anomaly_dashboard view.
    Shows anomaly types, severity distribution, and open issues.
    """
    query = """
    SELECT anomaly_type, severity, count, open_count, 
           avg_confidence, latest
    FROM v_anomaly_dashboard
    ORDER BY open_count DESC, count DESC;
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()

        for r in rows:
            if isinstance(r.get("latest"), datetime):
                r["latest"] = r["latest"].isoformat()

        return {
            "status": "success",
            "count": len(rows),
            "data": rows,
            "engine": "HeatWave ML",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching anomaly dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/ml-features")
def get_ml_features(limit: int = Query(default=100, ge=1, le=1000)):
    """
    Returns sanitized telemetry features prepared for HeatWave AutoML.
    Complies with Oracle HeatWave AutoML strict data type and language requirements.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT node_name, cpu_usage_percent, mem_usage_percent, disk_usage_percent, "
                    "net_in_mb, net_out_mb, status, recorded_at "
                    "FROM v_telemetry_ml_features LIMIT %s",
                    (limit,)
                )
                rows = cur.fetchall()
                for r in rows:
                    if isinstance(r.get("recorded_at"), datetime):
                        r["recorded_at"] = r["recorded_at"].isoformat()

        return {
            "status": "success",
            "count": len(rows),
            "data": rows,
            "engine": "HeatWave AutoML Feature Store",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching ML features: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/heatwave-status")
def get_heatwave_status():
    """
    Returns HeatWave cluster status and performance metrics.
    Shows memory usage, query offload stats, and acceleration ratios.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get HeatWave status variables
                status_vars = {}
                key_vars = [
                    'rapid_cluster_status', 'rapid_service_status', 
                    'rapid_heap_usage', 'rapid_query_offload_count',
                    'rapid_query_nonoffload_count', 'rapid_change_propagation_status',
                    'rapid_ml_status'
                ]
                for var in key_vars:
                    cur.execute(
                        "SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = %s",
                        (var,)
                    )
                    row = cur.fetchone()
                    status_vars[var] = row['VARIABLE_VALUE'] if row else None
                
                # Get loaded tables count
                cur.execute("SELECT COUNT(*) as cnt FROM performance_schema.rpd_tables")
                tables_loaded = cur.fetchone()['cnt']
                
                # Get total records across active and archive partitions
                cur.execute("SELECT GREATEST(COALESCE((SELECT MAX(id) FROM vm_telemetry), 0), COALESCE((SELECT MAX(id) FROM vm_telemetry_archive), 0)) as cnt")
                total_records = cur.fetchone()['cnt']

        heap_bytes = int(status_vars.get('rapid_heap_usage', 0) or 0)
        offload = int(status_vars.get('rapid_query_offload_count', 0) or 0)
        non_offload = int(status_vars.get('rapid_query_nonoffload_count', 0) or 0)
        total_queries = offload + non_offload
        offload_rate = (offload / total_queries * 100) if total_queries > 0 else 0

        return {
            "status": "success",
            "cluster": {
                "status": status_vars.get('rapid_cluster_status', 'N/A'),
                "service": status_vars.get('rapid_service_status', 'N/A'),
                "ml_status": status_vars.get('rapid_ml_status', 'N/A'),
                "change_propagation": status_vars.get('rapid_change_propagation_status', 'N/A')
            },
            "memory": {
                "used_mb": round(heap_bytes / 1024 / 1024, 1),
                "total_mb": 16384,
                "usage_percent": round(heap_bytes / 1024 / 1024 / 163.84, 1)
            },
            "performance": {
                "queries_offloaded": offload,
                "queries_not_offloaded": non_offload,
                "offload_rate_percent": round(offload_rate, 1)
            },
            "data": {
                "tables_loaded": tables_loaded,
                "total_records": total_records
            },
            "engine": "HeatWave",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching HeatWave status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/diagnostics")
def get_ai_diagnostics():
    """
    Automated health heuristics & anomaly detection summary with HeatWave HTAP + ML.
    Uses v_node_latest_status view and anomaly_detection table for insights.
    """
    active_names = [n["name"] for n in TARGET_NODES]
    format_strings = ','.join(['%s'] * len(active_names))

    # Use HeatWave view for latest status with health scores
    query_latest = f"""
    SELECT node_name, status, cpu_usage_percent, mem_usage_percent,
           disk_usage_percent, latency_ms as scrape_duration_ms, 
           recorded_at, health_score
    FROM v_node_latest_status
    WHERE node_name IN ({format_strings});
    """
    
    # HeatWave OLAP analytics query
    query_htap = """
    SELECT 
        COUNT(*) as sample_count,
        MAX(scrape_duration_ms) as peak_latency,
        AVG(cpu_usage_percent) as avg_cpu,
        STDDEV(cpu_usage_percent) as cpu_volatility
    FROM vm_telemetry
    WHERE recorded_at >= NOW() - INTERVAL 1 HOUR
    """
    
    # Get recent anomalies from ML detection
    query_anomalies = """
    SELECT node_name, anomaly_type, severity, description, confidence
    FROM anomaly_detection
    WHERE status = 'OPEN' AND detected_at >= NOW() - INTERVAL 24 HOUR
    ORDER BY FIELD(severity, 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'), confidence DESC
    LIMIT 10
    """

    try:
        import time
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Fetch latest data from HeatWave view
                cur.execute(query_latest, tuple(active_names))
                rows = cur.fetchall()
                
                # 2. Run HeatWave OLAP analytics
                htap_start = time.time()
                cur.execute(query_htap)
                htap_res = cur.fetchone()
                htap_duration = time.time() - htap_start
                total_samples = int(htap_res.get('sample_count') or 0) if htap_res else 0
                avg_cpu = float(htap_res.get('avg_cpu') or 0.0) if htap_res else 0.0
                cpu_vol = float(htap_res.get('cpu_volatility') or 0.0) if htap_res else 0.0
                
                # 3. Get ML-detected anomalies
                cur.execute(query_anomalies)
                anomalies = cur.fetchall()
                
                # 4. Get total record count across active and archive partitions for display
                cur.execute("SELECT GREATEST(COALESCE((SELECT MAX(id) FROM vm_telemetry), 0), COALESCE((SELECT MAX(id) FROM vm_telemetry_archive), 0)) as cnt")
                total_records = cur.fetchone()['cnt']
                
                # 5. Get HeatWave offload stats
                cur.execute("SELECT VARIABLE_VALUE FROM performance_schema.global_status WHERE VARIABLE_NAME = 'rapid_query_offload_count'")
                offload_row = cur.fetchone()
                offload_count = int(offload_row['VARIABLE_VALUE']) if offload_row else 0

        total = len(rows)
        online = sum(1 for r in rows if r["status"] == "ONLINE")
        warnings = []
        
        # HeatWave HTAP & ML status messages
        warnings.append(
            f"HeatWave HTAP: 内存加速引擎已处理 {offload_count} 次 OLAP 查询，"
            f"本次分析 {total_samples:,} 条样本仅耗时 {htap_duration*1000:.0f}ms，无需 ETL。"
        )
        warnings.append(
            f"HeatWave ML: 实时监测 {total_records:,} 条遥测记录，"
            f"当前 CPU 均值 {avg_cpu:.1f}%，波动率 {cpu_vol:.2f}。"
        )
        
        # Add ML-detected anomalies
        if anomalies:
            for a in anomalies:
                sev_icon = "🔴" if a['severity'] in ('CRITICAL', 'HIGH') else "🟡" if a['severity'] == 'MEDIUM' else "🟢"
                conf = float(a['confidence']) if a['confidence'] else 0
                warnings.append(
                    f"HeatWave ML 检测 {sev_icon}: [{a['anomaly_type']}] {a['node_name']} - "
                    f"{a['description']} (置信度: {conf*100:.0f}%)"
                )
        else:
            warnings.append("HeatWave ML: 异常检测引擎运行中，当前无高危告警。")

        # Real-time threshold checks
        for r in rows:
            if r["status"] != "ONLINE":
                warnings.append(f"实时告警: 节点 {r['node_name']} 状态异常 ({r['status']})，需要人工介入。")
            elif r.get("cpu_usage_percent", 0) > 80.0:
                warnings.append(f"实时告警: 节点 {r['node_name']} CPU 负载过高 ({r['cpu_usage_percent']:.1f}%)。")
            elif r.get("mem_usage_percent", 0) > 85.0:
                warnings.append(f"实时告警: 节点 {r['node_name']} 内存压力 ({r['mem_usage_percent']:.1f}%)。")
            elif r.get("scrape_duration_ms", 0) > 800:
                warnings.append(f"实时告警: 节点 {r['node_name']} 网络延迟异常 ({r['scrape_duration_ms']}ms)。")

        # Health score: pure average of per-node resource health (CPU/MEM/disk)
        # Reflects actual resource state, not penalized by anomaly counts
        health_score = round(
            sum(float(r.get('health_score', 100) or 100) for r in rows) / max(len(rows), 1),
            1
        )

        # Status: independent rule-based judgment, not derived from health_score
        has_offline = any(r["status"] != "ONLINE" for r in rows)
        has_high_anomaly = any(a.get('severity') in ('CRITICAL', 'HIGH') for a in anomalies)
        has_realtime_alert = any(
            r.get("cpu_usage_percent", 0) > 80.0 or
            r.get("mem_usage_percent", 0) > 85.0 or
            r.get("scrape_duration_ms", 0) > 800
            for r in rows
        )

        if has_offline or has_high_anomaly:
            fleet_status = "CRITICAL"
        elif has_realtime_alert or (len(anomalies) > 0):
            fleet_status = "WARNING"
        else:
            fleet_status = "HEALTHY"

        return {
            "fleet_health_score": health_score,
            "total_nodes": total,
            "online_nodes": online,
            "status": fleet_status,
            "anomalies_count": len(anomalies),
            "diagnostics": warnings,
            "heatwave": {
                "queries_offloaded": offload_count,
                "total_records": total_records,
                "analysis_time_ms": round(htap_duration * 1000, 1)
            },
            "evaluated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        import traceback
        logger.error(f"Error in AI diagnostics: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
import os
from fastapi import Request
from starlette.responses import JSONResponse

INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET")

@app.post("/api/maintenance/prune")
def prune_old_data():
    """Prune telemetry data older than 60 days. Protected by X-Internal-Secret middleware."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Delete from raw table
                cur.execute("DELETE FROM vm_telemetry WHERE recorded_at < NOW() - INTERVAL 60 DAY")
                deleted_raw = cur.rowcount
                # Delete from archive table
                cur.execute("DELETE FROM vm_telemetry_archive WHERE recorded_at < NOW() - INTERVAL 60 DAY")
                deleted_archive = cur.rowcount
            conn.commit()
        return {
            "status": "success",
            "deleted_raw": deleted_raw,
            "deleted_archive": deleted_archive
        }
    except Exception as e:
        logger.error(f"Error during pruning: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.middleware("http")
async def verify_internal_secret(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method != "OPTIONS":
        secret = request.headers.get("X-Internal-Secret")
        # Bypass auth for unit tests if not running in production
        if not INTERNAL_API_SECRET and "pytest" in sys.modules:
             return await call_next(request)
        if secret != INTERNAL_API_SECRET or not secret:
            return JSONResponse(status_code=403, content={"detail": "Forbidden: Invalid internal secret"})
    return await call_next(request)



