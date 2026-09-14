#!/usr/bin/env bash
#
# Back up the development database, whichever one it is.
#
#     tools/backup.sh                 # to backups/, named by timestamp
#     tools/backup.sh /somewhere/x    # to a path you choose
#     MB_DATABASE_URL=... tools/backup.sh
#
# Restore with `tools/restore.sh`.
#
# The database is read from MB_DATABASE_URL — the same value the application
# opens — so this cannot back up one database while the app writes another.
#
# ------------------------------------------------------------ why not `cp`
#
# For SQLite, `cp minibozor.db backup.db` is wrong while anything is connected.
# SQLite writes through a journal (or a WAL), so a copy taken mid-transaction
# can be a file that is internally inconsistent — and it will open cleanly and
# fail later, on one query, which is the worst way for a backup to be broken.
# `sqlite3 .backup` (and the Python API this uses) takes a read lock and copies
# pages consistently. It works on a live database, which `cp` only appears to.
#
# For Postgres it is `pg_dump`, run inside the container so no client needs to
# be installed on the host, in the custom format — which compresses, and which
# `pg_restore` can read selectively.

set -euo pipefail
cd "$(dirname "$0")/.."

VENV="./.venv"
PY="$VENV/bin/python"
DB_CONTAINER="${MB_DB_CONTAINER:-minibozor_db}"
STAMP="$(date +%Y%m%d-%H%M%S)"

[ -x "$PY" ] || { echo "No virtualenv at backend/.venv" >&2; exit 1; }

URL="$("$PY" -c 'from app.core.config import settings; print(settings.database_url)')"
[ -n "$URL" ] || { echo "Could not read MB_DATABASE_URL." >&2; exit 1; }

case "$URL" in
  sqlite*)
    SRC="${URL#sqlite:///}"
    SRC="${SRC#./}"
    [ -f "$SRC" ] || { echo "No such database file: $SRC" >&2; exit 1; }
    OUT="${1:-../backups/sqlite-$STAMP.db}"
    mkdir -p "$(dirname "$OUT")"
    # `Connection.backup` is the online backup API: a consistent copy of a
    # database somebody may be writing to, page by page, under a read lock.
    "$PY" - "$SRC" "$OUT" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1], sys.argv[2]
src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
dst = sqlite3.connect(target)
with dst:
    src.backup(dst)
# Read it back through SQLite rather than trusting the byte count: an
# unreadable backup that is the right size is the failure this catches.
rows = sum(
    dst.execute(f'select count(*) from "{t[0]}"').fetchone()[0]
    for t in dst.execute("select name from sqlite_master where type='table'")
)
tables = dst.execute(
    "select count(*) from sqlite_master where type='table'"
).fetchone()[0]
integrity = dst.execute("pragma integrity_check").fetchone()[0]
src.close()
dst.close()
print(f"  tables: {tables}")
print(f"  rows:   {rows}")
print(f"  integrity_check: {integrity}")
if integrity != "ok":
    sys.exit(1)
PY
    echo "  file:   $OUT  ($(du -h "$OUT" | cut -f1))"
    echo "backed up SQLite → $OUT"
    ;;

  postgresql*|postgres://*)
    OUT="${1:-../backups/postgres-$STAMP.dump}"
    mkdir -p "$(dirname "$OUT")"
    # Parsed out of the URL rather than asked for again, so there is one place
    # the credentials live and it is not this file.
    read -r DBUSER DBNAME <<<"$("$PY" - "$URL" <<'PY'
import sys

from sqlalchemy.engine import make_url

u = make_url(sys.argv[1])
print(u.username or "postgres", u.database or "postgres")
PY
)"
    docker exec "$DB_CONTAINER" pg_dump -U "$DBUSER" -d "$DBNAME" \
      --format=custom --no-owner --no-privileges > "$OUT"
    # `pg_restore --list` parses the archive's table of contents, so it fails
    # on a truncated or empty dump — which a plain redirect can produce
    # silently if the container was not running.
    if ! docker exec -i "$DB_CONTAINER" pg_restore --list < "$OUT" > /dev/null 2>&1; then
      echo "The dump is not readable by pg_restore. Removing it." >&2
      rm -f "$OUT"
      exit 1
    fi
    TABLES="$(docker exec -i "$DB_CONTAINER" pg_restore --list < "$OUT" \
      | grep -c 'TABLE DATA' || true)"
    echo "  tables with data: $TABLES"
    echo "  file:   $OUT  ($(du -h "$OUT" | cut -f1))"
    echo "backed up Postgres → $OUT"
    ;;

  *)
    echo "Don't know how to back up $URL" >&2
    exit 1
    ;;
esac
