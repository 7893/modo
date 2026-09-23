"""Environment and node configuration shared by API modules."""
import json
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv()

INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET")
SERVICE_NODE_NAME = os.getenv("SERVICE_NODE_NAME", "modo-api")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:8787").split(",")
    if origin.strip()
]

_NODES_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "nodes.json")


def load_target_nodes() -> list:
    """Load target nodes from nodes.json without failing API import."""
    try:
        with open(_NODES_CONFIG_PATH, "r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        logger.warning("nodes.json not found, using empty list")
        return []
    except json.JSONDecodeError as error:
        logger.error("Invalid JSON in nodes.json: %s", error)
        return []


TARGET_NODES = load_target_nodes()
