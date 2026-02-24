from __future__ import annotations

import logging
import threading
import time

from config import STREAM_SLEEP_SECONDS, WELL_CONFIGS, WellConfig
from streaming.processor import WellProcessor, iter_well_files, load_processor_bundle
from streaming.storage import get_connection

logger = logging.getLogger(__name__)


def _run_well_stream(well_cfg: WellConfig, sleep_seconds: float) -> None:
    logger.info("[%s] Запуск потока скважины", well_cfg.well_id)
    bundle = load_processor_bundle(well_cfg.pump_type)

    with get_connection() as conn:
        processor = WellProcessor(well_cfg, bundle, conn)

        for path in iter_well_files(well_cfg.data_dir):
            logger.info("[%s] Читаю файл: %s", well_cfg.well_id, path.name)
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        processor.process_raw_line(line)
                    except ValueError as exc:
                        logger.warning("[%s] Пропущена строка: %s", well_cfg.well_id, exc)
                    except Exception as exc:
                        logger.exception("[%s] Критическая ошибка: %s", well_cfg.well_id, exc)
                    time.sleep(sleep_seconds)

    logger.info("[%s] Все файлы обработаны", well_cfg.well_id)


def run_emulator_background(sleep_seconds: float = STREAM_SLEEP_SECONDS) -> list[threading.Thread]:
    threads = [
        threading.Thread(
            target=_run_well_stream,
            args=(well_cfg, sleep_seconds),
            name=f"well-{well_cfg.well_id}",
            daemon=True,
        )
        for well_cfg in WELL_CONFIGS
    ]
    for t in threads:
        t.start()
    return threads
