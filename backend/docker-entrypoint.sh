#!/bin/sh
set -e

# Only the api container runs migrations. Workers start straight into rq.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "[entrypoint] running alembic upgrade head..."
  alembic upgrade head
fi

exec "$@"
