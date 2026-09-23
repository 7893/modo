"""Health and telemetry query handlers."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Query

import api_config
from api_database import get_db_connection

logger = logging.getLogger(__name__)

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
        "node": api_config.SERVICE_NODE_NAME,
        "database_status": "connected" if db_ok else "error",
        "timestamp": datetime.now().isoformat()
    }


def get_latest_metrics():
    """
    Returns the latest telemetry snapshot for every registered active node.
    Uses HeatWave-optimized view v_node_latest_status for acceleration.
    Used for dashboard top cards, world map status, and fleet overview.
    """
    active_names = [n["name"] for n in api_config.TARGET_NODES]
    node_map = {n["name"]: n for n in api_config.TARGET_NODES}

    # Use HeatWave-optimized view instead of subquery
    format_strings = ','.join(['%s'] * len(active_names))
    query = f"""
    SELECT /*+ MAX_EXECUTION_TIME(6000) */
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


def get_metrics_history(
    node: Optional[str] = Query(None, description="Filter by configured node name"),
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
    SELECT /*+ MAX_EXECUTION_TIME(6000) */
    node_name, hour, samples, avg_cpu, avg_mem,
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
