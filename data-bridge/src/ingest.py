"""
Nexus Data Bridge - Telemetry Ingestion Service
Scrapes node_exporter metrics (port 9100) from all configured global VMs
and ingests parsed metrics into MySQL HeatWave.
"""
import os
import json
import logging
import time
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pymysql
from dbutils.pooled_db import PooledDB
from dotenv import load_dotenv

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

SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "60"))

# Database connection pool (lazy initialization)
_db_pool = None

# Load nodes from config file
_nodes_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "nodes.json")


def load_target_nodes() -> list:
    """Load target nodes from nodes.json config file."""
    try:
        with open(_nodes_config_path, "r") as f:
            nodes = json.load(f)
            logger.info(f"Loaded {len(nodes)} nodes from config")
            return nodes
    except FileNotFoundError:
        logger.error(f"nodes.json not found at {_nodes_config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in nodes.json: {e}")
        raise


# Target nodes (loaded from config)
TARGET_NODES = load_target_nodes()

# Global state for CPU usage calculation
_previous_cpu_state = {}  # Format: { "node_name": {"timestamp": float, "cpu_total": float, "cpu_idle": float} }


def get_db_pool() -> PooledDB:
    """Get or create the database connection pool."""
    global _db_pool
    if _db_pool is None:
        host = os.getenv("MYSQL_HOST")
        port = int(os.getenv("MYSQL_PORT", "3306"))
        user = os.getenv("MYSQL_USER")
        password = os.getenv("MYSQL_PASSWORD")
        database = os.getenv("MYSQL_DATABASE", "nexus_db")
        
        if not all([host, user, password]):
            raise RuntimeError("Missing required environment variables: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD")
        
        _db_pool = PooledDB(
            creator=pymysql,
            maxconnections=5,
            mincached=1,
            maxcached=3,
            blocking=True,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
        )
        logger.info(f"Database connection pool initialized (host={host}, database={database})")
    
    return _db_pool


def parse_prometheus_metrics(raw_text: str) -> dict:
    """Extract key metrics from raw Prometheus text format."""
    metrics = {
        "mem_total": 0,
        "mem_avail": 0,
        "disk_size": 0,
        "disk_free": 0,
        "net_in": 0,
        "net_out": 0,
        "cpu_total_secs": 0.0,
        "cpu_idle_secs": 0.0,
    }
    
    for line in raw_text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
            
        # CPU metrics
        if line.startswith("node_cpu_seconds_total{"):
            val = float(line.split()[1])
            metrics["cpu_total_secs"] += val
            if 'mode="idle"' in line:
                metrics["cpu_idle_secs"] += val
        
        # Memory metrics
        elif line.startswith("node_memory_MemTotal_bytes "):
            metrics["mem_total"] = float(line.split()[1])
        elif line.startswith("node_memory_MemAvailable_bytes "):
            metrics["mem_avail"] = float(line.split()[1])
            
        # Root filesystem metrics
        elif 'node_filesystem_size_bytes{device="/dev/' in line and 'mountpoint="/"' in line:
            metrics["disk_size"] = float(line.split()[1])
        elif 'node_filesystem_avail_bytes{device="/dev/' in line and 'mountpoint="/"' in line:
            metrics["disk_free"] = float(line.split()[1])
            
        # Network metrics
        elif line.startswith("node_network_receive_bytes_total{device="):
            if 'device="lo"' not in line:
                metrics["net_in"] += float(line.split()[1])
        elif line.startswith("node_network_transmit_bytes_total{device="):
            if 'device="lo"' not in line:
                metrics["net_out"] += float(line.split()[1])

    return metrics


def scrape_single_node(node: dict) -> dict:
    """Scrapes metrics from one node's node_exporter."""
    target_url = f"http://{node['host']}:9100/metrics"
    start_time = time.time()
    result = {
        "node_name": node["name"],
        "host_ip": node["host"],
        "region": node["region"],
        "cpu_usage_percent": 0.0,
        "mem_total_bytes": 0,
        "mem_available_bytes": 0,
        "mem_usage_percent": 0.0,
        "disk_usage_percent": 0.0,
        "net_in_bytes_sec": 0,
        "net_out_bytes_sec": 0,
        "scrape_duration_ms": 0,
        "status": "OFFLINE",
    }
    
    try:
        resp = requests.get(target_url, timeout=3.5)
        duration_ms = int((time.time() - start_time) * 1000)
        result["scrape_duration_ms"] = duration_ms
        
        if resp.status_code == 200:
            parsed = parse_prometheus_metrics(resp.text)
            result["status"] = "ONLINE"
            result["mem_total_bytes"] = int(parsed["mem_total"])
            result["mem_available_bytes"] = int(parsed["mem_avail"])
            
            # CPU Calculation
            if parsed["cpu_total_secs"] > 0:
                current_time = time.time()
                prev_state = _previous_cpu_state.get(node["name"])
                
                if prev_state:
                    total_diff = parsed["cpu_total_secs"] - prev_state["cpu_total"]
                    idle_diff = parsed["cpu_idle_secs"] - prev_state["cpu_idle"]
                    
                    if total_diff > 0 and idle_diff >= 0 and total_diff >= idle_diff:
                        usage = 100.0 * (1.0 - (idle_diff / total_diff))
                        result["cpu_usage_percent"] = round(usage, 2)
                        
                _previous_cpu_state[node["name"]] = {
                    "timestamp": current_time,
                    "cpu_total": parsed["cpu_total_secs"],
                    "cpu_idle": parsed["cpu_idle_secs"]
                }
            
            if parsed["mem_total"] > 0:
                used_mem = parsed["mem_total"] - parsed["mem_avail"]
                result["mem_usage_percent"] = round((used_mem / parsed["mem_total"]) * 100, 2)
                
            if parsed["disk_size"] > 0:
                used_disk = parsed["disk_size"] - parsed["disk_free"]
                result["disk_usage_percent"] = round((used_disk / parsed["disk_size"]) * 100, 2)
                
            result["net_in_bytes_sec"] = int(parsed["net_in"])
            result["net_out_bytes_sec"] = int(parsed["net_out"])
        else:
            logger.warning(f"Node {node['name']} returned HTTP {resp.status_code}")
    except requests.exceptions.Timeout:
        result["scrape_duration_ms"] = int((time.time() - start_time) * 1000)
        result["status"] = "TIMEOUT"
        logger.warning(f"Node {node['name']} scrape timed out")
    except requests.exceptions.ConnectionError as e:
        result["scrape_duration_ms"] = int((time.time() - start_time) * 1000)
        result["status"] = "OFFLINE"
        logger.warning(f"Node {node['name']} connection error: {e}")
    except Exception as e:
        result["scrape_duration_ms"] = int((time.time() - start_time) * 1000)
        result["status"] = "ERROR"
        logger.error(f"Node {node['name']} scrape error: {e}")
        
    return result


def scrape_all_nodes() -> list:
    """Concurrently scrapes all nodes."""
    results = []
    with ThreadPoolExecutor(max_workers=len(TARGET_NODES)) as executor:
        futures = {executor.submit(scrape_single_node, node): node for node in TARGET_NODES}
        for future in as_completed(futures):
            node = futures[future]
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Unexpected error scraping node {node['name']}: {e}")
    return results


def insert_telemetry_batch(records: list):
    """Inserts scraped telemetry batch into MySQL using connection pool."""
    if not records:
        return
        
    insert_sql = """
    INSERT INTO vm_telemetry (
        node_name, host_ip, region, cpu_usage_percent,
        mem_total_bytes, mem_available_bytes, mem_usage_percent,
        disk_usage_percent, net_in_bytes_sec, net_out_bytes_sec,
        scrape_duration_ms, status
    ) VALUES (
        %(node_name)s, %(host_ip)s, %(region)s, %(cpu_usage_percent)s,
        %(mem_total_bytes)s, %(mem_available_bytes)s, %(mem_usage_percent)s,
        %(disk_usage_percent)s, %(net_in_bytes_sec)s, %(net_out_bytes_sec)s,
        %(scrape_duration_ms)s, %(status)s
    );
    """
    try:
        pool = get_db_pool()
        conn = pool.connection()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(insert_sql, records)
                conn.commit()
            logger.info(f"Ingested {len(records)} records into MySQL")
        finally:
            conn.close()
    except Exception as err:
        logger.error(f"MySQL insert error: {err}")


def run_pipeline():
    """Single run of scrape and insert."""
    logger.info(f"Scraping {len(TARGET_NODES)} nodes...")
    records = scrape_all_nodes()
    online_count = sum(1 for r in records if r["status"] == "ONLINE")
    logger.info(f"Scrape complete: {online_count}/{len(records)} nodes ONLINE")
    insert_telemetry_batch(records)


def main():
    parser = argparse.ArgumentParser(description="Nexus Telemetry Ingestion Service")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()
    
    if args.once:
        run_pipeline()
    else:
        logger.info(f"Starting ingestion daemon (interval: {SCRAPE_INTERVAL}s)")
        while True:
            try:
                run_pipeline()
            except Exception as e:
                logger.error(f"Pipeline error: {e}")
            time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
