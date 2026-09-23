"""Pure Prometheus text parsing helpers for MODO telemetry ingestion."""


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

    for line in raw_text.splitlines():
        if line.startswith("#") or not line.strip():
            continue

        if line.startswith("node_cpu_seconds_total{"):
            value = float(line.split()[1])
            metrics["cpu_total_secs"] += value
            if 'mode="idle"' in line:
                metrics["cpu_idle_secs"] += value
        elif line.startswith("node_memory_MemTotal_bytes "):
            metrics["mem_total"] = float(line.split()[1])
        elif line.startswith("node_memory_MemAvailable_bytes "):
            metrics["mem_avail"] = float(line.split()[1])
        elif 'node_filesystem_size_bytes{device="/dev/' in line and 'mountpoint="/"' in line:
            metrics["disk_size"] = float(line.split()[1])
        elif 'node_filesystem_avail_bytes{device="/dev/' in line and 'mountpoint="/"' in line:
            metrics["disk_free"] = float(line.split()[1])
        elif line.startswith("node_network_receive_bytes_total{device="):
            if 'device="lo"' not in line:
                metrics["net_in"] += float(line.split()[1])
        elif line.startswith("node_network_transmit_bytes_total{device="):
            if 'device="lo"' not in line:
                metrics["net_out"] += float(line.split()[1])

    return metrics
