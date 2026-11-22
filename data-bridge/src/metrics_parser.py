"""Pure Prometheus text parsing helpers for MODO telemetry ingestion."""
import math

_IGNORED_ROOT_FS_MARKERS = (
    'device="rootfs"',
    'fstype="rootfs"',
    'fstype="tmpfs"',
    'fstype="devtmpfs"',
    'fstype="devfs"',
)


def _parse_metric_value(line: str) -> float | None:
    """Extract a finite numeric sample value from a Prometheus text line."""
    brace_end = line.rfind("}")
    if brace_end != -1:
        parts = line[brace_end + 1 :].split()
        token = parts[0] if parts else None
    else:
        parts = line.split()
        token = parts[1] if len(parts) >= 2 else None
    if token is None:
        return None
    try:
        value = float(token)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _is_root_filesystem_line(line: str, metric_prefix: str) -> bool:
    """Match Linux (/dev/*) and FreeBSD (ZFS/UFS) root mounts while skipping pseudo mounts."""
    if not line.startswith(metric_prefix) or 'mountpoint="/"' not in line:
        return False
    return not any(marker in line for marker in _IGNORED_ROOT_FS_MARKERS)


def _is_loopback_device(line: str) -> bool:
    """Return True for Linux (lo) and FreeBSD (lo0) loopback interfaces."""
    return 'device="lo"' in line or 'device="lo0"' in line


def parse_prometheus_metrics(raw_text: str) -> dict:
    """Extract the node_exporter metrics used by the ingestion pipeline."""
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

    bsd_mem_avail = 0.0

    for line in raw_text.splitlines():
        if line.startswith("#") or not line.strip():
            continue

        if line.startswith("node_cpu_seconds_total{"):
            value = _parse_metric_value(line)
            if value is None:
                continue
            metrics["cpu_total_secs"] += value
            if 'mode="idle"' in line:
                metrics["cpu_idle_secs"] += value
        elif line.startswith("node_memory_MemTotal_bytes "):
            value = _parse_metric_value(line)
            if value is not None:
                metrics["mem_total"] = value
        elif line.startswith("node_memory_MemAvailable_bytes "):
            value = _parse_metric_value(line)
            if value is not None:
                metrics["mem_avail"] = value
        elif line.startswith("node_memory_size_bytes "):
            value = _parse_metric_value(line)
            if value is not None and metrics["mem_total"] == 0:
                metrics["mem_total"] = value
        elif (
            line.startswith("node_memory_free_bytes ")
            or line.startswith("node_memory_inactive_bytes ")
            or line.startswith("node_memory_cache_bytes ")
        ):
            value = _parse_metric_value(line)
            if value is not None:
                bsd_mem_avail += value
        elif _is_root_filesystem_line(line, "node_filesystem_size_bytes{"):
            value = _parse_metric_value(line)
            if value is not None:
                metrics["disk_size"] = value
        elif _is_root_filesystem_line(line, "node_filesystem_avail_bytes{"):
            value = _parse_metric_value(line)
            if value is not None:
                metrics["disk_free"] = value
        elif line.startswith("node_network_receive_bytes_total{device="):
            if not _is_loopback_device(line):
                value = _parse_metric_value(line)
                if value is not None:
                    metrics["net_in"] += value
        elif line.startswith("node_network_transmit_bytes_total{device="):
            if not _is_loopback_device(line):
                value = _parse_metric_value(line)
                if value is not None:
                    metrics["net_out"] += value

    if metrics["mem_avail"] == 0 and bsd_mem_avail > 0:
        metrics["mem_avail"] = min(metrics["mem_total"], bsd_mem_avail)

    return metrics
