"""
Unit tests for the side-effect-free Prometheus metric parser.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from metrics_parser import parse_prometheus_metrics

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


def test_parse_freebsd_memory_metrics():
    """Verify FreeBSD node_exporter memory fallback metrics are parsed accurately."""
    bsd_metrics = """
node_memory_size_bytes 2147483648
node_memory_free_bytes 536870912
node_memory_inactive_bytes 268435456
node_memory_cache_bytes 134217728
"""
    metrics = parse_prometheus_metrics(bsd_metrics)
    assert metrics["mem_total"] == 2147483648
    assert metrics["mem_avail"] == 536870912 + 268435456 + 134217728


def test_parse_freebsd_zfs_root_and_lo0_exclusion():
    """Verify FreeBSD ZFS root mounts are detected and lo0 loopback traffic is ignored."""
    bsd_metrics = """
node_filesystem_size_bytes{device="tmpfs",fstype="tmpfs",mountpoint="/"} 1000
node_filesystem_size_bytes{device="zroot/ROOT/default",fstype="zfs",mountpoint="/"} 53687091200
node_filesystem_avail_bytes{device="zroot/ROOT/default",fstype="zfs",mountpoint="/"} 26843545600
node_filesystem_avail_bytes{device="rootfs",fstype="rootfs",mountpoint="/"} 500
node_network_receive_bytes_total{device="lo0"} 99999999
node_network_receive_bytes_total{device="vtnet0"} 4200
node_network_transmit_bytes_total{device="lo0"} 88888888
node_network_transmit_bytes_total{device="vtnet0"} 8400
"""
    metrics = parse_prometheus_metrics(bsd_metrics)
    assert metrics["disk_size"] == 53687091200
    assert metrics["disk_free"] == 26843545600
    assert metrics["net_in"] == 4200
    assert metrics["net_out"] == 8400


def test_parse_malformed_and_non_finite_values():
    """Malformed, missing, NaN, and Inf metric lines must be skipped safely."""
    bad_metrics = """
node_cpu_seconds_total{cpu="0",mode="idle"} NaN
node_cpu_seconds_total{cpu="0",mode="user"} +Inf
node_cpu_seconds_total{cpu="0",mode="system"}
node_memory_MemTotal_bytes not_a_number
node_memory_MemAvailable_bytes -Inf
node_filesystem_size_bytes{device="/dev/sda1",mountpoint="/"} NaN
node_network_receive_bytes_total{device="eth0"} bad
node_network_transmit_bytes_total{device="eth0"} 1234
"""
    metrics = parse_prometheus_metrics(bad_metrics)
    assert metrics["cpu_total_secs"] == 0.0
    assert metrics["cpu_idle_secs"] == 0.0
    assert metrics["mem_total"] == 0
    assert metrics["mem_avail"] == 0
    assert metrics["disk_size"] == 0
    assert metrics["net_in"] == 0
    assert metrics["net_out"] == 1234
