.PHONY: install fmt lint type check run run-fast

install:
	poetry install

run:
	set PYTHONPATH=src&& poetry run python main.py

run-fast:
	set PYTHONPATH=src&& poetry run python main.py --fast

fmt:
	poetry run ruff format .
	poetry run ruff check --fix .

lint:
	poetry run ruff check .

type:
	poetry run mypy src/

check: lint type
