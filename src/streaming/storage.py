from __future__ import annotations

import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import astuple, dataclass
from pathlib import Path

from config import DB_PATH

logger = logging.getLogger(__name__)


@dataclass
class HistoryRecord:
    timestamp: str
    well: str
    pump_type: str
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
        conn.close()


def insert_history_record(conn: sqlite3.Connection, record: HistoryRecord) -> None:
    conn.execute(_INSERT_SQL, astuple(record))
    conn.commit()
    logger.debug(
        "history: well=%s ts=%s cluster=%s deviation=%.4f",
        record.well,
        record.timestamp,
        record.cluster,
        record.deviation,
    )


def fetch_history(
    conn: sqlite3.Connection,
    well: str,
    limit: int = 1000,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT timestamp, cluster, deviation, pump_type,
               us_center, us_periph, gas_center, gas_periph, temp,
               water_center, water_periph, gas_integral, water_integral
        FROM history
        WHERE well = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (well, limit),
    ).fetchall()
