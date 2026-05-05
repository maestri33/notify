.PHONY: help install dev run test lint fmt migrate clean

help:
	@echo "make install   - sincroniza dependencias (uv sync)"
	@echo "make dev       - roda uvicorn com reload na porta 80"
	@echo "make run       - roda uvicorn em modo prod (sem reload)"
	@echo "make test      - roda pytest"
	@echo "make lint      - ruff check + mypy"
	@echo "make fmt       - ruff format"
	@echo "make migrate   - aerich migrate && upgrade"
	@echo "make clean     - remove caches"

install:
	uv sync

dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --workers 2

test:
	uv run pytest -q

lint:
	uv run ruff check app tests
	uv run mypy app

fmt:
	uv run ruff format app tests
	uv run ruff check --fix app tests

migrate:
	uv run aerich migrate
	uv run aerich upgrade

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +
