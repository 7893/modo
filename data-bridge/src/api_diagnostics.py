"""Fleet health diagnostics backed by HeatWave telemetry."""
import logging
import time
from datetime import datetime

from fastapi import HTTPException

import api_config
from api_database import get_db_connection

logger = logging.getLogger(__name__)

def get_ai_diagnostics():
    """
    Automated health heuristics & anomaly detection summary with HeatWave HTAP + ML.
    Uses v_node_latest_status view and anomaly_detection table for insights.
    """
    active_names = [n["name"] for n in api_config.TARGET_NODES]
    format_strings = ','.join(['%s'] * len(active_names))

    # Use HeatWave view for latest status with health scores
    query_latest = f"""
    SELECT /*+ MAX_EXECUTION_TIME(6000) */
    node_name, status, cpu_usage_percent, mem_usage_percent,
           disk_usage_percent, latency_ms as scrape_duration_ms,
           recorded_at, health_score
    FROM v_node_latest_status
    WHERE node_name IN ({format_strings});
    """

    # HeatWave OLAP analytics query
    query_htap = """
    SELECT /*+ MAX_EXECUTION_TIME(6000) */
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
                cur.execute("SELECT (SELECT COUNT(*) FROM vm_telemetry) + (SELECT COUNT(*) FROM vm_telemetry_archive) AS cnt")
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
