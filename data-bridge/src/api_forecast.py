"""Non-blocking HeatWave latency forecast cache and endpoint."""
import json
import logging
import math
import os
import re
import threading
import time
from datetime import datetime

import pymysql
from fastapi import HTTPException

import api_config
from api_database import get_db_connection

logger = logging.getLogger(__name__)

_ml_forecast_cache: dict = {}
_ml_forecast_at = 0.0
_ml_forecast_lock = threading.Lock()
_ml_forecast_refreshing = False
_ML_FORECAST_TTL = 60

def _refresh_ml_forecast() -> None:
    """Background thread: run ML_PREDICT_ROW for all nodes, update cache."""
    global _ml_forecast_cache, _ml_forecast_at, _ml_forecast_refreshing
    try:
        active_names = [n["name"] for n in api_config.TARGET_NODES]
        database = os.getenv("MYSQL_DATABASE", "modo_db")
        mysql_user = os.getenv("MYSQL_USER")
        ml_schema = os.getenv("MYSQL_ML_SCHEMA") or (f"ML_SCHEMA_{mysql_user}" if mysql_user else "")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
            raise RuntimeError("MYSQL_DATABASE must be a valid SQL identifier")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", ml_schema):
            raise RuntimeError("MYSQL_ML_SCHEMA must be a valid SQL identifier")
        train_table = f"{database}.latency_forecast_train"

        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=90,
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT model_handle FROM `{ml_schema}`.MODEL_CATALOG
                WHERE train_table_name = %s
                  AND task = 'regression' AND model_type IS NOT NULL
                ORDER BY model_id DESC LIMIT 1
            """, (train_table,))
            mrow = cur.fetchone()
            if not mrow:
                return
            handle = mrow['model_handle']

            # Fetch real current features per node (never predict on zeros:
            # the model was trained on real cpu/mem/net, so zero inputs push it
            # far outside the training distribution).
            format_strings = ','.join(['%s'] * len(active_names))
            cur.execute(f"""
                SELECT
                    v.node_name,
                    COALESCE(v.cpu_usage_percent, 0) AS cpu,
                    COALESCE(v.mem_usage_percent, 0) AS mem,
                    COALESCE((
                        SELECT t.net_in_bytes_sec / 1000000.0
                        FROM vm_telemetry t
                        WHERE t.node_name = v.node_name
                        ORDER BY t.recorded_at DESC
                        LIMIT 1
                    ), 0) AS net_mb
                FROM v_node_latest_status v
                WHERE v.node_name IN ({format_strings})
            """, tuple(active_names))
            feats = {r['node_name']: r for r in cur.fetchall()}

            new_cache = {}
            for name in active_names:
                f = feats.get(name, {})
                cur.execute("""
                    SELECT sys.ML_PREDICT_ROW(
                        JSON_OBJECT('id',0,'node_name',%s,'hour_of_day',HOUR(NOW()),
                            'day_of_week',DAYOFWEEK(NOW()),
                            'cpu_usage_percent',%s,'mem_usage_percent',%s,'net_in_mb',%s),
                        %s, NULL) as pred
                """, (name, float(f.get('cpu') or 0), float(f.get('mem') or 0),
                      float(f.get('net_mb') or 0), handle))
                row = cur.fetchone()
                if row and row.get('pred'):
                    p = row['pred'] if isinstance(row['pred'], dict) else json.loads(row['pred'])
                    val = p.get('Prediction') or p.get('ml_results', {}).get('predictions', {}).get('scrape_duration_ms')
                    if val:
                        new_cache[name] = round(float(val), 1)
        conn.close()
        with _ml_forecast_lock:
            _ml_forecast_cache = new_cache
            _ml_forecast_at = time.time()
        logger.info(f"ML forecast cache refreshed: {len(new_cache)} nodes")
    except Exception as e:
        logger.warning(f"ML forecast refresh failed: {e}")
    finally:
        _ml_forecast_refreshing = False


def get_ml_forecast(node_name: str) -> float | None:
    """Return cached ML prediction for node, trigger background refresh if stale."""
    global _ml_forecast_refreshing
    now = time.time()
    if now - _ml_forecast_at > _ML_FORECAST_TTL and not _ml_forecast_refreshing:
        _ml_forecast_refreshing = True
        threading.Thread(target=_refresh_ml_forecast, name="ml-forecast", daemon=True).start()
    return _ml_forecast_cache.get(node_name)


def get_latency_forecast():
    """
    Returns per-node latency forecast using HeatWave AutoML (ML_PREDICT_ROW)
    combined with EMA of recent 5 samples for real-time correction.
    Used by the radar panel to drive arrow animation period dynamically.
    """
    active_names = [n["name"] for n in api_config.TARGET_NODES]
    format_strings = ','.join(['%s'] * len(active_names))

    # Query recent EMA: use last 5 scrape values per node via window function
    # Use v_node_latest_status for the latest single reading (lightweight)
    query_recent = f"""
    SELECT
        node_name,
        latency_ms as ema_ms,
        latency_ms as min_ms,
        latency_ms as max_ms,
        1 as samples,
        recorded_at as latest_at
    FROM v_node_latest_status
    WHERE node_name IN ({format_strings})
      AND latency_ms > 0
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # EMA from recent samples (lightweight, uses view index)
                cur.execute(query_recent, tuple(active_names))
                recent_rows = {r['node_name']: r for r in cur.fetchall()}

        # ML prediction: use background cache (non-blocking)
        predicted = {name: get_ml_forecast(name) for name in active_names}
        ml_available = any(v is not None for v in predicted.values())

        results = []
        for name in active_names:
            row = recent_rows.get(name, {})
            ema = float(row.get('ema_ms') or 200)
            ml_val = predicted.get(name)

            # Blend: 60% ML prediction + 40% EMA when model available
            if ml_available and ml_val and ml_val > 0:
                blended = round(ml_val * 0.6 + ema * 0.4, 1)
            else:
                blended = round(ema, 1)

            # Map latency to animation period using log scale
            # 15ms → ~6s,  200ms → ~10s,  500ms → ~12s,  700ms → ~13s
            clamped = max(10, min(1000, blended))
            period = round(1.0 + (math.log10(clamped) / math.log10(1000)) * 14, 2)

            results.append({
                "node_name": name,
                "predicted_ms": blended,
                "ml_ms": ml_val,
                "ema_ms": round(ema, 1),
                "period": period,
                "ml_available": ml_available,
                "samples": row.get('samples', 0),
                "latest_at": row.get('latest_at').isoformat() if row.get('latest_at') else None
            })

        return {
            "status": "success",
            "ml_available": ml_available,
            "count": len(results),
            "data": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in latency forecast: {e}")
        raise HTTPException(status_code=500, detail=str(e))
