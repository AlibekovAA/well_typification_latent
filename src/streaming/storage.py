from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from config import DB_BUSY_TIMEOUT_MS, DB_LOCK_RETRY_ATTEMPTS, DB_LOCK_RETRY_DELAY_SECONDS, DB_PATH, PumpType

logger = logging.getLogger(__name__)


@dataclass
class HistoryRecord:
    timestamp: str
    well: str
    pump_type: PumpType
    cluster: int
    deviation: float
    us_center: float
    us_periph: float
    gas_center: float
    gas_periph: float
    temp: float
    water_center: float
    water_periph: float
    gas_integral: float
    water_integral: float


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    well            TEXT NOT NULL,
    pump_type       TEXT NOT NULL,
    cluster         INTEGER NOT NULL,
    deviation       REAL NOT NULL,
    us_center       REAL,
    us_periph       REAL,
    gas_center      REAL,
    gas_periph      REAL,
    temp            REAL,
    water_center    REAL,
    water_periph    REAL,
    gas_integral    REAL,
    water_integral  REAL
)
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_history_well_ts ON history (well, timestamp)
"""

_INSERT_SQL = """
INSERT INTO history (
    timestamp, well, pump_type, cluster, deviation,
    us_center, us_periph, gas_center, gas_periph, temp,
    water_center, water_periph, gas_integral, water_integral
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
    conn.row_factory = sqlite3.Row


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _apply_pragmas(conn)
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_INDEX_SQL)
        conn.commit()
    logger.info("БД инициализирована: %s", db_path)


@contextmanager
def get_connection(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    _apply_pragmas(conn)
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()


def _record_values(record: HistoryRecord) -> tuple[object, ...]:
    return (
        record.timestamp,
        record.well,
        record.pump_type,
        record.cluster,
        record.deviation,
        record.us_center,
        record.us_periph,
        record.gas_center,
        record.gas_periph,
        record.temp,
        record.water_center,
        record.water_periph,
        record.gas_integral,
        record.water_integral,
    )


def insert_history_record(conn: sqlite3.Connection, record: HistoryRecord) -> None:
    insert_history_records(conn, [record])


def insert_history_records(conn: sqlite3.Connection, records: list[HistoryRecord]) -> None:
    if not records:
        return
    values = [_record_values(record) for record in records]
    for attempt in range(1, DB_LOCK_RETRY_ATTEMPTS + 1):
        try:
            conn.executemany(_INSERT_SQL, values)
            conn.commit()
            logger.debug("history: batch insert well=%s count=%d", records[0].well, len(records))
            return
        except sqlite3.OperationalError as exc:
            is_locked = "database is locked" in str(exc).lower()
            if not is_locked or attempt >= DB_LOCK_RETRY_ATTEMPTS:
                raise
            sleep_seconds = DB_LOCK_RETRY_DELAY_SECONDS * attempt
            logger.warning(
                "БД занята, повтор записи батча через %.2f с (attempt=%d/%d)",
                sleep_seconds,
                attempt,
                DB_LOCK_RETRY_ATTEMPTS,
            )
            time.sleep(sleep_seconds)


def fetch_history(
    conn: sqlite3.Connection,
    well: str,
    *,
    limit: int = 1000,
    since: str | None = None,
) -> list[sqlite3.Row]:
    sql = """
        SELECT timestamp, cluster, deviation, pump_type,
               us_center, us_periph, gas_center, gas_periph, temp,
               water_center, water_periph, gas_integral, water_integral
        FROM history
        WHERE well = ?
    """
    params: list[object] = [well]
    if since is not None:
        sql += " AND timestamp >= ?"
        params.append(since)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def fetch_history_since(
    conn: sqlite3.Connection,
    well: str,
    *,
    since_exclusive: str,
    limit: int = 1000,
) -> list[sqlite3.Row]:
    sql = """
        SELECT timestamp, cluster, deviation, pump_type,
               us_center, us_periph, gas_center, gas_periph, temp,
               water_center, water_periph, gas_integral, water_integral
        FROM history
        WHERE well = ? AND timestamp > ?
        ORDER BY timestamp ASC
        LIMIT ?
    """
    params: tuple[object, ...] = (well, since_exclusive, limit)
    return conn.execute(sql, params).fetchall()
