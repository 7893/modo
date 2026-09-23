"""Unit tests for AutoML training-table maintenance helpers."""

import os
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from train_latency_model import _validate_identifier, cleanup_training_backups
import api_maintenance


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
