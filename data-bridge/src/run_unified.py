#!/usr/bin/env python3
"""Supervisor for MODO API Gateway (Data Bridge)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [modo-supervisor] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("modo-supervisor")

SRC_DIR = Path(__file__).resolve().parent


def main() -> int:
    logger.info("Starting MODO supervisor from %s", SRC_DIR)

    base_env = os.environ.copy()
    base_env["PYTHONUNBUFFERED"] = "1"
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    base_env["PYTHONPATH"] = str(SRC_DIR)

    api_cmd = [
        sys.executable, "-m", "uvicorn", "api:app",
        "--host", "127.0.0.1", "--port", "8000",
    ]

    proc = None
    shutting_down = False

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        logger.info("Received %s, shutting down...", signal.Signals(signum).name)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    proc = subprocess.Popen(api_cmd, cwd=str(SRC_DIR), env=base_env)
    logger.info("MODO API started (port 8000)")

    while not shutting_down:
        time.sleep(1)
        if proc.poll() is not None:
            code = proc.poll()
            logger.error("API exited with code %s. Restarting in 3s...", code)
            time.sleep(3)
            if not shutting_down:
                proc = subprocess.Popen(api_cmd, cwd=str(SRC_DIR), env=base_env)

    if proc and proc.poll() is None:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    logger.info("MODO supervisor stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
