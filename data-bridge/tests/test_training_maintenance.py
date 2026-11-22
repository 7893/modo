"""Unit tests for AutoML training-table maintenance helpers."""

import os
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from train_latency_model import (
    _validate_identifier,
    _validate_model_handle,
    cleanup_training_backups,
    train_automl_model,
    verify_predictions,
)
import api_maintenance
import db_setup
import train_latency_model


class FakeCursor:
    def __init__(self, table_names):
        self.table_names = table_names
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)

    def fetchall(self):
        return [{"table": name} for name in self.table_names]


def test_cleanup_training_backups_keeps_newest_snapshots():
    cursor = FakeCursor([
        "latency_forecast_train_backup_100",
        "latency_forecast_train_backup_300",
        "latency_forecast_train_backup_200",
        "unrelated_table",
    ])

    cleanup_training_backups(cursor, keep_last=2)

    assert cursor.statements == [
        "SHOW TABLES LIKE 'latency_forecast_train_backup_%'",
        "DROP TABLE IF EXISTS `latency_forecast_train_backup_100`",
    ]


@pytest.mark.parametrize("value", ["modo-db", "modo.db", "modo db", "1modo", ""])
def test_validate_identifier_rejects_unsafe_names(value):
    with pytest.raises(RuntimeError):
        _validate_identifier(value, "TEST_SETTING")


def test_weekly_retrain_uses_current_python_without_linux_helpers(monkeypatch):
    commands = []
    monkeypatch.setattr(api_maintenance, "_retrain_last_run", "")
    monkeypatch.setattr(api_maintenance.shutil, "which", lambda _name: None)
    monkeypatch.setattr(api_maintenance.sys, "executable", "/test/python")
    monkeypatch.setattr(
        api_maintenance.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=0, stderr=""),
    )

    succeeded = api_maintenance.run_weekly_retrain_if_due(datetime(2026, 9, 27, 3))

    assert succeeded is True
    assert commands == [["/test/python", os.path.join(os.path.dirname(api_maintenance.__file__), "train_latency_model.py")]]
    assert api_maintenance._retrain_last_run == "2026-38"


def test_failed_weekly_retrain_remains_due(monkeypatch):
    monkeypatch.setattr(api_maintenance, "_retrain_last_run", "")
    monkeypatch.setattr(api_maintenance.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        api_maintenance.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stderr="failed"),
    )

    succeeded = api_maintenance.run_weekly_retrain_if_due(datetime(2026, 9, 27, 4))

    assert succeeded is False
    assert api_maintenance._retrain_last_run == ""


@pytest.mark.parametrize("value", ["", "bad handle", "x'; DROP TABLE t; --", "bad/handle"])
def test_validate_model_handle_rejects_unsafe_names(value):
    with pytest.raises(RuntimeError):
        _validate_model_handle(value)


def test_train_automl_skips_when_rapid_ml_off_and_closes_after_cursor(monkeypatch):
    """train_automl_model must exit cursor context before closing connection."""
    events = []

    class FakeMLCursor:
        def __enter__(self):
            events.append("cursor_enter")
            return self

        def __exit__(self, *_exc):
            events.append("cursor_exit")

        def execute(self, _sql, _params=None):
            pass

        def fetchone(self):
            return {"Variable_name": "rapid_ml_status", "Value": "OFF"}

    class FakeConn:
        def cursor(self):
            return FakeMLCursor()

        def close(self):
            events.append("conn_close")

    monkeypatch.setattr(train_latency_model, "MYSQL_DATABASE", "modo_db")
    monkeypatch.setattr(train_latency_model, "MYSQL_ML_SCHEMA", "ML_SCHEMA_modo")
    monkeypatch.setattr(train_latency_model, "get_conn", lambda: FakeConn())

    assert train_automl_model() is None
    assert events == ["cursor_enter", "cursor_exit", "conn_close"]


def test_verify_predictions_skips_none_prediction(monkeypatch):
    """verify_predictions must skip null predictions instead of crashing in float()."""
    closed = []

    class FakeVerifyCursor:
        def __init__(self):
            self.step = 0

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            pass

        def execute(self, _sql, _params=None):
            self.step += 1

        def fetchone(self):
            if self.step == 1:
                return {"cnt": 200}
            return {"pred": {"Prediction": None}}

        def fetchall(self):
            return [{"node_name": "node-a", "real_avg_ms": 42.0}]

    class FakeConn:
        def cursor(self):
            return FakeVerifyCursor()

        def close(self):
            closed.append(True)

    monkeypatch.setattr(train_latency_model, "get_conn", lambda: FakeConn())

    assert verify_predictions("MODO_LATENCY_FORECAST") == {}
    assert closed == [True]


def test_db_setup_rejects_database_name_with_trailing_newline(monkeypatch):
    """db_setup must use fullmatch so trailing newlines are rejected."""
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_USER", "modo_test")
    monkeypatch.setenv("MYSQL_PASSWORD", "test-pass")
    monkeypatch.setenv("MYSQL_DATABASE", "modo_db\n")

    with pytest.raises(ValueError):
        db_setup.get_db_config()
