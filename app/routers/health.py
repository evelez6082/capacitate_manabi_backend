from fastapi import APIRouter, Depends
from psycopg import Connection

from app.config import get_settings
from app.db import fetch_one, get_connection

router = APIRouter(tags=["salud"])


@router.get("/health")
def health(conn: Connection = Depends(get_connection)) -> dict:
    db = fetch_one(conn, "SELECT now() AS server_time")
    return {
        "status": "ok",
        "app": get_settings().app_name,
        "database": "ok" if db else "unknown",
        "server_time": db["server_time"] if db else None,
    }
