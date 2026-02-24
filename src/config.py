from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PumpType = Literal["ecn", "shgn"]

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
MODELS_DIR: Path = PROJECT_ROOT / "models"
DB_PATH: Path = PROJECT_ROOT / "db" / "streaming.db"

WINDOW_SIZE_ECN: int = 120
WINDOW_SIZE_SHGN: int = 100

FEATURE_COLUMNS: list[str] = [
    "us_center",
    "us_periph",
    "gas_center",
    "gas_periph",
    "temp",
    "water_center",
    "water_periph",
    "gas_integral",
    "water_integral",
]

FEATURE_LABELS: dict[str, str] = {
    "us_center": "Скорость ультразвука в центре трубы",
    "us_periph": "Скорость ультразвука на периферии трубы",
    "gas_center": "Газосодержание в центре трубы",
    "gas_periph": "Газосодержание на периферии трубы",
    "temp": "Температура",
    "water_center": "Обводнённость в центре трубы",
    "water_periph": "Обводнённость на периферии трубы",
    "gas_integral": "Интегральное газосодержание",
    "water_integral": "Интегральная обводнённость",
}

FEATURE_UNITS: dict[str, str] = {
    "us_center": "м/с",
    "us_periph": "м/с",
    "gas_center": "%",
    "gas_periph": "%",
    "temp": "°C",
    "water_center": "%",
    "water_periph": "%",
    "gas_integral": "%",
    "water_integral": "%",
}

COLUMN_NAMES: list[str] = [
    "date",
    "time",
    "us_center",
    "us_periph",
    "gas_center",
    "gas_periph",
    "temp",
    "water_center",
    "water_periph",
    "outlet_num",
    "gas_integral",
    "water_integral",
]

FEATURE_INDICES: list[int] = [2, 3, 4, 5, 6, 7, 8, 10, 11]


@dataclass(frozen=True)
class PumpConfig:
    pump_type: PumpType
    window_size: int


@dataclass(frozen=True)
class WellConfig:
    well_id: str
    pump_type: PumpType
    data_dir: Path


PUMP_CONFIGS: dict[PumpType, PumpConfig] = {
    "ecn": PumpConfig(pump_type="ecn", window_size=WINDOW_SIZE_ECN),
    "shgn": PumpConfig(pump_type="shgn", window_size=WINDOW_SIZE_SHGN),
}

WELL_CONFIGS: list[WellConfig] = [
    WellConfig(well_id="133", pump_type="ecn", data_dir=DATA_DIR / "скважина 133 ЭЦН"),
    WellConfig(well_id="134", pump_type="shgn", data_dir=DATA_DIR / "скважина 134 ШГН"),
    WellConfig(well_id="135", pump_type="shgn", data_dir=DATA_DIR / "скважина 135 ШГН"),
]

CLUSTER_LABELS: dict[str, dict[int, str]] = {
    "ecn": {0: "Стабильная работа", 1: "Запуск", 2: "Выключена"},
    "shgn": {0: "Нефть", 1: "Нефть→Газ", 2: "Газ", 3: "Вода"},
}

PUMP_TYPE_LABEL: dict[str, str] = {
    "ecn": "ЭЦН",
    "shgn": "ШГН",
}

CLUSTER_COLORS: dict[str, dict[int, str]] = {
    "ecn": {0: "#f0a500", 1: "#2ecc71", 2: "#95a5a6"},
    "shgn": {0: "#8e44ad", 1: "#e67e22", 2: "#3498db", 3: "#1abc9c"},
}

MODEL_HYPERPARAMS: dict[str, int | float] = {
    "input_dim": len(FEATURE_COLUMNS),
    "hidden_size": 192,
    "num_layers": 2,
    "kernel_size": 5,
    "dilation_base": 2,
    "dropout": 0.15,
}

STREAM_SLEEP_SECONDS: float = 10.0
FAST_EMULATOR_SLEEP_SECONDS: float = 0.5
DEVIATION_WARN_THRESHOLD: float = 5
DEVIATION_ALERT_THRESHOLD: float = 5.5
