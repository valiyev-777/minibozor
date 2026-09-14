#!/usr/bin/env bash
#
# The whole system, locally, in one command.
#
#     ./dev.sh              bring everything up and hold it
#     ./dev.sh status       is everything alive? (one line per service)
#     ./dev.sh down         stop anything left listening on our ports
#     ./dev.sh --help
#
# ---------------------------------------------------------------- why a script
#
# Three mechanisms were on the table and this is a shell script because of the
# ordering.
#
# `docker compose` for all five services would mean a Dockerfile per web app,
# an image rebuild on every dependency change, and bind mounts to get `--reload`
# and HMR working through a container — slower to use and more to maintain than
# what it replaces, for a job that is "start five things on one laptop". The
# database is already in compose, where it belongs: it is the one piece with
# state and a version that matters.
#
# A Procfile runner (honcho, foreman, overmind) starts every process at once,
# and that is exactly what must not happen here. The backend checks the schema
# revision on startup and refuses to run if it is behind, so Postgres has to be
# accepting connections and the database has to be at head *before* uvicorn is
# launched. A runner that starts them together turns a solved ordering problem
# into a race that usually works.
#
# What is left is a script, and the requirements are sequential logic rather
# than process supervision: check the ports, check `node_modules`, check the
# revision, then start four things and watch them.
#
# ------------------------------------------------- and why it moves to a host
#
# Every address is a variable and every variable takes its value from the
# environment, so pointing this at something else is `MB_API_PORT=9000 ./dev.sh`
# rather than an edit. The three web apps read their API base from
# `VITE_API_URL`, which this exports; the backend reads `MB_DATABASE_URL`. That
# is the whole surface. A real deployment replaces the *process manager* — this
# script — and keeps the configuration: it does not rewrite the applications,
# because none of them have a hostname compiled into them.
#
# Host, domain, TLS, nginx, systemd and CI are deliberately absent. This brings
# up a laptop.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# --------------------------------------------------------------------- config

API_HOST="${MB_API_HOST:-127.0.0.1}"
API_PORT="${MB_API_PORT:-8000}"
API_URL="${MB_API_URL:-http://localhost:${API_PORT}}"

# One web app where there were three. The port is the one the back office
# used, because it is the one everybody has bookmarked.
WEB_PORT="${MB_WEB_PORT:-5173}"

# The database compose reads. Kept in step with backend/docker-compose.yml.
DB_PORT="${MB_POSTGRES_PORT:-5434}"
DB_CONTAINER="${MB_DB_CONTAINER:-minibozor_db}"

VENV="$ROOT/backend/.venv"
PY="$VENV/bin/python"
LOG_DIR="${MB_LOG_DIR:-$ROOT/.dev-logs}"

# How long to wait for a service to answer before calling it failed. Vite is
# fast; a cold uvicorn with --reload and 190 routes is not.
WAIT_SECONDS="${MB_WAIT_SECONDS:-45}"

# Which services this run started, as "name:pid" — the list `cleanup` walks.
declare -a STARTED=()
declare -a STARTED_NAMES=()

# ---------------------------------------------------------------------- output

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  B=$'\033[1m'; DIM=$'\033[2m'; R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; N=$'\033[0m'
else
  B=''; DIM=''; R=''; G=''; Y=''; N=''
fi

say()  { printf '%s\n' "$*"; }
step() { printf '%s==>%s %s\n' "$B" "$N" "$*"; }
ok()   { printf '  %s✓%s %s\n' "$G" "$N" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$R" "$N" "$*"; }
die()  { printf '\n%sCannot start.%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

# ------------------------------------------------------------------- utilities

# Who is listening on a TCP port, or nothing. `ss` is on every Linux with
# iproute2; `lsof` is the fallback because it is what macOS has.
port_holder() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnpH "sport = :$port" 2>/dev/null \
      | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2
  elif command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null | head -1
  fi
}

port_busy() { [ -n "$(port_holder "$1")" ]; }

describe_pid() {
  local pid="$1"
  [ -z "$pid" ] && { echo "unknown process"; return; }
  local cmd; cmd="$(ps -o args= -p "$pid" 2>/dev/null | head -1 | cut -c1-70)"
  echo "pid $pid — ${cmd:-gone}"
}

# Poll a URL until it answers, or give up. Returns the last status code.
wait_for_http() {
  local url="$1" deadline=$(( SECONDS + WAIT_SECONDS )) code=000
  while [ "$SECONDS" -lt "$deadline" ]; do
    # No `|| echo 000` here: curl already prints `000` when it cannot connect
    # *and* exits non-zero, so the fallback appended a second one and `000000`
    # is not `000` — which made a refused connection look like an answer.
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null)"
    [ -z "$code" ] && code=000
    # Any answer at all means the server is up. 503 from /health is a *running*
    # backend telling us its database is wrong, which is a different problem
    # and one it reports better than we could.
    [ "$code" != "000" ] && { echo "$code"; return 0; }
    sleep 0.4
  done
  echo "$code"
  return 1
}

# ------------------------------------------------------------------- teardown
#
# Ctrl+C must leave nothing behind. Two mechanisms, because one is not enough:
#
#   * every child is started with `setsid`, so it leads its own process group.
#     `vite` and `uvicorn --reload` both fork — uvicorn's reloader supervises a
#     worker, vite spawns esbuild — and killing the pid we know about leaves the
#     grandchildren holding the port. Killing the *group* takes the family.
#   * the ports are checked afterwards, and anything still listening on one of
#     ours is killed by port. That catches a process that outlived its group
#     and is the difference between "we tried" and "the port is free".

cleanup() {
  local code=$?
  trap - INT TERM EXIT
  printf '\n%s==>%s stopping\n' "$B" "$N"

  local i pid name
  for i in "${!STARTED[@]}"; do
    pid="${STARTED[$i]}"; name="${STARTED_NAMES[$i]}"
    if kill -0 "$pid" 2>/dev/null; then
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
      ok "$name stopped"
    fi
  done

  # Give them a moment to go quietly, then insist.
  local deadline=$(( SECONDS + 6 ))
  while [ "$SECONDS" -lt "$deadline" ]; do
    local alive=0
    for pid in "${STARTED[@]}"; do kill -0 "$pid" 2>/dev/null && alive=1; done
    [ "$alive" -eq 0 ] && break
    sleep 0.3
  done
  for pid in "${STARTED[@]}"; do
    kill -0 "$pid" 2>/dev/null && kill -KILL -- "-$pid" 2>/dev/null
  done

  # Anything still on one of our ports, whoever it belongs to now.
  local port holder
  for port in "$API_PORT" "$WEB_PORT"; do
    holder="$(port_holder "$port")"
    if [ -n "$holder" ]; then
      kill -KILL "$holder" 2>/dev/null && warn "killed leftover on :$port ($holder)"
    fi
  done

  say "${DIM}Postgres is left running — it holds your data. './dev.sh down' or"
  say "'cd backend && docker compose stop' if you want it stopped.${N}"
  exit "$code"
}

# --------------------------------------------------------------- start a thing

# start <name> <port> <dir> <command...>
start_service() {
  local name="$1" port="$2" dir="$3"; shift 3
  local log="$LOG_DIR/$name.log"
  : > "$log"
  # setsid: its own process group, so cleanup can take the whole family.
  ( cd "$dir" && exec setsid "$@" >>"$log" 2>&1 ) &
  local pid=$!
  STARTED+=("$pid")
  STARTED_NAMES+=("$name")
  printf '  %s·%s %-11s starting on :%s %s(%s)%s\n' \
    "$DIM" "$N" "$name" "$port" "$DIM" "$log" "$N"
}

# ------------------------------------------------------------------ preflight

preflight() {
  step "Checking what is here"

  [ -x "$PY" ] || die "No virtualenv at backend/.venv.
    Create it and install the backend:
      cd backend && python3 -m venv .venv
      .venv/bin/python -m pip install -e '.[dev,postgres]'"
  ok "backend virtualenv"

  command -v curl >/dev/null 2>&1 || die "curl is needed for the health checks."

  # Node, only if the web app is going to be started.
  if ! command -v npm >/dev/null 2>&1; then
    die "npm is not on PATH, and one of the four interfaces is a web app."
  fi
  ok "node $(node --version 2>/dev/null), npm $(npm --version 2>/dev/null)"

  # Dependencies. Installing is the friendly default; MB_NO_INSTALL=1 turns it
  # into a refusal for anybody who would rather nothing touched their tree.
  if [ -d "$ROOT/web" ]; then
    if [ ! -d "$ROOT/web/node_modules" ]; then
      if [ -n "${MB_NO_INSTALL:-}" ]; then
        die "web/node_modules is missing. Run:  cd web && npm install"
      fi
      warn "web/node_modules missing — installing (once, this will take a minute)"
      if ! ( cd "$ROOT/web" && npm install --no-audit --no-fund ); then
        die "npm install failed in web/. Run it by hand to see why."
      fi
    fi
    [ -x "$ROOT/web/node_modules/.bin/vite" ] || die \
      "web/node_modules exists but has no vite binary. Try:  cd web && npm install"
    ok "node_modules and vite present in web"
  else
    warn "web/ not present yet — skipping"
  fi

  # Ports. Named individually, because "address already in use" from two
  # services at once tells you nothing about which one lost.
  local busy=0 port name
  for pair in "$API_PORT:backend" "$WEB_PORT:web"; do
    port="${pair%%:*}"; name="${pair##*:}"
    [ "$name" = backend ] || [ -d "$ROOT/$name" ] || continue
    if port_busy "$port"; then
      bad ":$port is taken — $name wants it — $(describe_pid "$(port_holder "$port")")"
      busy=1
    fi
  done
  if [ "$busy" -eq 1 ]; then
    die "Ports above are in use. Stop them, or './dev.sh down' to clear ours,
    or move this run:  MB_API_PORT=8100 MB_WEB_PORT=5273 ./dev.sh"
  fi
  ok "ports :$API_PORT :$WEB_PORT are free"
}

# ------------------------------------------------------------------- database

database() {
  step "Database"
  mkdir -p "$LOG_DIR"

  # Which one? Whatever the backend itself would open, asked of the backend.
  local url dialect
  url="$( cd "$ROOT/backend" && "$PY" -c \
    'from app.core.config import settings; print(settings.database_url)' 2>/dev/null )"
  [ -z "$url" ] && die "Could not read MB_DATABASE_URL from backend/.env or the defaults."

  case "$url" in
    postgresql*|postgres://*) dialect=postgres ;;
    sqlite*)                  dialect=sqlite ;;
    *)                        dialect=other ;;
  esac
  # The summary printed a Postgres address whichever database was in use, so
  # the line under "SQLite — minibozor.db" said to connect to a container that
  # was not running. What is open is worth knowing; what is not open is worth
  # not being told.
  DB_DIALECT="$dialect"
  DB_FILE="${url##*/}"

  if [ "$dialect" = postgres ]; then
    if ! command -v docker >/dev/null 2>&1; then
      die "MB_DATABASE_URL points at Postgres but docker is not on PATH."
    fi
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$DB_CONTAINER"; then
      warn "starting Postgres ($DB_CONTAINER)"
      ( cd "$ROOT/backend" && docker compose up -d ) >/dev/null 2>&1 \
        || die "docker compose up failed. From backend/:  docker compose up -d
    A missing MB_POSTGRES_PASSWORD in backend/.env stops it on purpose."
    fi
    local deadline=$(( SECONDS + 60 ))
    until [ "$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER" 2>/dev/null)" = healthy ]; do
      [ "$SECONDS" -ge "$deadline" ] && die "Postgres did not become healthy in 60s.
    Look at:  docker logs $DB_CONTAINER"
      sleep 1
    done
    ok "Postgres healthy on :$DB_PORT"
  else
    ok "SQLite — ${url##*/}"
  fi

  # The revision, before uvicorn rather than through it. The backend refuses to
  # start when the database is behind, and its message is good; it is just a
  # worse place to read it than here, five seconds earlier, next to the command
  # that fixes it.
  local schema
  # The message and not the traceback: `require_current_schema` already writes
  # a sentence naming both revisions and the command, and eleven frames of
  # SQLAlchemy on top of it is exactly the "uvicorn error" this check exists to
  # replace.
  if schema="$( cd "$ROOT/backend" && "$PY" -c '
import sys

from app.db import require_current_schema

try:
    print(require_current_schema())
except RuntimeError as error:
    print(error, file=sys.stderr)
    sys.exit(1)
' 2>"$LOG_DIR/schema.err" )"; then
    ok "schema at $schema"
  else
    say ""
    sed 's/^/  /' "$LOG_DIR/schema.err"
    say ""
    die "The database is not ready, so the backend would refuse to start.
    From backend/:
      .venv/bin/alembic upgrade head
      .venv/bin/python -m app.seed        # if it holds nothing yet"
  fi
}

# --------------------------------------------------------------------- startup

bring_up() {
  mkdir -p "$LOG_DIR"
  trap cleanup INT TERM EXIT

  step "Starting"
  # The backend first, and alone for a moment: the web apps are useless without
  # it and this way a backend that will not start is not buried under three
  # lots of Vite output.
  start_service backend "$API_PORT" "$ROOT/backend" \
    "$VENV/bin/uvicorn" app.main:app --reload --host "$API_HOST" --port "$API_PORT"

  local code
  code="$(wait_for_http "$API_URL/health")" || {
    bad "backend did not answer on :$API_PORT within ${WAIT_SECONDS}s"
    say ""
    tail -25 "$LOG_DIR/backend.log"
    die "See $LOG_DIR/backend.log"
  }
  if [ "$code" = "200" ]; then
    ok "backend answering on :$API_PORT"
  else
    warn "backend answering on :$API_PORT but /health says $code — see './dev.sh status'"
  fi

  # And the tunnel a real phone needs, which `backend/run.sh` used to open and
  # this script had dropped.
  #
  # The Android and iOS debug builds have `http://localhost:8000` compiled in,
  # deliberately: `10.0.2.2` is the emulator's alias for the host and means
  # nothing on a handset, so one address that works on both is worth more than
  # two that each work once. `adb reverse` is what makes it true on a handset —
  # it forwards the device's own localhost:8000 back down the USB cable to this
  # machine's. Without it the app resolves localhost to the phone itself, finds
  # nothing listening, and shows a network error that looks like a bug in the
  # app.
  #
  # Harmless when there is no adb and no device: nothing is attached, nothing
  # is claimed. Reported either way, because "did the tunnel open" is the first
  # question when the phone shows nothing.
  local adb="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
  if [ -x "$adb" ]; then
    local attached
    attached="$("$adb" devices 2>/dev/null | grep -cw device || true)"
    if [ "${attached:-0}" -gt 0 ]; then
      if "$adb" reverse "tcp:$API_PORT" "tcp:$API_PORT" >/dev/null 2>&1; then
        ok "adb reverse :$API_PORT — the phone reaches this backend"
      else
        warn "adb reverse failed — a USB-connected phone will not reach :$API_PORT"
      fi
    fi
  fi

  # The web app, handed the API address so it does not have to have guessed
  # right in its own .env.
  export VITE_API_URL="$API_URL"
  # Vite's own binary, not `npm run dev`. Through npm the process this script
  # tracks is npm, which forks a shell which forks node: the pid we watch is
  # two removes from the thing that holds the port, so "did it die" was being
  # asked about the wrong process — a vite that crashed left npm alive and this
  # script none the wiser. Running the binary makes the tracked pid the server.
  if [ -d "$ROOT/web" ]; then
    start_service web "$WEB_PORT" "$ROOT/web" \
      "$ROOT/web/node_modules/.bin/vite" --port "$WEB_PORT" --strictPort
    if code="$(wait_for_http "http://localhost:$WEB_PORT/")"; then
      ok "web answering on :$WEB_PORT"
    else
      bad "web did not answer on :$WEB_PORT — see $LOG_DIR/web.log"
    fi
  fi
}

# ---------------------------------------------------------------- the summary

summary() {
  local admin warehouse seller courier demo store
  read -r admin warehouse seller courier demo <<<"$( cd "$ROOT/backend" && "$PY" -c \
    'from app import seed; print(seed.ADMIN_PHONE, seed.WAREHOUSE_PHONE, seed.SELLER_PHONE, seed.COURIER_PHONE, seed.DEMO_PHONE)' \
    2>/dev/null || echo '+998900000001 +998900000002 +998900000004 +998900000003 +998901234567' )"

  if [ "${DB_DIALECT:-}" = postgres ]; then
    store="$(printf '%-16s%-31s%s' 'Postgres' "localhost:$DB_PORT" "(docker: $DB_CONTAINER)")"
  else
    store="$(printf '%-16s%-31s%s' 'SQLite' "backend/$DB_FILE" '(a file, not a service)')"
  fi

  cat <<EOF

${B}Everything is up.${N}

  ${B}Interface${N}       ${B}Address${N}                        ${B}Sign in as${N}
  web             http://localhost:$WEB_PORT           admin      $admin
                                                    ombor      $warehouse
                                                    sotuvchi   $seller
                                                    kuryer     $courier
  API + /docs     $API_URL/docs      —
  API health      $API_URL/health    —
  $store

  One web app, not three panels: the same bundle is the office, the bench and
  the van, and the role on the account decides which. The Android and iOS
  clients are the shopping app and talk to this same API. From an emulator
  that is http://10.0.2.2:$API_PORT, from a simulator http://localhost:$API_PORT.

  ${B}Signing in${N} — every interface uses the same OTP flow. Enter the phone
  number, then the SMS code ${B}123456${N} (dev builds return it in the response).
  The shopper's PIN is 1234. Customer demo account: $demo

  More staff, if you need them:
      cd backend && .venv/bin/python -m tools.make_staff +998900000009 warehouse "Ismi"

  Logs      $LOG_DIR/{backend,web}.log
  Status    ./dev.sh status
  Stop      Ctrl+C   (Postgres keeps running; './dev.sh down' stops the rest)

EOF
}

# --------------------------------------------------------------------- status

cmd_status() {
  local failed=0 code detail
  printf '%s%-12s %-34s %-8s %s%s\n' "$B" "SERVICE" "ADDRESS" "STATUS" "DETAIL" "$N"

  # Postgres, if that is what the backend is pointed at.
  local url
  url="$( cd "$ROOT/backend" && "$PY" -c \
    'from app.core.config import settings; print(settings.database_url)' 2>/dev/null )"
  case "$url" in
    postgresql*|postgres://*)
      local health
      health="$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER" 2>/dev/null)"
      if [ "$health" = healthy ]; then
        printf '%-12s %-34s %s%-8s%s %s\n' postgres "localhost:$DB_PORT" "$G" up "$N" "container $DB_CONTAINER"
      else
        printf '%-12s %-34s %s%-8s%s %s\n' postgres "localhost:$DB_PORT" "$R" down "$N" "${health:-not running}"
        failed=1
      fi
      ;;
    *)
      printf '%-12s %-34s %s%-8s%s %s\n' sqlite "${url##*/}" "$G" "n/a" "$N" "a file, not a service"
      ;;
  esac

  # The backend, which is the only one that can say more than "listening".
  local body
  body="$(curl -s --max-time 4 "$API_URL/health" 2>/dev/null)"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$API_URL/health" 2>/dev/null)"
  [ -z "$code" ] && code=000
  if [ "$code" = "200" ]; then
    detail="$( printf '%s' "$body" | "$PY" -c '
import json, sys
d = json.load(sys.stdin)["database"]
print("{} at {}, {}ms".format(d["dialect"], d["revision"], d["latency_ms"]))
' 2>/dev/null || echo "healthy" )"
    printf '%-12s %-34s %s%-8s%s %s\n' backend "$API_URL" "$G" up "$N" "$detail"
  elif [ "$code" = "503" ]; then
    detail="$( printf '%s' "$body" | "$PY" -c '
import json, sys
d = json.load(sys.stdin)["database"]
why = "reachable but not at head" if d["reachable"] else "unreachable"
print("database {} (want {}, have {})".format(why, d["expected"], d["revision"]))
' 2>/dev/null || echo "unhealthy" )"
    printf '%-12s %-34s %s%-8s%s %s\n' backend "$API_URL" "$R" sick "$N" "$detail"
    failed=1
  else
    printf '%-12s %-34s %s%-8s%s %s\n' backend "$API_URL" "$R" down "$N" "no answer (HTTP $code)"
    failed=1
  fi

  # The three panels. A Vite dev server has no health endpoint of its own, so
  # the honest check is that it serves its index and that the index is an HTML
  # document — which is what a browser is about to ask for.
  local name port
  for pair in "web:$WEB_PORT"; do
    name="${pair%%:*}"; port="${pair##*:}"
    [ -d "$ROOT/$name" ] || continue
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://localhost:$port/" 2>/dev/null)"
    [ -z "$code" ] && code=000
    if [ "$code" = "200" ]; then
      if curl -s --max-time 4 "http://localhost:$port/" 2>/dev/null | grep -qi '<div id="root"'; then
        detail="serving its index"
      else
        detail="answering, but the index looks wrong"
      fi
      printf '%-12s %-34s %s%-8s%s %s\n' "$name" "http://localhost:$port" "$G" up "$N" "$detail"
    else
      printf '%-12s %-34s %s%-8s%s %s\n' "$name" "http://localhost:$port" "$R" down "$N" "no answer (HTTP $code)"
      failed=1
    fi
  done

  return "$failed"
}

# ----------------------------------------------------------------------- down

cmd_down() {
  local port holder stopped=0
  for pair in "$API_PORT:backend" "$WEB_PORT:web"; do
    port="${pair%%:*}"
    holder="$(port_holder "$port")"
    if [ -n "$holder" ]; then
      say "stopping $(describe_pid "$holder") on :$port"
      # The group first: vite and uvicorn --reload both have children that
      # would otherwise keep the port.
      kill -TERM -- "-$holder" 2>/dev/null || kill -TERM "$holder" 2>/dev/null
      stopped=1
    fi
  done
  [ "$stopped" -eq 1 ] && sleep 2
  for pair in "$API_PORT:x" "$WEB_PORT:x"; do
    port="${pair%%:*}"
    holder="$(port_holder "$port")"
    [ -n "$holder" ] && kill -KILL "$holder" 2>/dev/null
  done
  if [ "$stopped" -eq 1 ]; then ok "stopped"; else ok "nothing was listening"; fi

  # A `dev.sh` still supervising is reported rather than killed: the ports are
  # configurable, so a second run on other ports is a legitimate thing to be
  # doing and is none of this one's business.
  local others
  others="$(pgrep -f '[b]ash .*dev\.sh$' 2>/dev/null | grep -v "^$$\$" | tr '\n' ' ')"
  [ -n "${others// /}" ] && warn "a dev.sh is still running (pid ${others% }) — Ctrl+C it in its own terminal"

  say "${DIM}Postgres is separate:  cd backend && docker compose stop${N}"
}

# ----------------------------------------------------------------------- main

case "${1:-up}" in
  up|"")
    preflight
    database
    bring_up
    summary
    step "Running — Ctrl+C to stop everything"
    # Watch the children. If one dies the others carry on, because a broken
    # panel should not cost you the backend you were about to debug it against
    # — but it has to be visible, and a name is more use than a pid.
    while :; do
      sleep 2
      alive=0
      for i in "${!STARTED[@]}"; do
        pid="${STARTED[$i]}"
        if [ -z "$pid" ]; then continue; fi
        if kill -0 "$pid" 2>/dev/null; then
          alive=$(( alive + 1 ))
          continue
        fi
        bad "${STARTED_NAMES[$i]} exited — last lines of $LOG_DIR/${STARTED_NAMES[$i]}.log:"
        tail -8 "$LOG_DIR/${STARTED_NAMES[$i]}.log" 2>/dev/null | sed 's/^/      /'
        say "      the others are still up; restart it alone, or Ctrl+C and start again"
        STARTED[$i]=""
      done
      # Nothing left to supervise. Sitting in this loop over an empty stack is
      # how a `dev.sh` ends up in `ps` a day later holding no port and doing
      # nothing — which is the mess this script exists to avoid, so it exits
      # and lets the trap tidy up.
      if [ "$alive" -eq 0 ]; then
        say ""
        bad "every service has exited — nothing left to watch"
        exit 1
      fi
    done
    ;;
  status)
    if cmd_status; then
      printf '\n%sall up%s\n' "$G" "$N"
    else
      printf '\n%ssomething is down%s — ./dev.sh   to start it\n' "$R" "$N"
      exit 1
    fi
    ;;
  down) cmd_down ;;
  -h|--help|help)
    sed -n '2,8p' "$BASH_SOURCE"| sed 's/^#\s\?//'
    say ""
    say "Ports, and how to move them:"
    say "  MB_API_PORT=$API_PORT  MB_WEB_PORT=$WEB_PORT"
    say "  MB_NO_INSTALL=1   refuse to run npm install, just say what is missing"
    say "  MB_LOG_DIR=...    where the four logs go (default .dev-logs/)"
    ;;
  *) die "Unknown command '$1'. Try: up, status, down, --help" ;;
esac
