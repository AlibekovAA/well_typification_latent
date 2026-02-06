.PHONY: install fmt lint type check

install:
	poetry install

fmt:
	poetry run ruff format .
	poetry run ruff check --fix .

lint:
	poetry run ruff check .

type:
	poetry run mypy src/

check: lint type
