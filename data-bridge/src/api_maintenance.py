"""Scheduled model retraining and telemetry retention tasks."""
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime

from fastapi import HTTPException

from api_database import get_db_connection

logger = logging.getLogger(__name__)
_retrain_last_run = ""


def run_weekly_retrain_if_due(now: datetime | None = None) -> bool:
    """Run one due retraining attempt and return whether it succeeded."""
    global _retrain_last_run
    now = now or datetime.now()
    week_key = now.strftime("%Y-%W")
    if now.weekday() != 6 or now.hour < 3 or _retrain_last_run == week_key:
        return False

    logger.info("Weekly retrain triggered (Sunday 3AM)")
    script_path = os.path.join(os.path.dirname(__file__), "train_latency_model.py")
    command = [sys.executable, script_path]

    ionice = shutil.which("ionice")
    if ionice:
        command = [ionice, "-c", "3", *command]

    nice = shutil.which("nice")
    if nice:
        command = [nice, "-n", "19", *command]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=os.path.dirname(script_path),
    )
    if result.returncode == 0:
        logger.info("Weekly retrain completed successfully")
        _retrain_last_run = week_key
        return True

    logger.error(
        "Weekly retrain failed and will retry next hour: %s",
        result.stderr[:500],
    )
    return False


def weekly_retrain_loop() -> None:
    """Background thread: run weekly training with same-day hourly retries."""
    while True:
        try:
            run_weekly_retrain_if_due()
        except Exception as e:
            logger.error(f"Weekly retrain error: {e}")
        time.sleep(3600)  # Check every hour
def prune_old_data():
    """Prune telemetry data older than 60 days in one transaction."""
    try:
        with get_db_connection() as conn:
            conn.begin()
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM vm_telemetry WHERE recorded_at < NOW() - INTERVAL 60 DAY")
                    deleted_raw = cur.rowcount
                    cur.execute("DELETE FROM vm_telemetry_archive WHERE recorded_at < NOW() - INTERVAL 60 DAY")
                    deleted_archive = cur.rowcount
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {
            "status": "success",
            "deleted_raw": deleted_raw,
            "deleted_archive": deleted_archive
        }
    except Exception as e:
        logger.error(f"Error during pruning: {e}")
        raise HTTPException(status_code=500, detail=str(e))
