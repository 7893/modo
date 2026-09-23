"""Initialize the complete MODO schema on MySQL or MySQL HeatWave."""

import logging
import os
import re

import mysql.connector
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv()


def get_db_config():
    """Get validated database configuration from environment variables."""
    host = os.getenv("MYSQL_HOST")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQL_DATABASE", "modo_db")

    if not all([host, user, password]):
        raise RuntimeError("Missing required environment variables: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD")
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", database):
        raise ValueError(f"Invalid database name: {database}")

    return host, port, user, password, database


def _ensure_column(cursor, database: str, table: str, column: str, ddl: str) -> None:
    """Add a column when upgrading a schema created by an older release."""
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """,
        (database, table, column),
    )
    if cursor.fetchone()[0] == 0:
        logger.info("Adding missing column %s.%s", table, column)
        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN {ddl}")


def init_db():
    """Create all tables and views required by the API and training jobs."""
    host, port, user, password, database = get_db_config()
    logger.info("Connecting to MySQL server at %s:%s as %s...", host, port, user)
    conn = None
    cursor = None

    try:
        conn = mysql.connector.connect(host=host, port=port, user=user, password=password)
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE `{database}`")

        logger.info("Creating telemetry tables...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vm_telemetry (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                node_name VARCHAR(32) NOT NULL,
                host_ip VARCHAR(64) NOT NULL,
                region VARCHAR(32) DEFAULT '',
                cpu_usage_percent FLOAT DEFAULT NULL,
                mem_total_bytes BIGINT DEFAULT 0,
                mem_available_bytes BIGINT DEFAULT 0,
                mem_usage_percent FLOAT DEFAULT 0.0,
                disk_usage_percent FLOAT DEFAULT 0.0,
                net_in_bytes_sec BIGINT DEFAULT 0,
                net_out_bytes_sec BIGINT DEFAULT 0,
                scrape_duration_ms INT DEFAULT 0,
                rtt_ms INT DEFAULT NULL,
                status VARCHAR(16) DEFAULT 'ONLINE',
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_node_time (node_name, recorded_at),
                INDEX idx_recorded_at (recorded_at)
            ) ENGINE=InnoDB
            """
        )
        _ensure_column(cursor, database, "vm_telemetry", "rtt_ms", "`rtt_ms` INT DEFAULT NULL AFTER `scrape_duration_ms`")

        cursor.execute("CREATE TABLE IF NOT EXISTS vm_telemetry_archive LIKE vm_telemetry")
        _ensure_column(cursor, database, "vm_telemetry_archive", "rtt_ms", "`rtt_ms` INT DEFAULT NULL AFTER `scrape_duration_ms`")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS anomaly_detection (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                node_name VARCHAR(32) NOT NULL,
                anomaly_type VARCHAR(64) NOT NULL,
                severity ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL DEFAULT 'LOW',
                description VARCHAR(512) NOT NULL,
                confidence DECIMAL(6,5) DEFAULT NULL,
                status ENUM('OPEN', 'RESOLVED') NOT NULL DEFAULT 'OPEN',
                detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP NULL DEFAULT NULL,
                INDEX idx_anomaly_status_time (status, detected_at),
                INDEX idx_anomaly_node_time (node_name, detected_at)
            ) ENGINE=InnoDB
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS latency_forecast_train (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                node_name VARCHAR(32) NOT NULL,
                hour_of_day TINYINT UNSIGNED NOT NULL,
                day_of_week TINYINT UNSIGNED NOT NULL,
                cpu_usage_percent FLOAT NOT NULL DEFAULT 0,
                mem_usage_percent FLOAT NOT NULL DEFAULT 0,
                net_in_mb FLOAT NOT NULL DEFAULT 0,
                scrape_duration_ms INT NOT NULL,
                INDEX idx_latency_node_time (node_name, day_of_week, hour_of_day)
            ) ENGINE=InnoDB
            """
        )

        logger.info("Creating analytics views...")
        cursor.execute(
            """
            CREATE OR REPLACE VIEW vm_telemetry_hourly AS
            WITH base AS (
                SELECT
                    t.*,
                    CAST(DATE_FORMAT(recorded_at, '%Y-%m-%d %H:00:00') AS DATETIME) AS hour_bucket,
                    COALESCE(rtt_ms, scrape_duration_ms) AS latency_ms
                FROM vm_telemetry t
            ), ranked AS (
                SELECT
                    base.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY node_name, hour_bucket
                        ORDER BY latency_ms
                    ) AS latency_rank,
                    COUNT(*) OVER (
                        PARTITION BY node_name, hour_bucket
                    ) AS bucket_count
                FROM base
            )
            SELECT
                node_name,
                hour_bucket,
                COUNT(*) AS sample_count,
                SUM(status = 'ONLINE') AS online_count,
                ROUND(AVG(status = 'ONLINE'), 4) AS online_ratio,
                ROUND(AVG(cpu_usage_percent), 2) AS cpu_avg,
                ROUND(MAX(cpu_usage_percent), 2) AS cpu_max,
                ROUND(MIN(cpu_usage_percent), 2) AS cpu_min,
                ROUND(STDDEV_POP(cpu_usage_percent), 2) AS cpu_stddev,
                ROUND(AVG(mem_usage_percent), 2) AS mem_avg,
                ROUND(MAX(mem_usage_percent), 2) AS mem_max,
                ROUND(AVG(disk_usage_percent), 2) AS disk_avg,
                ROUND(MAX(disk_usage_percent), 2) AS disk_max,
                ROUND(AVG(latency_ms), 2) AS latency_avg,
                MAX(latency_ms) AS latency_max,
                MIN(CASE
                    WHEN latency_rank >= CEIL(bucket_count * 0.95) THEN latency_ms
                END) AS latency_p95
            FROM ranked
            GROUP BY node_name, hour_bucket
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_node_latest_status AS
            WITH ranked AS (
                SELECT t.*,
                       ROW_NUMBER() OVER (PARTITION BY node_name ORDER BY recorded_at DESC, id DESC) AS row_num
                FROM vm_telemetry t
            )
            SELECT
                node_name,
                host_ip,
                region,
                cpu_usage_percent,
                mem_usage_percent,
                disk_usage_percent,
                COALESCE(rtt_ms, scrape_duration_ms) AS latency_ms,
                status,
                recorded_at,
                ROUND(GREATEST(0, LEAST(100,
                    100 - COALESCE(cpu_usage_percent, 0) * 0.4
                        - COALESCE(mem_usage_percent, 0) * 0.35
                        - COALESCE(disk_usage_percent, 0) * 0.25
                )), 1) AS health_score,
                ROUND(GREATEST(0, 100 - COALESCE(cpu_usage_percent, 0)), 1) AS cpu_score,
                ROUND(GREATEST(0, 100 - COALESCE(mem_usage_percent, 0)), 1) AS mem_score
            FROM ranked
            WHERE row_num = 1
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_realtime_analytics AS
            SELECT
                node_name,
                hour_bucket AS hour,
                sample_count AS samples,
                cpu_avg AS avg_cpu,
                mem_avg AS avg_mem,
                cpu_stddev AS cpu_volatility,
                latency_max AS peak_latency
            FROM vm_telemetry_hourly
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_fleet_health_report AS
            SELECT
                node_name,
                status,
                cpu_usage_percent,
                mem_usage_percent,
                disk_usage_percent,
                latency_ms,
                health_score,
                recorded_at,
                DENSE_RANK() OVER (ORDER BY cpu_usage_percent DESC) AS cpu_load_rank
            FROM v_node_latest_status
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_anomaly_dashboard AS
            SELECT
                anomaly_type,
                severity,
                COUNT(*) AS count,
                SUM(status = 'OPEN') AS open_count,
                ROUND(AVG(confidence), 4) AS avg_confidence,
                MAX(detected_at) AS latest
            FROM anomaly_detection
            GROUP BY anomaly_type, severity
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_telemetry_ml_features AS
            SELECT
                node_name,
                cpu_usage_percent,
                mem_usage_percent,
                disk_usage_percent,
                ROUND(net_in_bytes_sec / 1024 / 1024, 2) AS net_in_mb,
                ROUND(net_out_bytes_sec / 1024 / 1024, 2) AS net_out_mb,
                status,
                recorded_at
            FROM vm_telemetry
            WHERE recorded_at >= NOW() - INTERVAL 7 DAY
              AND status IS NOT NULL
              AND cpu_usage_percent IS NOT NULL
              AND mem_usage_percent IS NOT NULL
              AND disk_usage_percent IS NOT NULL
            """
        )

        cursor.execute(
            """
            CREATE OR REPLACE VIEW v_telemetry_hourly_forecasting AS
            SELECT
                node_name,
                hour_bucket,
                sample_count,
                online_count,
                online_ratio,
                cpu_avg,
                cpu_max,
                cpu_min,
                cpu_stddev,
                mem_avg,
                mem_max,
                disk_avg,
                disk_max,
                latency_avg,
                latency_max,
                latency_p95
            FROM vm_telemetry_hourly
            """
        )

        conn.commit()
        logger.info("Database tables and views initialized successfully")
    except mysql.connector.Error as err:
        if conn:
            conn.rollback()
        logger.error("MySQL error: %s", err)
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    init_db()
