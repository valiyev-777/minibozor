# Mini Bozor

**One company with one warehouse.** The owner goes to the wholesale market and
brings back sacks; somebody opens them, sorts by colour and size, counts each
pile, photographs each colour and puts it on a shelf. The system's whole job is
to know what arrived, where it is, and how to fetch it again.

It was a multi-seller marketplace until September 2026. There are no sellers
now, no offers, no settlements and no payouts: price and stock belong to the
product, and the catalogue belongs to the company.

```
design/       the imported design + extracted tokens, icons and per-screen HTML
backend/      FastAPI + SQLModel + Alembic — one API, runs on SQLite and Postgres
web/          one React app for the office, the warehouse bench and the van
shared/       theme.css — the design tokens both the web app and the panels used
android/      Kotlin + Jetpack Compose — the customer's shopping app
ios/          Swift + SwiftUI — the customer's shopping app
docs/         BUILD_PROMPT.md — the brief this rebuild is written against
```

## Run the whole thing

```bash
./dev.sh
```

That is Postgres (if configured), the API and the web app, in dependency
order, with a health check on each and one address list at the end. `Ctrl+C`
stops everything it started.

```bash
./dev.sh status     # is everything alive? one line per service
./dev.sh down       # stop whatever is still holding our ports
./dev.sh --help     # and how to move the ports
```

The seed writes one account per role, so there is somebody to let in on a
fresh database.

### Where everything is, and who signs in

| Interface | Address | Role | Phone |
|---|---|---|---|
| API + `/docs` | <http://localhost:8000/docs> | — | — |
| API health | <http://localhost:8000/health> | — | — |
| **web** | <http://localhost:5173> | admin | `+998900000001` |
| | | warehouse | `+998900000002` |
| | | courier | `+998900000003` |
| **shopper app** | Android Studio / Xcode | customer | `+998901234567` |
| Postgres | `localhost:5434` | — | see `backend/.env` |

One bundle, three jobs: the role on the account decides the navigation, the
density and which screens exist. There is no separate panel per role any more,
because three panels built in three sessions is three design systems.

Every interface signs in the same way: the phone number, then the SMS code
**123456**. There is no password and no second login screen — the role on the
account is the only difference between them. The shopper's optional PIN is
`1234`. Dev builds return the code in the response, so no SMS gateway is
involved.

The Android and iOS debug builds point at this same API — `10.0.2.2:8000` from
an emulator, `localhost:8000` from a simulator, and `backend/run.sh` opens the
`adb reverse` tunnel for a physical phone.

### One service at a time

```bash
cd backend && ./run.sh                       # just the API, with adb reverse
cd web && npm run dev                        # just the web app
```

`./dev.sh` exists because the order matters: the backend checks its schema
revision on startup and refuses to run if the database is behind, so Postgres
has to be up and migrated before uvicorn is launched.

## The design as source of truth

`design/` holds the imported project plus three things the apps read from:

| File | What it is |
|---|---|
| `design/tokens.json` | colours, type scale, radii, spacing, component metrics |
| `design/icons.json` | the 30 glyphs as SVG path data on a 24×24 grid |
| `design/screens/*.html` | each of the 47 screens, split out for reference |

Both apps generate their icon sets from `icons.json` and mirror `tokens.json` in
their design layer, so a change in the design has one obvious place to land.

### Product photography

**The only photographs that will ever exist are the ones taken at the receiving
desk.** Market goods arrive with no pictures, so a card is written and then
photographed against a sheet of white paper while the sack is being sorted —
which is why a product with a colour that has no picture stays in `draft` and
never reaches the shopping app. A catalogue of grey squares sells nothing.

The design's own product photos are still in `backend/media/products/` and are
used by nothing: the database starts empty and the owner enters real goods.

## Backups

The development database, whichever it is — the scripts read `MB_DATABASE_URL`
and pick SQLite or Postgres from it:

```bash
cd backend
tools/backup.sh                                    # → backups/<dialect>-<stamp>
tools/restore.sh ../backups/sqlite-20260907-173230.db
```

Backing up SQLite goes through its online-backup API rather than `cp`: a copy
taken while anything is connected can be a file that opens cleanly and fails
later, on one query. Postgres goes through `pg_dump --format=custom` inside the
container, so nothing has to be installed on the host. Both verify what they
wrote — `integrity_check` for SQLite, `pg_restore --list` for Postgres — and a
restore takes its own `pre-restore-*` copy first, because a restore is what
people reach for when something has already gone wrong.

`backups/` is gitignored: it holds the real catalogue and real orders.

## Status

The rebuild is running against [`docs/BUILD_PROMPT.md`](docs/BUILD_PROMPT.md),
in phases.

| Piece | State |
|---|---|
| Design extraction | Complete — tokens, icons, 47 screens, assets |
| Backend | 134 endpoints (71 of them back-office), 42 tables, Alembic, SQLite and Postgres, 90 tests passing |
| Warehouse model | Locations, placements and a ledger of moves; racks are seed data, not constants |
| web | Skeleton: login, role-based shell, theme and formatting. The screens are phases 5 and 6 |
| Android | 82 Kotlin files, not yet compiled; the API contract has moved under it |
| iOS | 60 Swift files, not yet compiled; the same |

Neither mobile client has been compiled: this machine has no JDK, Android SDK
or Swift toolchain, so the first build has to happen on a machine that does.
What in them breaks against the new API is phase 7 of the brief.
