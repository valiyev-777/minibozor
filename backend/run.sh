#!/usr/bin/env bash
# Dev server, reachable from the Android emulator (10.0.2.2) and iOS simulator.
set -euo pipefail
cd "$(dirname "$0")"
[ -f minibozor.db ] || .venv/bin/python -m app.seed

# A phone or emulator reaches this server through its own localhost, so open the
# reverse tunnel if adb is around and a device is attached. Harmless otherwise.
ADB="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
[ -x "$ADB" ] && "$ADB" reverse tcp:8000 tcp:8000 >/dev/null 2>&1 || true
exec .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
