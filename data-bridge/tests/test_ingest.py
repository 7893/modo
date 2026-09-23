"""Unit tests for ingestion startup and CPU counter warm-up."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import ingest


class FakeResponse:
    status_code = 200

    def __init__(self, text: str):
        self.text = text


def cpu_metrics(idle: int, user: int) -> str:
    return (
        f'node_cpu_seconds_total{{cpu="0",mode="idle"}} {idle}\n'
        f'node_cpu_seconds_total{{cpu="0",mode="user"}} {user}\n'
    )


def test_empty_node_list_skips_thread_pool(monkeypatch):
    monkeypatch.setattr(ingest, "TARGET_NODES", [])
    monkeypatch.setattr(
        ingest,
        "ThreadPoolExecutor",
        lambda **_kwargs: pytest.fail("thread pool must not be created"),
    )

    assert ingest.scrape_all_nodes() == []


def test_second_cpu_sample_uses_warmed_counter(monkeypatch):
    responses = iter([
        FakeResponse(cpu_metrics(idle=80, user=20)),
        FakeResponse(cpu_metrics(idle=85, user=35)),
    ])
    monkeypatch.setattr(ingest.requests, "get", lambda *_args, **_kwargs: next(responses))
    monkeypatch.setattr(ingest, "measure_tcp_rtt", lambda *_args, **_kwargs: 1)
    ingest._previous_cpu_state.clear()
    node = {"name": "test-a", "host": "192.0.2.10", "region": "test"}

    warmup = ingest.scrape_single_node(node)
    persisted = ingest.scrape_single_node(node)

    assert warmup["cpu_usage_percent"] == 0.0
    assert persisted["cpu_usage_percent"] == 75.0


def test_once_mode_warms_before_pipeline(monkeypatch):
    events = []
    test_nodes = [{"name": "test-a", "host": "192.0.2.10", "region": "test"}]
    monkeypatch.setattr(ingest, "load_target_nodes", lambda: test_nodes)
    monkeypatch.setattr(ingest, "scrape_all_nodes", lambda: events.append("warmup"))
    monkeypatch.setattr(ingest, "run_pipeline", lambda: events.append("pipeline"))
    monkeypatch.setattr(ingest.time, "sleep", lambda seconds: events.append(("sleep", seconds)))
    monkeypatch.setattr(ingest, "CPU_WARMUP_SECONDS", 0.25)
    monkeypatch.setattr(sys, "argv", ["ingest.py", "--once"])

    ingest.main()

    assert ingest.TARGET_NODES == test_nodes
    assert events == ["warmup", ("sleep", 0.25), "pipeline"]
