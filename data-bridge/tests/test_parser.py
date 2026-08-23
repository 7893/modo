"""
Unit tests for Prometheus metric parser in ingest.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ingest import parse_prometheus_metrics

MOCK_PROMETHEUS_METRICS = """
# HELP node_memory_MemTotal_bytes Memory information field MemTotal_bytes.
# TYPE node_memory_MemTotal_bytes gauge
node_memory_MemTotal_bytes 16777216000
# HELP node_memory_MemAvailable_bytes Memory information field MemAvailable_bytes.
# TYPE node_memory_MemAvailable_bytes gauge
node_memory_MemAvailable_bytes 8388608000
# HELP node_filesystem_size_bytes Filesystem size in bytes.
# TYPE node_filesystem_size_bytes gauge
node_filesystem_size_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 107374182400
# HELP node_filesystem_avail_bytes Filesystem space available to non-root users in bytes.
# TYPE node_filesystem_avail_bytes gauge
node_filesystem_avail_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 53687091200
# HELP node_network_receive_bytes_total Network device statistic receive_bytes.
# TYPE node_network_receive_bytes_total counter
node_network_receive_bytes_total{device="eth0"} 123456789
node_network_receive_bytes_total{device="lo"} 999999
# HELP node_network_transmit_bytes_total Network device statistic transmit_bytes.
# TYPE node_network_transmit_bytes_total counter
node_network_transmit_bytes_total{device="eth0"} 987654321
node_network_transmit_bytes_total{device="lo"} 999999
"""

def test_parse_valid_prometheus_metrics():
    """Verify accurate extraction of memory, disk, and network stats."""
    metrics = parse_prometheus_metrics(MOCK_PROMETHEUS_METRICS)
    
    # Check memory
    assert metrics["mem_total"] == 16777216000
    assert metrics["mem_avail"] == 8388608000
    
    # Check root filesystem
    assert metrics["disk_size"] == 107374182400
    assert metrics["disk_free"] == 53687091200
    
    # Check network ignoring loopback
    assert metrics["net_in"] == 123456789
    assert metrics["net_out"] == 987654321

def test_parse_empty_metrics():
    """Verify graceful fallback with empty or malformed input."""
    metrics = parse_prometheus_metrics("")
    assert metrics["mem_total"] == 0
    assert metrics["mem_avail"] == 0
    assert metrics["disk_size"] == 0
    assert metrics["disk_free"] == 0
    assert metrics["net_in"] == 0
    assert metrics["net_out"] == 0

def test_parse_corrupt_metrics():
    """Verify that comment lines and invalid text don't throw unhandled exceptions."""
    corrupt_text = "# Just some random comments\ninvalid_line_without_numbers\n"
    metrics = parse_prometheus_metrics(corrupt_text)
    assert isinstance(metrics, dict)
    assert metrics["mem_total"] == 0
