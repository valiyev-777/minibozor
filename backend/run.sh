#!/usr/bin/env bash
# Dev server, reachable from the Android emulator (10.0.2.2) and iOS simulator.
set -euo pipefail
cd "$(dirname "$0")"
[ -f minibozor.db ] || .venv/bin/python -m app.seed
exec .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
