from __future__ import annotations
import pyodbc
from dataclasses import dataclass
from typing import Any, Iterable, Optional
import config

def _conn_str() -> str:
    parts = [
        f"DRIVER={config.DRIVER}",
        f"SERVER={config.SERVER}",
        f"DATABASE={config.DATABASE}",
        "Trusted_Connection=yes",
    ]
    if getattr(config, "TRUST_SERVER_CERT", False):
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts) + ";"

@dataclass
class DB:
    conn: pyodbc.Connection

    @staticmethod
    def connect() -> "DB":
        conn = pyodbc.connect(_conn_str(), autocommit=False)
        conn.timeout = 5
        return DB(conn)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> Optional[pyodbc.Row]:
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        return cur.fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[pyodbc.Row]:
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        return cur.fetchall()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        cur = self.conn.cursor()
        cur.execute(sql, tuple(params))
        return cur.rowcount

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

def init_db_check(db: DB) -> None:
    row = db.fetchone("""
        SELECT COUNT(*) AS cnt
        FROM sys.tables
        WHERE name IN ('UserAccounts','Resources','Bookings','BookingStatuses')
    """)
    if not row or row.cnt < 4:
        raise RuntimeError("В базе нет нужных таблиц.")
