#!/usr/bin/env bash
#
# The whole system, locally, in one command.
#
#     ./dev.sh              bring everything up and hold it
#     ./dev.sh status       is everything alive? (one line per service)
#     ./dev.sh logs [name]  follow the logs
#     ./dev.sh build        rebuild the images (after a dependency change)
#     ./dev.sh sh <name>    a shell inside a container
#     ./dev.sh down         stop it
#     ./dev.sh --help
#
# ------------------------------------------------------------- what this is
#
# A thin wrapper around `docker-compose.yml`, which is where everything about
# *what runs* lives. This script exists for the three things compose does not
# do: it points compose at backend/.env, it opens the adb tunnel a USB phone
# needs, and it prints the addresses and the accounts at the end.
#
# It used to start four host processes itself — a venv uvicorn, a host Vite,
# and a great deal of process-group bookkeeping to make Ctrl+C leave nothing
# behind. Containers make that the container runtime's problem: a stopped
# container holds no port, and there is no such thing as a grandchild that
# outlived it.
#
# What is *not* given up in the move: `--reload` and HMR still work, because
# neither image contains any source — the repository is bind-mounted into both.
# An edit is a reload, never a rebuild. `./dev.sh build` is only for a change to
# pyproject.toml or package.json.
#
# ------------------------------------------------- and why it moves to a host
#
# Every address is a variable and every variable comes from the environment, so
# pointing this somewhere else is `MB_API_PORT=9000 ./dev.sh` rather than an
# edit. A real deployment replaces the *compose file* and keeps the
# configuration; it does not rewrite the applications, because none of them
# have a hostname compiled into them.
#
# Host, domain, TLS, nginx and CI are deliberately absent. This brings up a
# laptop.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --------------------------------------------------------------------- config

API_PORT="${MB_API_PORT:-8000}"
API_URL="${MB_API_URL:-http://localhost:${API_PORT}}"
WEB_PORT="${MB_WEB_PORT:-5173}"
DB_PORT="${MB_POSTGRES_PORT:-5434}"

ENV_FILE="$ROOT/backend/.env"

# How long to wait for the API to answer before calling it failed. A cold
# uvicorn with --reload and 190 routes is not fast, and the first start also
# migrates and seeds.
WAIT_SECONDS="${MB_WAIT_SECONDS:-90}"

# One invocation of compose, defined once. `--env-file` is what makes
# backend/.env the source of MB_POSTGRES_PASSWORD and friends: compose reads
# `.env` from its own directory by default, and this project's is one level
# down in backend/, next to the application that owns it.
compose() { docker compose --env-file "$ENV_FILE" -f "$ROOT/docker-compose.yml" "$@"; }

# ---------------------------------------------------------------------- output

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; DIM=$'\033[2m'; N=$'\033[0m'
else B=""; G=""; Y=""; R=""; DIM=""; N=""; fi

say()  { printf '%s\n' "$*"; }
step() { printf '%s==>%s %s\n' "$B" "$N" "$*"; }
ok()   { printf '  %s✓%s %s\n' "$G" "$N" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$R" "$N" "$*"; }
die()  { printf '\n%sCannot start.%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

# ------------------------------------------------------------------- utilities

# Poll a URL until it answers, or give up. Prints the last status code.
wait_for_http() {
  local url="$1" deadline=$(( SECONDS + WAIT_SECONDS )) code
  while [ "$SECONDS" -lt "$deadline" ]; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$url" 2>/dev/null)"
    [ "$code" = "200" ] && { printf '%s' "$code"; return 0; }
    sleep 1
  done
  printf '%s' "${code:-000}"
  return 1
}

# ------------------------------------------------------------------ preflight

preflight() {
  step "Checking what is here"

  command -v docker >/dev/null 2>&1 || die "docker is not on PATH.
    Everything now runs in containers — see 'Docker, in this project' in README.md."
  docker compose version >/dev/null 2>&1 || die "'docker compose' is not available.
    This needs Compose v2, which ships with Docker Desktop and with the
    docker-compose-plugin package on Linux."
  docker info >/dev/null 2>&1 || die "the Docker daemon is not running.
    Either:  sudo systemctl start docker          (the system daemon)
    or:      systemctl --user start docker-desktop && docker context use desktop-linux"
  ok "docker $(docker --version | sed 's/Docker version //; s/,.*//'), compose $(docker compose version --short 2>/dev/null)"

  # Which daemon, named out loud.
  #
  # Docker Desktop is installed on this machine alongside the system daemon,
  # and they are two engines with two separate sets of images, containers and
  # volumes — nothing is shared. Switching context is therefore not a view
  # change: the containers you had are still running, on the other daemon,
  # invisible from here, and `./dev.sh` will build a second set. That is worth
  # one line rather than ten minutes of "where did everything go".
  ok "daemon: context $(docker context show 2>/dev/null) — $(docker context inspect -f '{{.Endpoints.docker.Host}}' 2>/dev/null)"

  [ -f "$ENV_FILE" ] || die "backend/.env is missing. Create it:
      cp backend/.env.example backend/.env
    and set MB_POSTGRES_PASSWORD to anything — the database will not start
    without one, on purpose."
  grep -q '^MB_POSTGRES_PASSWORD=..*' "$ENV_FILE" \
    || die "MB_POSTGRES_PASSWORD is empty in backend/.env. The database refuses
    to start without one rather than come up open to the network."
  ok "backend/.env"

  command -v curl >/dev/null 2>&1 || die "curl is needed for the health checks."

  # Ports. Anything holding one of ours that is *not* one of our own containers
  # is a conflict worth naming — compose would otherwise fail with "port is
  # already allocated" and no clue whose.
  local port name holder busy=0
  for pair in "$API_PORT:api" "$WEB_PORT:web" "$DB_PORT:db"; do
    port="${pair%%:*}"; name="${pair##*:}"
    holder="$(docker ps --filter "publish=$port" --format '{{.Names}}' 2>/dev/null | head -1)"
    [ -n "$holder" ] && continue                       # ours, or about to be replaced
    if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$port "; then
      bad ":$port is taken and not by a container — $name wants it"
      busy=1
    fi
  done
  [ "$busy" -eq 1 ] && die "Ports above are in use. Stop them, or move this run:
      MB_API_PORT=8100 MB_WEB_PORT=5273 ./dev.sh"
  ok "ports :$API_PORT :$WEB_PORT :$DB_PORT"
}

# -------------------------------------------------------------------- teardown

cleanup() {
  local code=$?
  trap - INT TERM EXIT
  printf '\n%s==>%s stopping\n' "$B" "$N"
  # api and web, not db. Stopping the database on every Ctrl+C means waiting
  # for it to come back on every start, and it is the one service with state.
  compose stop api web >/dev/null 2>&1 && ok "api and web stopped"
  say "${DIM}Postgres is left running — it holds your data."
  say "'./dev.sh down' stops that too.${N}"
  exit "$code"
}

# --------------------------------------------------------------------- startup

bring_up() {
  step "Starting"
  # --build only when an image is missing; compose decides. A source edit is
  # never a rebuild here, because no source is in the image.
  if ! compose up -d --remove-orphans; then
    say ""
    die "compose could not start everything. The output above says which service;
    './dev.sh logs <name>' is the rest of it."
  fi
  ok "containers up"

  local code
  code="$(wait_for_http "$API_URL/health")" || {
    bad "the API did not answer on :$API_PORT within ${WAIT_SECONDS}s"
    say ""
    compose logs --tail 25 api
    die "See './dev.sh logs api'"
  }
  ok "API answering on :$API_PORT"

  if code="$(wait_for_http "http://localhost:$WEB_PORT/")"; then
    ok "web answering on :$WEB_PORT"
  else
    bad "web did not answer on :$WEB_PORT — see './dev.sh logs web'"
  fi

  adb_reverse
}

# The tunnel a real phone needs.
#
# The Android and iOS debug builds have `http://localhost:8000` compiled in,
# deliberately: `10.0.2.2` is the emulator's alias for the host and means
# nothing on a handset, so one address that works on both is worth more than
# two that each work once. `adb reverse` is what makes it true on a handset — it
# forwards the device's own localhost:8000 back down the USB cable to this
# machine's, where compose has published the API's port. Without it the app
# resolves localhost to the phone itself, finds nothing, and shows a network
# error that looks like a bug in the app.
#
# Unplugging the cable drops this and replugging does not restore it, so it is
# also what `./dev.sh status` reports on and what to re-run by hand.
adb_reverse() {
  local adb="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
  [ -x "$adb" ] || return 0
  local attached
  attached="$("$adb" devices 2>/dev/null | grep -cw device || true)"
  [ "${attached:-0}" -gt 0 ] || return 0
  if "$adb" reverse "tcp:$API_PORT" "tcp:$API_PORT" >/dev/null 2>&1; then
    ok "adb reverse :$API_PORT — the phone reaches this API"
  else
    warn "adb reverse failed — a USB phone will not reach :$API_PORT"
  fi
}

# ---------------------------------------------------------------- the summary

summary() {
  local admin warehouse courier demo store url
  read -r admin warehouse courier demo <<<"$( compose exec -T api python -c \
    'from app import seed; print(seed.ADMIN_PHONE, seed.WAREHOUSE_PHONE, seed.COURIER_PHONE, seed.DEMO_PHONE)' \
    2>/dev/null | tr -d '\r' )"
  [ -n "${admin:-}" ] || read -r admin warehouse courier demo \
    <<<'+998900000001 +998900000002 +998900000003 +998901234567'

  url="$( compose exec -T api printenv MB_DATABASE_URL 2>/dev/null | tr -d '\r' )"
  case "$url" in
    postgresql*|postgres://*) store="$(printf '%-16s%-31s%s' 'Postgres' "localhost:$DB_PORT" '(container minibozor_db)')" ;;
    *)                        store="$(printf '%-16s%-31s%s' 'SQLite' "backend/${url##*/}" '(a file, bind-mounted in)')" ;;
  esac

  cat <<EOF

${B}Everything is up.${N}

  ${B}Interface${N}       ${B}Address${N}                        ${B}Sign in as${N}
  web             http://localhost:$WEB_PORT           admin      $admin
                                                    ombor      $warehouse
                                                    kuryer     $courier
  API + /docs     $API_URL/docs      —
  API health      $API_URL/health    —
  $store

  One web app, not three panels: the same bundle is the office, the bench and
  the van, and the role on the account decides which. The Android and iOS
  clients are the shopping app and talk to this same API, over ${B}adb reverse${N}
  on a handset and http://10.0.2.2:$API_PORT from an emulator.

  ${B}Signing in${N} — every interface uses the same OTP flow. Enter the phone
  number, then the SMS code ${B}123456${N} (dev builds return it in the response).
  The shopper's PIN is 1234. Customer demo account: $demo

  More staff, if you need them:
      ./dev.sh sh api
      python -m tools.make_staff +998900000009 warehouse "Ismi"

  Logs      ./dev.sh logs        (or: logs api / logs web / logs db)
  Status    ./dev.sh status
  Stop      Ctrl+C   (Postgres keeps running; './dev.sh down' stops the rest)

EOF
}

# --------------------------------------------------------------------- status

cmd_status() {
  local failed=0 code detail state health name
  printf '%s%-12s %-34s %-8s %s%s\n' "$B" "SERVICE" "ADDRESS" "STATUS" "DETAIL" "$N"

  # Two daemons are installed here and each has its own containers, so "down"
  # sometimes only means "not on the daemon you are pointed at".
  printf '%-12s %-34s %s%-8s%s %s\n' "daemon" \
    "$(docker context show 2>/dev/null)" "$DIM" "ctx" "$N" \
    "$(docker context inspect -f '{{.Endpoints.docker.Host}}' 2>/dev/null)"

  # What compose thinks, per container, before anything is asked over HTTP —
  # "exited" and "answering 000" are the same line otherwise, and only one of
  # them is worth reading logs for.
  for name in db api web; do
    state="$( compose ps --format '{{.State}}' "$name" 2>/dev/null | head -1 )"
    [ -z "$state" ] && state="not created"
    case "$name" in
      db)  detail="localhost:$DB_PORT" ;;
      api) detail="$API_URL" ;;
      web) detail="http://localhost:$WEB_PORT" ;;
    esac
    if [ "$state" = running ]; then
      printf '%-12s %-34s %s%-8s%s %s\n' "$name" "$detail" "$G" up "$N" "container running"
    else
      printf '%-12s %-34s %s%-8s%s %s\n' "$name" "$detail" "$R" down "$N" "$state"
      failed=1
    fi
  done

  # The API, which is the only one that can say more than "listening".
  local body
  body="$(curl -s --max-time 4 "$API_URL/health" 2>/dev/null)"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "$API_URL/health" 2>/dev/null)"
  [ -z "$code" ] && code=000
  if [ "$code" = "200" ]; then
    detail="$( printf '%s' "$body" | python3 -c '
import json, sys
d = json.load(sys.stdin)["database"]
print("{} at {}, {}ms".format(d["dialect"], d["revision"], d["latency_ms"]))
' 2>/dev/null || echo healthy )"
    printf '%-12s %-34s %s%-8s%s %s\n' "/health" "$API_URL/health" "$G" ok "$N" "$detail"
  else
    printf '%-12s %-34s %s%-8s%s %s\n' "/health" "$API_URL/health" "$R" sick "$N" "HTTP $code"
    failed=1
  fi

  # A Vite dev server has no health endpoint, so the honest check is that it
  # serves its index and that the index is an HTML document — which is what a
  # browser is about to ask for.
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://localhost:$WEB_PORT/" 2>/dev/null)"
  if [ "$code" = "200" ] && curl -s --max-time 4 "http://localhost:$WEB_PORT/" 2>/dev/null | grep -qi '<div id="root"'; then
    printf '%-12s %-34s %s%-8s%s %s\n' "index" "http://localhost:$WEB_PORT" "$G" ok "$N" "serving its index"
  else
    printf '%-12s %-34s %s%-8s%s %s\n' "index" "http://localhost:$WEB_PORT" "$R" sick "$N" "HTTP ${code:-000}"
    failed=1
  fi

  # And the tunnel, because "the phone shows nothing" is almost always this.
  local adb="${ANDROID_HOME:-$HOME/Android/Sdk}/platform-tools/adb"
  if [ -x "$adb" ] && [ "$("$adb" devices 2>/dev/null | grep -cw device || echo 0)" -gt 0 ]; then
    if "$adb" reverse --list 2>/dev/null | grep -q "tcp:$API_PORT"; then
      printf '%-12s %-34s %s%-8s%s %s\n' "phone" "adb reverse :$API_PORT" "$G" up "$N" "the phone reaches the API"
    else
      printf '%-12s %-34s %s%-8s%s %s\n' "phone" "adb reverse :$API_PORT" "$Y" "off" "$N" "run './dev.sh' again, or: adb reverse tcp:$API_PORT tcp:$API_PORT"
    fi
  fi

  return "$failed"
}

# ----------------------------------------------------------------------- main

case "${1:-up}" in
  up|"")
    preflight
    trap cleanup INT TERM EXIT
    bring_up
    summary
    step "Running — Ctrl+C to stop (following the logs)"
    # Holding the terminal on the logs, which is also the supervision: a
    # container that dies says so here, and `restart: unless-stopped` has
    # already tried to bring it back.
    compose logs -f --tail 0 api web
    ;;
  status)
    if cmd_status; then
      printf '\n%sall up%s\n' "$G" "$N"
    else
      printf '\n%ssomething is down%s — ./dev.sh   to start it\n' "$R" "$N"
      exit 1
    fi
    ;;
  down)
    shift
    compose down "$@" && ok "stopped"
    say "${DIM}The database volume is kept. './dev.sh down -v' deletes it too.${N}"
    ;;
  build)
    shift
    # --no-cache is not the default: a dependency change should reinstall, and
    # nothing else in these images changes.
    compose build "$@" && ok "images rebuilt — ./dev.sh to start them"
    ;;
  logs)  shift; compose logs -f --tail 100 "$@" ;;
  # sh, not bash: the web image is alpine and has no bash in it.
  sh)    compose exec "${2:-api}" sh ;;
  ps)    compose ps ;;
  -h|--help|help)
    sed -n '3,12p' "${BASH_SOURCE[0]}" | sed 's/^#\s\?//'
    say ""
    say "Ports, and how to move them:"
    say "  MB_API_PORT=$API_PORT  MB_WEB_PORT=$WEB_PORT  MB_POSTGRES_PORT=$DB_PORT"
    say ""
    say "Configuration is backend/.env, for the containers as well as the host venv."
    say "To run on Postgres instead of the SQLite file, add to it:"
    say "  MB_DOCKER_DATABASE_URL=postgresql+psycopg://minibozor:PASSWORD@db:5432/minibozor"
    ;;
  *) die "Unknown command '$1'. Try: up, status, logs, build, sh, ps, down, --help" ;;
esac
