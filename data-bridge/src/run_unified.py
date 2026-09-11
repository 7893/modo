#!/usr/bin/env python3
"""Unified supervisor for MODO services (Data Bridge Gateway + Telemetry Ingestion).

Manages both modo-api (Uvicorn) and modo-ingest (Scraper daemon) as monitored
subprocesses, handling graceful shutdown, signal forwarding, and automatic restarts.
"""

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
    logger.info("Starting MODO unified supervisor from %s", SRC_DIR)

    base_env = os.environ.copy()
    base_env["PYTHONUNBUFFERED"] = "1"
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    base_env["PYTHONPATH"] = str(SRC_DIR)

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    ingest_cmd = [
        sys.executable,
        str(SRC_DIR / "ingest.py"),
    ]

    procs: dict[str, subprocess.Popen | None] = {"api": None, "ingest": None}
    shutting_down = False

    def handle_signal(signum: int, _frame: object) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, propagating to child processes...", sig_name)
        for name, p in procs.items():
            if p and p.poll() is None:
                try:
                    p.terminate()
                except OSError:
                    pass

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    def start_api() -> subprocess.Popen:
        logger.info("Launching MODO API sub-service (port 8000)...")
        return subprocess.Popen(api_cmd, cwd=str(SRC_DIR), env=base_env)

    def start_ingest() -> subprocess.Popen:
        logger.info("Launching MODO Ingest sub-service (global node scraper)...")
        return subprocess.Popen(ingest_cmd, cwd=str(SRC_DIR), env=base_env)

    procs["api"] = start_api()
    procs["ingest"] = start_ingest()

    while not shutting_down:
        time.sleep(1)
        if shutting_down:
            break

        # Check API health
        if procs["api"] and procs["api"].poll() is not None:
            code = procs["api"].poll()
            logger.error("MODO API sub-service exited unexpectedly with code %s. Restarting in 3s...", code)
            time.sleep(3)
            if not shutting_down:
                procs["api"] = start_api()

        # Check Ingest health
        if procs["ingest"] and procs["ingest"].poll() is not None:
            code = procs["ingest"].poll()
            logger.error("MODO Ingest sub-service exited unexpectedly with code %s. Restarting in 5s...", code)
            time.sleep(5)
            if not shutting_down:
                procs["ingest"] = start_ingest()

    # Graceful shutdown wait
    logger.info("Waiting for child processes to terminate...")
    deadline = time.time() + 10
    for name, p in procs.items():
        if p and p.poll() is None:
            remaining = max(0.1, deadline - time.time())
            try:
                p.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                logger.warning("Child process %s did not terminate in time, killing...", name)
                try:
                    p.kill()
                except OSError:
                    pass

    logger.info("MODO unified supervisor stopped cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
