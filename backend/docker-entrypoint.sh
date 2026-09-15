#!/usr/bin/env bash
# What has to be true before uvicorn is allowed to start, done in the container
# instead of in the script that launches it.
#
# The ordering problem the old host script solved by hand — Postgres accepting
# connections, then the schema at head, then the server — is the same problem
# here; the difference is that compose already knows how to wait for a healthy
# database (`depends_on`), so all that is left is the schema.
#
#   MB_NO_MIGRATE=1   start the server without touching the schema
#   MB_NO_SEED=1      never write the demo accounts, even into an empty database
set -euo pipefail

say() { printf '  [entrypoint] %s\n' "$*"; }

url="${MB_DATABASE_URL:-sqlite:///./minibozor.db}"
say "database: ${url%%:*}  (${url})"

# A Postgres URL means the `db` service, and compose is told to hold this
# container until that one is healthy — but a health check that has just gone
# green and a server ready for *our* connection are a second apart on a first
# boot, so the connection is what gets waited on, not the status.
case "$url" in
  postgresql*|postgres://*)
    deadline=$(( SECONDS + 60 ))
    until python - <<'PY' 2>/dev/null
import os
import sqlalchemy

sqlalchemy.create_engine(os.environ["MB_DATABASE_URL"]).connect().close()
PY
    do
      if [ "$SECONDS" -ge "$deadline" ]; then
        say "Postgres did not accept a connection in 60s — giving up."
        exit 1
      fi
      sleep 1
    done
    say "Postgres is accepting connections"
    ;;
esac

# The schema. `alembic upgrade head` is a no-op on a database already at head,
# which is the normal case, and is the whole fix on a fresh one — so it runs
# every time rather than being a thing you are told to go and do.
if [ -z "${MB_NO_MIGRATE:-}" ]; then
  say "alembic upgrade head"
  alembic upgrade head
else
  say "MB_NO_MIGRATE=1 — leaving the schema alone"
fi

# And somebody to sign in as. Only ever into a database with no users in it:
# this must not be able to touch a database that is in use.
if [ -z "${MB_NO_SEED:-}" ]; then
  if python - <<'PY'
import sys

from sqlmodel import Session, func, select

from app.db import engine
from app.models import User

with Session(engine) as session:
    sys.exit(0 if session.exec(select(func.count()).select_from(User)).one() == 0 else 1)
PY
  then
    say "no users in this database — seeding the demo accounts"
    python -m app.seed
  fi
fi

exec "$@"
