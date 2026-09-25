"""Explicit public schemas: internal node configuration must not become API data."""
NODE_FIELDS = frozenset({"name", "region", "provider", "lat", "lng"})
METRIC_FIELDS = frozenset({
    "id", "node_name", "region", "cpu_usage_percent", "mem_usage_percent",
    "disk_usage_percent", "net_in_bytes_sec", "net_out_bytes_sec",
    "scrape_duration_ms", "status", "recorded_at", "health_score", "cpu_score",
    "mem_score", "provider", "lat", "lng",
})


def public_node(node):
    return {key: value for key, value in node.items() if key in NODE_FIELDS}


def public_metric(row):
    return {key: value for key, value in row.items() if key in METRIC_FIELDS}
