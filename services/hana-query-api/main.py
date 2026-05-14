"""
HANA Query API
通用 SAP HANA SQL 查询服务，传入 SQL 返回 JSON
"""

import os
import logging
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from hdbcli import dbapi
import uvicorn

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

HANA_HOST = os.getenv("HANA_HOST", "10.142.1.38")
HANA_PORT = int(os.getenv("HANA_PORT", "30041"))
HANA_DATABASE = os.getenv("HANA_DATABASE", "S4P")
HANA_USER = os.getenv("HANA_USER", "FR_USER")
HANA_PASSWORD = os.getenv("HANA_PASSWORD", "")
HANA_QUERY_TIMEOUT = int(os.getenv("HANA_QUERY_TIMEOUT", "60"))
HANA_MAX_ROWS = int(os.getenv("HANA_MAX_ROWS", "10000"))
API_PORT = int(os.getenv("HANA_API_PORT", "8766"))

app = FastAPI(
    title="HANA Query API",
    version="1.0.0",
    description="通用 SAP HANA SQL 查询服务",
)


@contextmanager
def get_connection():
    conn = None
    try:
        conn = dbapi.connect(
            address=HANA_HOST,
            port=HANA_PORT,
            user=HANA_USER,
            password=HANA_PASSWORD,
            database=HANA_DATABASE,
        )
        yield conn
    finally:
        if conn:
            conn.close()


class QueryRequest(BaseModel):
    sql: str = Field(..., description="HANA SQL 查询语句")
    max_rows: Optional[int] = Field(
        default=None,
        description=f"最大返回行数，默认 {HANA_MAX_ROWS}",
    )


class QueryResponse(BaseModel):
    data: List[Dict[str, Any]]
    total: int
    columns: List[str]


class HealthResponse(BaseModel):
    status: str
    hana_host: str
    hana_port: int
    hana_database: str
    hana_connected: bool


@app.get("/health", response_model=HealthResponse)
def health():
    connected = False
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUMMY")
            cursor.fetchone()
            cursor.close()
            connected = True
    except Exception as e:
        logger.warning(f"HANA health check failed: {e}")

    return HealthResponse(
        status="ok" if connected else "degraded",
        hana_host=HANA_HOST,
        hana_port=HANA_PORT,
        hana_database=HANA_DATABASE,
        hana_connected=connected,
    )


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    max_rows = req.max_rows or HANA_MAX_ROWS
    if max_rows > HANA_MAX_ROWS:
        max_rows = HANA_MAX_ROWS

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(req.sql)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchmany(max_rows)
                data = [dict(zip(columns, row)) for row in rows]
                return QueryResponse(
                    data=data,
                    total=len(data),
                    columns=columns,
                )
            finally:
                cursor.close()
    except dbapi.Error as e:
        logger.error(f"HANA query error: {e}")
        raise HTTPException(status_code=400, detail=f"HANA query error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
