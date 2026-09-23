"""Bounded in-memory rate limiting for the private API gateway."""
import os
import time
from collections import defaultdict

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX_CLIENTS = max(1, int(os.getenv("RATE_LIMIT_MAX_CLIENTS", "10000")))
RATE_LIMIT_SWEEP_INTERVAL = max(1, int(os.getenv("RATE_LIMIT_SWEEP_INTERVAL", "60")))

rate_limit_store: dict[str, list[float]] = defaultdict(list)
rate_limit_last_sweep = 0.0


def sweep_rate_limit_store(now: float) -> None:
    """Remove expired client buckets and enforce a hard memory bound."""
    global rate_limit_last_sweep
    window_start = now - RATE_LIMIT_WINDOW
    for client_ip, timestamps in list(rate_limit_store.items()):
        recent = [timestamp for timestamp in timestamps if timestamp > window_start]
        if recent:
            rate_limit_store[client_ip] = recent
        else:
            rate_limit_store.pop(client_ip, None)

    excess = len(rate_limit_store) - RATE_LIMIT_MAX_CLIENTS
    if excess > 0:
        oldest_clients = sorted(
            rate_limit_store,
            key=lambda client_ip: rate_limit_store[client_ip][-1],
        )[:excess]
        for client_ip in oldest_clients:
            rate_limit_store.pop(client_ip, None)
    rate_limit_last_sweep = now


def check_rate_limit(client_ip: str) -> bool:
    """Record one request and return whether the client remains under quota."""
    global rate_limit_last_sweep
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    capacity_reached = client_ip not in rate_limit_store and len(rate_limit_store) >= RATE_LIMIT_MAX_CLIENTS
    if now - rate_limit_last_sweep >= RATE_LIMIT_SWEEP_INTERVAL or capacity_reached:
        sweep_rate_limit_store(now)

    if client_ip not in rate_limit_store and len(rate_limit_store) >= RATE_LIMIT_MAX_CLIENTS:
        oldest_client = min(rate_limit_store, key=lambda ip: rate_limit_store[ip][-1])
        rate_limit_store.pop(oldest_client, None)

    timestamps = [
        timestamp for timestamp in rate_limit_store.get(client_ip, [])
        if timestamp > window_start
    ]
    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        rate_limit_store[client_ip] = timestamps
        return False

    timestamps.append(now)
    rate_limit_store[client_ip] = timestamps
    return True
