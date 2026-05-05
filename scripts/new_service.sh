#!/usr/bin/env bash
# new_service.sh — clona este template para um servico novo.
#
# Uso:
#   ./scripts/new_service.sh <nome-do-servico> [destino]
#
# Exemplo:
#   ./scripts/new_service.sh auth-svc           # cria ../auth-svc
#   ./scripts/new_service.sh auth-svc /opt/svc  # cria /opt/svc/auth-svc
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 <nome-do-servico> [destino]" >&2
  exit 1
fi

name="$1"
parent_dir="${2:-$(cd "$(dirname "$0")/../.." && pwd)}"
src="$(cd "$(dirname "$0")/.." && pwd)"
dst="$parent_dir/$name"

if [[ -e "$dst" ]]; then
  echo "Destino ja existe: $dst" >&2
  exit 1
fi

echo "==> Copiando $src -> $dst"
mkdir -p "$dst"
# copia tudo menos venv, caches, banco local e sessoes do claude
rsync -a \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.mypy_cache' \
  --exclude '.ruff_cache' \
  --exclude 'data' \
  --exclude '*.db' \
  --exclude '.claude/sessions' \
  --exclude '.claude/projects' \
  "$src/" "$dst/"

echo "==> Substituindo nome 'microservice-template' -> '$name'"
# tenta gsed (mac) primeiro, depois sed -i
SED_INPLACE=(sed -i)
if command -v gsed >/dev/null 2>&1; then
  SED_INPLACE=(gsed -i)
elif sed --version >/dev/null 2>&1; then
  SED_INPLACE=(sed -i)
else
  SED_INPLACE=(sed -i '')
fi

grep -rl "microservice-template" "$dst" \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=__pycache__ \
  | while read -r f; do
    "${SED_INPLACE[@]}" "s/microservice-template/$name/g" "$f"
  done

echo "==> Pronto."
echo "    cd $dst"
echo "    cp .env.example .env"
echo "    uv sync"
echo "    make dev"
