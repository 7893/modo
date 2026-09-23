"""HeatWave analytics query handlers."""
import logging
from datetime import datetime

from fastapi import HTTPException, Query

from api_database import get_db_connection

logger = logging.getLogger(__name__)

def get_fleet_health_report():
    """
    Returns comprehensive fleet health report from HeatWave v_fleet_health_report view.
    Includes health scores, trends, and hour-over-hour comparisons.
    """
    query = """
    SELECT /*+ MAX_EXECUTION_TIME(6000) */ *
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


def get_anomaly_dashboard():
    """
    Returns anomaly detection summary from HeatWave v_anomaly_dashboard view.
    Shows anomaly types, severity distribution, and open issues.
    """
    query = """
    SELECT /*+ MAX_EXECUTION_TIME(6000) */
    anomaly_type, severity, count, open_count,
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


def get_heatwave_status():
    """
    Returns HeatWave cluster status and performance metrics.
    Shows memory usage, query offload stats, and acceleration ratios.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get HeatWave status variables - single query instead of 7 separate ones
                cur.execute("""
                    SELECT VARIABLE_NAME, VARIABLE_VALUE
                    FROM performance_schema.global_status
                    WHERE VARIABLE_NAME IN (
                        'rapid_cluster_status', 'rapid_service_status',
                        'rapid_heap_usage', 'rapid_query_offload_count',
                        'rapid_query_nonoffload_count', 'rapid_change_propagation_status',
                        'rapid_ml_status'
                    )
                """)
                status_vars = {row['VARIABLE_NAME']: row['VARIABLE_VALUE'] for row in cur.fetchall()}

                # HeatWave exposes rpd_tables; standard MySQL does not.
                try:
                    cur.execute("SELECT COUNT(*) as cnt FROM performance_schema.rpd_tables")
                    tables_loaded = cur.fetchone()['cnt']
                except Exception as heatwave_error:
                    logger.info("HeatWave table metrics unavailable: %s", heatwave_error)
                    tables_loaded = 0

                # Get total records across active and archive partitions.
                cur.execute("SELECT (SELECT COUNT(*) FROM vm_telemetry) + (SELECT COUNT(*) FROM vm_telemetry_archive) AS cnt")
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
