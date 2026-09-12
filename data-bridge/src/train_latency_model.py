"""
MODO Data Bridge - HeatWave AutoML Latency Forecast Retraining Script
Reconstructs latency_forecast_train for the USA Hub architecture (usa as central hub),
executes sys.ML_TRAIN with regression task, loads the model into HeatWave memory,
and verifies real-time inference via sys.ML_PREDICT_ROW.
"""
import os
import sys
import time
import math
import logging
import pymysql
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("train_latency_model")

# Load environment
for env_path in [
    os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    os.path.join(os.path.dirname(__file__), "..", ".env"),
    "/home/ubuntu/modo/.env",
    ".env"
]:
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        break

MYSQL_HOST = os.getenv("MYSQL_HOST", "10.0.0.145")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "admin")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "modo_db")


def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=600,
        write_timeout=600,
        autocommit=True
    )


def rebuild_training_data():
    """Populate latency_forecast_train by aggregating REAL telemetry from
    vm_telemetry, grouped by (node_name, hour_of_day, day_of_week).

    PRIORITY: Uses rtt_ms (true TCP RTT) as the target when available.
    Falls back to scrape_duration_ms only if rtt_ms data is insufficient.
    This ensures the model learns actual network latency, not HTTP fetch time.
    """
    logger.info("Connecting to database to rebuild training dataset from real telemetry...")
    conn = get_conn()
    with conn.cursor() as cur:
        # 1. Snapshot the current training table for rollback/comparison.
        backup_name = f"latency_forecast_train_backup_{int(time.time())}"
        logger.info(f"Backing up current latency_forecast_train to {backup_name}...")
        cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM latency_forecast_train")

        # 2. Check how much rtt_ms data we have
        cur.execute("SELECT COUNT(*) AS cnt FROM vm_telemetry WHERE rtt_ms IS NOT NULL AND rtt_ms > 0")
        rtt_count = cur.fetchone()['cnt']
        logger.info(f"Available rtt_ms records: {rtt_count}")

        # Use rtt_ms if we have enough data (at least 100 records), else fall back
        use_rtt = rtt_count >= 100
        target_col = "rtt_ms" if use_rtt else "scrape_duration_ms"
        logger.info(f"Using '{target_col}' as training target (threshold: 100 records)")

        # 3. Aggregate real telemetry into the (node, hour, dow) grid.
        #    Target uses a 10% TRIMMED MEAN to resist jitter and outliers.
        #    For small buckets, falls back to plain mean.
        agg_sql = f"""
        WITH ranked AS (
            SELECT
                node_name,
                HOUR(recorded_at)       AS hour_of_day,
                DAYOFWEEK(recorded_at)  AS day_of_week,
                cpu_usage_percent,
                mem_usage_percent,
                net_in_bytes_sec,
                {target_col} AS target_latency,
                ROW_NUMBER() OVER (
                    PARTITION BY node_name, HOUR(recorded_at), DAYOFWEEK(recorded_at)
                    ORDER BY {target_col}
                ) AS rn,
                COUNT(*) OVER (
                    PARTITION BY node_name, HOUR(recorded_at), DAYOFWEEK(recorded_at)
                ) AS cnt
            FROM vm_telemetry
            WHERE {target_col} IS NOT NULL AND {target_col} > 0
        )
        SELECT
            node_name,
            hour_of_day,
            day_of_week,
            ROUND(AVG(cpu_usage_percent), 2)             AS cpu_usage_percent,
            ROUND(AVG(mem_usage_percent), 2)             AS mem_usage_percent,
            ROUND(AVG(net_in_bytes_sec) / 1000000.0, 2)  AS net_in_mb,
            ROUND(
                COALESCE(
                    AVG(CASE WHEN cnt >= 10
                              AND rn >  cnt * 0.1
                              AND rn <= cnt * 0.9
                             THEN target_latency END),
                    AVG(target_latency)
                )
            )                                            AS latency_ms
        FROM ranked
        GROUP BY node_name, hour_of_day, day_of_week
        """
        cur.execute(agg_sql)
        rows = cur.fetchall()
        rows_to_insert = [
            (
                r["node_name"], int(r["hour_of_day"]), int(r["day_of_week"]),
                float(r["cpu_usage_percent"] or 0.0),
                float(r["mem_usage_percent"] or 0.0),
                float(r["net_in_mb"] or 0.0),
                int(r["latency_ms"] or 0),
            )
            for r in rows
        ]

        if not rows_to_insert:
            raise RuntimeError("No aggregated rows produced from vm_telemetry; aborting to avoid emptying the training table.")

        # 3. Replace training data only after aggregation succeeded.
        logger.info("Truncating latency_forecast_train...")
        cur.execute("TRUNCATE TABLE latency_forecast_train")

        logger.info(f"Inserting {len(rows_to_insert)} real aggregated rows into latency_forecast_train...")
        insert_sql = """
        INSERT INTO latency_forecast_train
        (node_name, hour_of_day, day_of_week, cpu_usage_percent, mem_usage_percent, net_in_mb, scrape_duration_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cur.executemany(insert_sql, rows_to_insert)
        logger.info(f"Training dataset rebuilt from real telemetry ({len(rows_to_insert)} rows). Backup: {backup_name}")
    conn.close()


def train_automl_model():
    """Execute sys.ML_TRAIN and sys.ML_MODEL_LOAD for MODO latency forecast."""
    logger.info("Executing sys.ML_TRAIN on modo_db.latency_forecast_train...")
    conn = get_conn()
    model_handle = "MODO_LATENCY_FORECAST"

    with conn.cursor() as cur:
        # Check if old model exists and unload it
        try:
            cur.execute(f"CALL sys.ML_MODEL_UNLOAD('{model_handle}')")
            logger.info(f"Unloaded previous model '{model_handle}'")
        except Exception as e:
            logger.info(f"ML_MODEL_UNLOAD info: {e}")

        try:
            cur.execute(f"DELETE FROM ML_SCHEMA_admin.MODEL_CATALOG WHERE model_handle = '{model_handle}'")
            logger.info(f"Removed previous catalog record for '{model_handle}'")
        except Exception as e:
            logger.info(f"Catalog delete info: {e}")

        # Set user variable for model handle
        cur.execute(f"SET @model_handle = '{model_handle}'")

        # Execute ML_TRAIN
        t0 = time.time()
        logger.info("Starting HeatWave AutoML training (this typically takes 30-90 seconds)...")
        train_sql = """
        CALL sys.ML_TRAIN(
            'modo_db.latency_forecast_train',
            'scrape_duration_ms',
            JSON_OBJECT(
                'task', 'regression',
                'exclude_column_list', JSON_ARRAY('id')
            ),
            @model_handle
        )
        """
        cur.execute(train_sql)
        duration = time.time() - t0
        logger.info(f"ML_TRAIN completed in {duration:.2f} seconds.")

        # Check model catalog record
        cur.execute("""
            SELECT model_id, model_handle, train_table_name, target_column_name, task, model_type 
            FROM ML_SCHEMA_admin.MODEL_CATALOG
            WHERE train_table_name = 'modo_db.latency_forecast_train'
            ORDER BY model_id DESC LIMIT 1
        """)
        m_info = cur.fetchone()
        logger.info(f"Trained model in MODEL_CATALOG: {m_info}")

        if not m_info:
            raise RuntimeError("Model was not found in ML_SCHEMA_admin.MODEL_CATALOG after training!")

        # Load model into memory
        actual_handle = m_info['model_handle']
        logger.info(f"Loading model '{actual_handle}' into HeatWave memory...")
        cur.execute(f"CALL sys.ML_MODEL_LOAD('{actual_handle}', NULL)")
        logger.info("Model loaded successfully.")

    conn.close()
    return actual_handle


def verify_predictions(model_handle: str):
    """Run test predictions for all nodes and compare with real historical mean."""
    logger.info(f"Verifying sys.ML_PREDICT_ROW using model '{model_handle}'...")
    conn = get_conn()
    results = {}
    with conn.cursor() as cur:
        # Check which target we should compare against (rtt_ms preferred)
        cur.execute("SELECT COUNT(*) AS cnt FROM vm_telemetry WHERE rtt_ms IS NOT NULL AND rtt_ms > 0")
        rtt_count = cur.fetchone()['cnt']
        use_rtt = rtt_count >= 100
        target_col = "rtt_ms" if use_rtt else "scrape_duration_ms"
        logger.info(f"Comparing predictions against real '{target_col}' averages")

        # Real historical mean latency per node
        cur.execute(f"""
            SELECT node_name, ROUND(AVG({target_col}), 1) AS real_avg_ms
            FROM vm_telemetry
            WHERE {target_col} IS NOT NULL AND {target_col} > 0
            GROUP BY node_name
        """)
        real_avg = {r['node_name']: float(r['real_avg_ms']) for r in cur.fetchall()}

        for node_name in real_avg.keys():
            cur.execute("""
                SELECT sys.ML_PREDICT_ROW(
                    JSON_OBJECT(
                        'id', 0,
                        'node_name', %s,
                        'hour_of_day', HOUR(NOW()),
                        'day_of_week', DAYOFWEEK(NOW()),
                        'cpu_usage_percent', 0,
                        'mem_usage_percent', 0,
                        'net_in_mb', 0
                    ),
                    %s,
                    NULL
                ) as pred
            """, (node_name, model_handle))
            row = cur.fetchone()
            import json
            pred_raw = row['pred'] if isinstance(row['pred'], dict) else json.loads(row['pred'])
            pred_val = pred_raw.get('Prediction') or pred_raw.get('ml_results', {}).get('predictions', {}).get('scrape_duration_ms')

            # Compute period as frontend does
            clamped = max(10, min(1000, float(pred_val)))
            period = round(1.0 + (math.log10(clamped) / math.log10(1000)) * 14, 2)
            expected = real_avg.get(node_name, 0.0)
            results[node_name] = {
                'predicted_ms': round(float(pred_val), 1),
                'real_avg_ms': expected,
                'period': period
            }
            logger.info(f"Node {node_name:4s} -> ML Predicted: {float(pred_val):6.1f} ms (real avg ~{expected:.1f} ms) | period: {period:5.2f}s")

    conn.close()
    return results


def main():
    logger.info("=== STEP 1: Rebuilding Training Dataset ===")
    rebuild_training_data()

    logger.info("\n=== STEP 2: Executing HeatWave sys.ML_TRAIN ===")
    handle = train_automl_model()

    logger.info(f"\n=== STEP 3: Verifying In-Database Predictions ({handle}) ===")
    results = verify_predictions(handle)

    logger.info("\n=== All AutoML Retraining Steps Finished Successfully ===")


if __name__ == "__main__":
    main()
