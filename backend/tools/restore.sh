#!/usr/bin/env bash
#
# Put a backup back.
#
#     tools/restore.sh ../backups/sqlite-20260907-181500.db
#     tools/restore.sh ../backups/postgres-20260907-181500.dump
#     MB_DATABASE_URL=... tools/restore.sh <file>        # somewhere else
#
# Restoring destroys what is there now, so it asks — unless MB_YES=1, which is
# for scripts that have already decided.
#
# It also takes its own backup of the current state first, into
# `backups/pre-restore-*`. A restore is the operation people reach for when
# something has gone wrong, and reaching for it with the wrong file is exactly
# the mistake that then has nothing to go back to.
#
# The destination is MB_DATABASE_URL, not a path in the backup: a dump does not
# get to decide which database it lands in. To restore into a scratch copy
# rather than over your own, point that variable somewhere else — which is what
# the proof in the README does.

set -euo pipefail
cd "$(dirname "$0")/.."

VENV="./.venv"
PY="$VENV/bin/python"
DB_CONTAINER="${MB_DB_CONTAINER:-minibozor_db}"
STAMP="$(date +%Y%m%d-%H%M%S)"

FILE="${1:-}"
[ -n "$FILE" ] || { echo "Usage: tools/restore.sh <backup file>" >&2; exit 2; }
[ -f "$FILE" ] || { echo "No such file: $FILE" >&2; exit 1; }
[ -x "$PY" ] || { echo "No virtualenv at backend/.venv" >&2; exit 1; }

URL="$("$PY" -c 'from app.core.config import settings; print(settings.database_url)')"

confirm() {
  [ -n "${MB_YES:-}" ] && return 0
  echo "About to overwrite:"
  echo "    $1"
  echo "with:"
  echo "    $FILE"
  printf 'Type yes to continue: '
  read -r answer
  [ "$answer" = "yes" ] || { echo "Stopped."; exit 1; }
}

case "$URL" in
  sqlite*)
    DEST="${URL#sqlite:///}"
    DEST="${DEST#./}"
    confirm "$DEST"

    if [ -f "$DEST" ]; then
      mkdir -p ../backups
      SAFETY="../backups/pre-restore-$STAMP.db"
      cp "$DEST" "$SAFETY"
      echo "  current state saved to $SAFETY"
    fi

    # Restored through SQLite's own backup API in the other direction, rather
    # than `cp`: it replaces the pages of the destination in place, so a
    # process holding the file open ends up with the restored data instead of
    # a deleted inode it is still reading from.
    "$PY" - "$FILE" "$DEST" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1], sys.argv[2]
src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
if src.execute("pragma integrity_check").fetchone()[0] != "ok":
    print("  the backup fails integrity_check — refusing", file=sys.stderr)
    sys.exit(1)
dst = sqlite3.connect(target)
with dst:
    src.backup(dst)
rows = sum(
    dst.execute(f'select count(*) from "{t[0]}"').fetchone()[0]
    for t in dst.execute("select name from sqlite_master where type='table'")
)
print(f"  restored {rows} rows")
src.close()
dst.close()
PY
    echo "restored SQLite ← $FILE"
    ;;

  postgresql*|postgres://*)
    read -r DBUSER DBNAME <<<"$("$PY" - "$URL" <<'PY'
import sys

from sqlalchemy.engine import make_url

u = make_url(sys.argv[1])
print(u.username or "postgres", u.database or "postgres")
PY
)"
    confirm "$DBNAME on $DB_CONTAINER"

    mkdir -p ../backups
    SAFETY="../backups/pre-restore-$STAMP.dump"
    if docker exec "$DB_CONTAINER" pg_dump -U "$DBUSER" -d "$DBNAME" \
         --format=custom --no-owner --no-privileges > "$SAFETY" 2>/dev/null; then
      echo "  current state saved to $SAFETY"
    else
      rm -f "$SAFETY"
      echo "  (nothing to save — the database is empty or absent)"
    fi

    # `--clean --if-exists` drops what the dump is about to recreate. Without
    # `--if-exists` the drops of objects that are not there are errors, and the
    # restore ends in a wall of them with the data loaded anyway — which reads
    # like a failure and is not one.
    docker exec -i "$DB_CONTAINER" pg_restore -U "$DBUSER" -d "$DBNAME" \
      --clean --if-exists --no-owner --no-privileges < "$FILE"
    echo "restored Postgres ← $FILE"
    ;;

  *)
    echo "Don't know how to restore into $URL" >&2
    exit 1
    ;;
esac

# The schema has just been replaced wholesale, so what the application will
# make of it is worth knowing now rather than at the next boot.
if REV="$("$PY" -c '
import sys

from app.db import require_current_schema

try:
    print(require_current_schema())
except RuntimeError as error:
    print(error, file=sys.stderr)
    sys.exit(1)
' 2>&1)"; then
  echo "  schema at $REV — the application will start against this"
else
  echo
  echo "$REV"
  echo
  echo "  The restored database is not at the revision this checkout expects."
  echo "  That is what the backup held; bring it forward with:"
  echo "      .venv/bin/alembic upgrade head"
fi
