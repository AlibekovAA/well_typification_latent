from __future__ import annotations

import logging
import sqlite3
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from config import FEATURE_COLUMNS, PUMP_CONFIGS, PumpType, WellConfig
from streaming.storage import HistoryRecord, insert_history_record
from utils import get_device, load_kmeans, load_scaler, load_trained_model

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessorBundle:
    model: Any
    kmeans: KMeans
    scaler: StandardScaler
    window_size: int
    pump_type: PumpType


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
        self._device = get_device()
        self._buffer: deque[np.ndarray] = deque(maxlen=bundle.window_size)

    @staticmethod
    def _parse_line(line: str) -> tuple[str, np.ndarray]:
        parts = line.strip().split("\t")
        if len(parts) < 12:
            raise ValueError(f"Неверный формат строки: {line!r}")

        timestamp = datetime.strptime(f"{parts[0]} {parts[1]}", "%Y.%m.%d %H:%M:%S").isoformat(sep=" ")

        features = np.array(
            [float(parts[i]) for i in (2, 3, 4, 5, 6, 7, 8, 10, 11)],
            dtype=np.float32,
        )
        return timestamp, features

    def process_raw_line(self, line: str) -> None:
        timestamp, features = self._parse_line(line)
        self._buffer.append(features)

        if len(self._buffer) < self._bundle.window_size:
            return

        window = np.stack(self._buffer, axis=0)
        window_df = pd.DataFrame(window, columns=FEATURE_COLUMNS)
        window_scaled = self._bundle.scaler.transform(window_df).astype(np.float32)

        with torch.no_grad():
            x = torch.from_numpy(window_scaled).unsqueeze(0).to(self._device)
            z_np = self._bundle.model.encode(x).cpu().numpy()[0]

        cluster_id = int(self._bundle.kmeans.predict(z_np.reshape(1, -1))[0])
        center = self._bundle.kmeans.cluster_centers_[cluster_id]
        deviation = float(np.linalg.norm(z_np - center))

        record = HistoryRecord(
            timestamp=timestamp,
            well=self._well.well_id,
            pump_type=self._bundle.pump_type,
            cluster=cluster_id,
            deviation=deviation,
            **{col: float(features[i]) for i, col in enumerate(FEATURE_COLUMNS)},
        )
        insert_history_record(self._db_conn, record)
        logger.info(
            "[%s] запись: кластер=%s отклонение=%.4f",
            self._well.well_id,
            cluster_id,
            deviation,
        )


def iter_well_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("*.dat.txt"))
