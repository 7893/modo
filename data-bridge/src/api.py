"""
MODO Data Bridge - API Gateway
Provides node metadata and health endpoints for Cloudflare Workers & Frontend UI.
"""
import os
import json
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv()

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

ALLOWED_ORIGINS = [
    "https://modo.53.workers.dev",
    "http://localhost:8787",
]

_nodes_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "nodes.json")


def load_target_nodes() -> list:
    try:
        with open(_nodes_config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("nodes.json not found, using empty list")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in nodes.json: {e}")
        return []


TARGET_NODES = load_target_nodes()

app = FastAPI(
    title="MODO Core API Gateway",
    description="Internal API for Cloudflare Tunnel & Worker integration",
    version="2.0.0"
)

_rate_limit_store: dict = defaultdict(list)


def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if t > window_start]
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    _rate_limit_store[client_ip].append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = (
        request.headers.get("CF-Connecting-IP") or
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        request.client.host or "unknown"
    )
    if not check_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"error": "Too many requests"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Internal-Secret"],
)


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "MODO Data Bridge Gateway",
        "timestamp": datetime.now().isoformat(),
        "tunnel_endpoint": "api-modo.8n8m.cfd"
    }


@app.get("/api/nodes/summary")
def get_nodes_summary():
    return {
        "total_nodes": len(TARGET_NODES),
        "nodes": TARGET_NODES,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
