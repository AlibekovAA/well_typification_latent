from __future__ import annotations

import argparse
import logging
import signal
import sys

from dashboard.app import run_app

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(threadName)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _exit_clean(_signum: int | None = None, _frame: object | None = None) -> None:
    print("\nОстановка...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _exit_clean)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _exit_clean)

    parser = argparse.ArgumentParser(description="Мониторинг режимов скважин")
    parser.add_argument(
        "--fast",
        "-f",
        action="store_true",
        help="Быстрый эмулятор: пауза 0.1 с между строками (для отладки)",
    )
    args = parser.parse_args()

    try:
        run_app(fast=args.fast)
    except KeyboardInterrupt:
        _exit_clean()
