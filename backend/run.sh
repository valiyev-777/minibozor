#!/usr/bin/env bash
# The backend on its own, reachable from the Android emulator (10.0.2.2) and
# the iOS simulator.
#
# For everything at once — Postgres, the API and the three web panels — use
# `../dev.sh` from the repository root. This is the one service, for when that
# is all you want.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${MB_PORT:-8000}"

# The schema belongs to Alembic, and startup checks the revision rather than
# creating tables — so the order matters and a bad order should say so.
#
# This used to be `[ -f minibozor.db ] || python -m app.seed`, which was wrong
# twice over: it ran the seed with no explicit MB_DATABASE_URL, so it wrote to
# whatever the environment happened to point at, and the seed now refuses a
# database that is not at head — so on a fresh checkout it failed with a schema
# error rather than building anything.
if ! .venv/bin/python - <<'PY'
import sys

from app.db import require_current_schema

try:
    require_current_schema()
except RuntimeError as error:
    print(error, file=sys.stderr)
    sys.exit(1)
PY
then
  echo >&2
  echo "The database is not ready. From backend/:" >&2
  echo "    .venv/bin/alembic upgrade head" >&2
  echo "    .venv/bin/python -m app.seed        # if it holds nothing yet" >&2
  exit 1
fi

# A phone or emulator reaches this server through its own localhost, so open the
# reverse tunnel if adb is around and a device is attached. Harmless otherwise.
ADB="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
[ -x "$ADB" ] && "$ADB" reverse "tcp:$PORT" "tcp:$PORT" >/dev/null 2>&1 || true

exec .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port "$PORT"
