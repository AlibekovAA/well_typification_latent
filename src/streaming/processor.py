from __future__ import annotations

import logging
import sqlite3
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from numpy.typing import NDArray
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from config import (
    DB_BATCH_COMMIT_INTERVAL_SECONDS,
    DB_BATCH_COMMIT_SIZE,
    FEATURE_COLUMNS,
    FEATURE_INDICES,
    PUMP_CONFIGS,
    PumpType,
    WellConfig,
)
from streaming.storage import HistoryRecord, insert_history_records
from utils import EncodableModel, get_device, load_kmeans, load_scaler, load_trained_model

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessorBundle:
    model: EncodableModel
    kmeans: KMeans
    scaler: StandardScaler
    window_size: int
    pump_type: PumpType
    device: torch.device


def load_processor_bundle(pump_type: PumpType) -> ProcessorBundle:
    device = get_device()
    pump_cfg = PUMP_CONFIGS[pump_type]
    model, _ = load_trained_model(pump_type, device=device)
    return ProcessorBundle(
        model=model,
        kmeans=load_kmeans(pump_type),
        scaler=load_scaler(pump_type),
        window_size=pump_cfg.window_size,
        pump_type=pump_type,
        device=device,
    )


class WellProcessor:
    def __init__(
        self,
        well: WellConfig,
        bundle: ProcessorBundle,
        db_conn: sqlite3.Connection,
    ) -> None:
        self._well = well
        self._bundle = bundle
        self._db_conn = db_conn
        self._buffer: deque[NDArray[np.float32]] = deque(maxlen=bundle.window_size)
        self._lines_seen: int = 0
        self._pending_records: list[HistoryRecord] = []
        self._last_commit_monotonic: float = time.monotonic()
        self._scaler_feature_names: tuple[str, ...] | None = None
        feature_names = getattr(bundle.scaler, "feature_names_in_", None)
        if feature_names is not None:
            self._scaler_feature_names = tuple(str(name) for name in feature_names)

    @staticmethod
    def _parse_line(line: str) -> tuple[str, NDArray[np.float32]]:
        parts = line.strip().split("\t")
        if len(parts) < 12:
            raise ValueError(f"Неверный формат строки: {line!r}")
        timestamp = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y.%m.%d %H:%M:%S").isoformat(sep=" ")
        features = np.array(
            [float(parts[i]) for i in FEATURE_INDICES],
            dtype=np.float32,
        )
        return timestamp, features

    def _flush_if_needed(self, *, force: bool = False) -> None:
        elapsed = time.monotonic() - self._last_commit_monotonic
        if not force and len(self._pending_records) < DB_BATCH_COMMIT_SIZE and elapsed < DB_BATCH_COMMIT_INTERVAL_SECONDS:
            return
        if not self._pending_records:
            return
        batch_size = len(self._pending_records)
        insert_history_records(self._db_conn, self._pending_records)
        self._pending_records.clear()
        self._last_commit_monotonic = time.monotonic()
        logger.debug("[%s] батч-коммит записей: %d", self._well.well_id, batch_size)

    def flush(self) -> None:
        self._flush_if_needed(force=True)

    def process_raw_line(self, line: str) -> None:
        timestamp, features = self._parse_line(line)
        self._buffer.append(features)

        self._lines_seen += 1
        if self._lines_seen % 50 == 0:
            logger.info(
                "[%s] получено %d строк, размер окна=%d/%d",
                self._well.well_id,
                self._lines_seen,
                len(self._buffer),
                self._bundle.window_size,
            )

        if len(self._buffer) < self._bundle.window_size:
            return

        window = np.stack(self._buffer, axis=0)
        if self._scaler_feature_names is None:
            transformed = self._bundle.scaler.transform(window)
        else:
            window_df = pd.DataFrame(window, columns=self._scaler_feature_names)
            transformed = self._bundle.scaler.transform(window_df)
        window_scaled = np.asarray(transformed, dtype=np.float32)

        with torch.no_grad():
            x = torch.from_numpy(window_scaled).unsqueeze(0).to(self._bundle.device)
            encoded = self._bundle.model.encode(x).cpu().numpy()[0]
            z_np = np.asarray(encoded, dtype=np.float32)

        cluster_id = int(self._bundle.kmeans.predict(z_np.reshape(1, -1))[0])
        center = self._bundle.kmeans.cluster_centers_[cluster_id].astype(np.float32)
        deviation = float(np.linalg.norm(z_np - center))

        record = HistoryRecord(
            timestamp=timestamp,
            well=self._well.well_id,
            pump_type=self._bundle.pump_type,
            cluster=cluster_id,
            deviation=deviation,
            **{col: float(features[i]) for i, col in enumerate(FEATURE_COLUMNS)},
        )
        self._pending_records.append(record)
        self._flush_if_needed()
        logger.info(
            "[%s] запись: кластер=%s отклонение=%.4f",
            self._well.well_id,
            cluster_id,
            deviation,
        )


def iter_well_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("*.dat.txt"))
