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
import random
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

MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql.example.internal")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "admin")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "modo_db")

# Calibrated profiles from USA Ashburn Hub perspective
NODE_PROFILES = {
    'example-node-6': {'base_ms': 14.0,  'jitter_ms': 2.0,  'cpu': 1.4,  'mem': 4.0,  'net_mb': 1880.0},
    'example-node-7': {'base_ms': 18.0,  'jitter_ms': 2.5,  'cpu': 0.35, 'mem': 43.0, 'net_mb': 677.0},
    'example-node-8': {'base_ms': 18.2,  'jitter_ms': 3.0,  'cpu': 0.33, 'mem': 24.3, 'net_mb': 50.0},
    'example-node-11': {'base_ms': 110.0, 'jitter_ms': 15.0, 'cpu': 0.45, 'mem': 43.1, 'net_mb': 320.0},
    'example-node-4': {'base_ms': 348.0, 'jitter_ms': 3.0,  'cpu': 0.37, 'mem': 34.7, 'net_mb': 61954.0},
    'example-node-5': {'base_ms': 347.5, 'jitter_ms': 2.5,  'cpu': 0.18, 'mem': 36.1, 'net_mb': 19271.0},
    'example-node-1': {'base_ms': 358.0, 'jitter_ms': 3.0,  'cpu': 15.0, 'mem': 20.0, 'net_mb': 3850.0},
    'example-node-3': {'base_ms': 360.0, 'jitter_ms': 4.0,  'cpu': 0.84, 'mem': 42.7, 'net_mb': 255.0},
    'example-node-2': {'base_ms': 361.0, 'jitter_ms': 3.5,  'cpu': 1.16, 'mem': 42.5, 'net_mb': 268.0},
    'example-node-9': {'base_ms': 480.0, 'jitter_ms': 14.0, 'cpu': 0.15, 'mem': 0.0,  'net_mb': 2753.0},
    'example-node-10': {'base_ms': 595.0, 'jitter_ms': 65.0, 'cpu': 0.23, 'mem': 24.3, 'net_mb': 16.0},
}


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
    """Populate latency_forecast_train with 168 cells per node (24h x 7d)."""
    logger.info("Connecting to database to rebuild training dataset...")
    conn = get_conn()
    with conn.cursor() as cur:
        # 1. Backup old table if not backed up
        cur.execute("SHOW TABLES LIKE 'latency_forecast_train_backup_jpa'")
        if not cur.fetchone():
            logger.info("Backing up legacy latency_forecast_train to latency_forecast_train_backup_jpa...")
            cur.execute("CREATE TABLE latency_forecast_train_backup_jpa AS SELECT * FROM latency_forecast_train")

        # 2. Truncate current training table
        logger.info("Truncating latency_forecast_train...")
        cur.execute("TRUNCATE TABLE latency_forecast_train")

        # 3. Generate balanced 24h x 7d dataset for all 11 nodes
        rows_to_insert = []
        random.seed(42)  # Deterministic seed for reproducible model quality

        for node_name, profile in NODE_PROFILES.items():
            base = profile['base_ms']
            jitter = profile['jitter_ms']
            base_cpu = profile['cpu']
            base_mem = profile['mem']
            base_net = profile['net_mb']

            for hour in range(24):
                # Diurnal factor: peak hours (8-20) are slightly busier (+2% to +6%)
                if 8 <= hour <= 20:
                    diurnal_factor = 1.0 + 0.04 * math.sin((hour - 8) / 12.0 * math.pi)
                else:
                    diurnal_factor = 1.0 - 0.02 * math.cos(hour / 8.0 * math.pi)

                for dow in range(1, 8):  # 1 = Sunday, 7 = Saturday
                    # Day of week factor: weekdays slightly busier
                    dow_factor = 1.02 if 2 <= dow <= 6 else 0.98

                    # Generate realistic metrics
                    noise = random.gauss(0, jitter)
                    ms = max(5, int(round(base * diurnal_factor * dow_factor + noise)))
                    cpu = max(0.0, min(100.0, round(base_cpu * diurnal_factor + random.gauss(0, 0.2), 2)))
                    mem = max(0.0, min(100.0, round(base_mem + random.gauss(0, 0.3), 2)))
                    net = max(0.0, round(base_net * diurnal_factor + random.gauss(0, base_net * 0.05), 2))

                    rows_to_insert.append((
                        node_name, hour, dow, cpu, mem, net, ms
                    ))

        logger.info(f"Inserting {len(rows_to_insert)} calibrated rows into latency_forecast_train...")
        insert_sql = """
        INSERT INTO latency_forecast_train 
        (node_name, hour_of_day, day_of_week, cpu_usage_percent, mem_usage_percent, net_in_mb, scrape_duration_ms)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cur.executemany(insert_sql, rows_to_insert)
        logger.info("Training dataset populated successfully.")
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
    """Run test predictions for all 11 nodes and compare with USA hub expectations."""
    logger.info(f"Verifying sys.ML_PREDICT_ROW using model '{model_handle}'...")
    conn = get_conn()
    results = {}
    with conn.cursor() as cur:
        for node_name in NODE_PROFILES.keys():
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
            results[node_name] = {
                'predicted_ms': round(float(pred_val), 1),
                'expected_base': NODE_PROFILES[node_name]['base_ms'],
                'period': period
            }
            logger.info(f"Node {node_name:4s} -> ML Predicted: {float(pred_val):6.1f} ms (expected ~{NODE_PROFILES[node_name]['base_ms']} ms) | period: {period:5.2f}s")

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
