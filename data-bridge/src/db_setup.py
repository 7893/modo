"""
Nexus Data Bridge - Database Setup
Initializes the nexus_db database and vm_telemetry table on MySQL HeatWave.
"""
import os
import re
import logging
import mysql.connector
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv()


def get_db_config():
    """Get database configuration from environment variables."""
    host = os.getenv("MYSQL_HOST")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQL_DATABASE", "nexus_db")
    
    if not all([host, user, password]):
        raise RuntimeError("Missing required environment variables: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD")
    
    # Validate database name to prevent SQL injection
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', database):
        raise ValueError(f"Invalid database name: {database}")
    
    return host, port, user, password, database


def init_db():
    host, port, user, password, database = get_db_config()
    logger.info(f"Connecting to MySQL server at {host}:{port} as {user}...")
    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        # 1. Create database (database name validated in get_db_config)
        logger.info(f"Creating database '{database}' if not exists...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.execute(f"USE `{database}`;")
        
        # 2. Create vm_telemetry table
        logger.info("Creating table 'vm_telemetry' if not exists...")
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS vm_telemetry (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            node_name VARCHAR(32) NOT NULL,
            host_ip VARCHAR(64) NOT NULL,
            region VARCHAR(32) DEFAULT '',
            cpu_usage_percent FLOAT DEFAULT 0.0,
            mem_total_bytes BIGINT DEFAULT 0,
            mem_available_bytes BIGINT DEFAULT 0,
            mem_usage_percent FLOAT DEFAULT 0.0,
            disk_usage_percent FLOAT DEFAULT 0.0,
            net_in_bytes_sec BIGINT DEFAULT 0,
            net_out_bytes_sec BIGINT DEFAULT 0,
            scrape_duration_ms INT DEFAULT 0,
            status VARCHAR(16) DEFAULT 'ONLINE',
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_node_time (node_name, recorded_at),
            INDEX idx_recorded_at (recorded_at)
        ) ENGINE=InnoDB;
        """
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("Database and table initialized successfully")
        
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        logger.error(f"MySQL error: {err}")
        raise


if __name__ == "__main__":
    init_db()
