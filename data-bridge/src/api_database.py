"""Lazy MySQL connection pool for API request handlers."""
import logging
import os
from contextlib import contextmanager
from typing import Optional

import pymysql
from dbutils.pooled_db import PooledDB

logger = logging.getLogger(__name__)
_db_pool: Optional[PooledDB] = None


def get_db_pool() -> PooledDB:
    """Get or create the process-local database connection pool."""
    global _db_pool
    if _db_pool is not None:
        return _db_pool

    host = os.getenv("MYSQL_HOST")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER")
    password = os.getenv("MYSQL_PASSWORD")
    database = os.getenv("MYSQL_DATABASE", "modo_db")
    if not all([host, user, password]):
        raise RuntimeError(
            "Missing required environment variables: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD"
        )

    _db_pool = PooledDB(
        creator=pymysql,
        maxconnections=10,
        mincached=2,
        maxcached=5,
        blocking=True,
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5,
        read_timeout=8,
        write_timeout=8,
        autocommit=True,
    )
    logger.info("Database connection pool initialized (host=%s, database=%s)", host, database)
    return _db_pool


@contextmanager
def get_db_connection():
    """Yield a pooled database connection and always return it to the pool."""
    connection = get_db_pool().connection()
    try:
        yield connection
    finally:
        connection.close()
