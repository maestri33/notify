#!/usr/bin/env bash
# Roda o servico em modo desenvolvimento (reload, logs verbosos, porta 80).
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 80 --reload --log-level info
