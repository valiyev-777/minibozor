# Mini Bozor API

FastAPI backend for the Mini Bozor Android and iOS apps. The schema and the
endpoint shapes come straight from the 47-screen design — each screen usually
maps to a single request, and every summary in `/docs` quotes its screen number.

## Run it

Usually you want the whole system rather than this one service — the API, the
three web panels and the database, in the order they depend on each other:

```bash
cd .. && ./dev.sh
```

See the root README. What follows is this service on its own.

```bash
python3 -m venv --without-pip .venv        # this machine has no ensurepip
python3 /path/to/pip.pyz --python .venv/bin/python install -e ".[dev]"
# on a normal machine: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

cp .env.example .env
.venv/bin/alembic upgrade head             # build the schema
.venv/bin/python -m app.seed               # load the design's content
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The `alembic upgrade head` step is not optional and the app will tell you so:
it checks the database is at the newest revision on startup and refuses to run
otherwise. See [Schema changes](#schema-changes).

- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- Product images: <http://localhost:8000/media/products/gazelle.png>

`./run.sh` does the same thing and checks the schema first, so a database that
is behind is a sentence naming the command rather than a stack trace. It also
opens the `adb reverse` tunnel when a device is attached.

`--host 0.0.0.0` matters: the Android emulator reaches the host at
`http://10.0.2.2:8000`, an iOS simulator at `http://localhost:8000`, and a
physical device at your machine's LAN address.

## Schema changes

Alembic owns the schema. `SQLModel.metadata.create_all` — which is what
startup used to call — creates a table that is missing and **never alters one
that exists**, so before this every column change was a hand-written `ALTER`
and nothing compared the result against `models.py`.

That is not a hypothetical. When Alembic went in, this project's own
development database was missing **seven indexes** that `models.py` had
declared for months, including `ix_products_status` on the column that gates
every customer-facing read and `ix_sellers_user_id`, consulted on every
seller-scoped request. `ALTER TABLE ... ADD COLUMN` adds a column and not the
index beside it, and none of the one-off scripts in `tools/` created one. A
fresh install had them. Nothing said the two disagreed.

### Writing one

```bash
# 1. change models.py
# 2. let Alembic read the difference between the models and the database
.venv/bin/alembic revision --autogenerate -m "what you changed"
# 3. read what it wrote — it is a draft, not an answer
# 4. apply it
.venv/bin/alembic upgrade head
```

Always read the generated file. Autogenerate is good at columns, indexes and
constraints and is blind to anything that needs a decision: it renders a
renamed column as a drop and an add, which throws the data away, and it cannot
know that a new `NOT NULL` column needs a value for the rows already there.
Both are ordinary and both are yours to write.

### Running and undoing one

```bash
.venv/bin/alembic current              # what this database is
.venv/bin/alembic history --verbose    # what there is
.venv/bin/alembic upgrade head         # to the newest
.venv/bin/alembic upgrade +1           # one step
.venv/bin/alembic downgrade -1         # back one step
.venv/bin/alembic downgrade base       # back to nothing
.venv/bin/alembic upgrade head --sql   # print the SQL instead of running it
```

A `downgrade` is only as good as the `downgrade()` somebody wrote, and
autogenerate's version drops what `upgrade()` created — which on a table means
the rows in it. Undoing a migration on a database with data in it wants a
backup first, always:

```bash
cp minibozor.db minibozor.db.bak
```

`--sql` is the safe way to see what a migration will do to a database you care
about, and the way to hand a change to somebody else to run.

### The database is checked on startup, and not migrated

The app refuses to start unless the database is at the newest revision, and it
does not migrate for you. The message names both revisions and the command.

Migrating at startup is one line and it is the wrong line. Several processes
start at once — two workers, or a rolling deploy where the old and new replica
overlap — and both run the same DDL; Alembic takes no cross-process lock, so
on SQLite the loser gets "table already exists" or a locked database and on
Postgres two DDL transactions can deadlock, intermittently and under load.
Booting is also not the moment anybody chose to change durable state: a
container an orchestrator restarts at three in the morning is not that moment,
and a batch migration on SQLite is several statements, so one that dies halfway
leaves the schema half-changed and the process dead and unable to say so. And
the runtime credential would need DDL rights for ever.

Starting anyway would be worse than either: a service that answers most
requests and returns 500 from the one endpoint touching the missing column, on
a Tuesday, to a customer.

The reasoning lives with the code in `app.db.require_current_schema`.

### The test that makes this worth having

The suite builds its database with `create_all`, because it is much faster than
replaying the history. On its own that would mean the tests say nothing about
whether the migrations are real — a column added to `models.py` with no
migration written appears on every fresh database, so the suite is green and
the schema in `alembic/versions` is fiction.

So `tests/test_schema.py` builds one database each way, from nothing, and
compares them at the level a database actually has: tables, columns, types,
nullability, indexes, unique constraints, foreign keys.

```bash
.venv/bin/python -m tools.schema_diff                     # both builders
.venv/bin/python -m tools.schema_diff URL_A URL_B         # any two databases
.venv/bin/python -m tools.schema_diff --json URL          # one, as data
.venv/bin/alembic check                                   # Alembic's own opinion
```

If the parity test fails after you touched `models.py`, you forgot step 2
above. There is a second test beside it that holds the comparison to being
able to tell two schemas apart, because a guard that always passes guards
nothing.

### Adopting a database that predates Alembic

```bash
cp minibozor.db minibozor.db.bak
.venv/bin/python -m tools.adopt_alembic            # dry run: what is missing
.venv/bin/python -m tools.adopt_alembic --apply    # create the missing indexes
.venv/bin/alembic stamp head                       # say what it is, run nothing
```

`stamp` writes the revision without executing any migration, which is the
whole point: the database already holds the schema and rebuilding it would
throw away the catalogue, the orders and the sellers in it.

Stamping makes a claim — "this database holds what the baseline builds" — so
`adopt_alembic` checks it first and repairs what it safely can. It creates
missing indexes, which reads a table and writes a new b-tree without moving a
row.

It deliberately leaves one thing: **legacy server defaults**. Eleven columns on
this project's database carry `DEFAULT 0` or `DEFAULT ''` in their DDL that
`models.py` never asked for, because `ALTER TABLE ... ADD COLUMN x NOT NULL
DEFAULT y` is the only form SQLite accepts on a table that already has rows —
the default is an artefact of how the column arrived. Nothing reads it: every
model field carries a Python-side default and SQLModel supplies a value for
every column on every insert. Removing one on SQLite means rebuilding the whole
table — create, copy every row, drop, rename — and there are seven such tables
holding live orders and products. That is real risk for a DDL string nobody
reads, so they stay.

The cost is that `alembic check` lists those eleven on a database adopted this
way. `adopt_alembic` prints the same list, so the two can be compared: anything
`check` reports beyond it is new drift and wants a migration. A database built
by `alembic upgrade head` never has them.

### The `tools/` scripts that came before

`tools/publish_catalogue.py`, `tools/open_stock_ledger.py` and
`tools/adopt_offers.py` were the hand-written migrations. Every column and
table they add is in `alembic/versions/0001_baseline.py`, so their `ALTER` step
finds nothing to do on a current database, and none of them creates tables any
more. They are kept for the half that is not schema and could not be a
migration — deciding that every card predating the `status` column was in the
shop is a judgement about this catalogue, and the stock ledger's opening
balances were read off counts as they stood at a moment that has passed.

## Is it alive

```bash
curl -s localhost:8000/health
```

```json
{"status": "ok", "env": "dev",
 "database": {"reachable": true, "dialect": "sqlite",
              "revision": "0001_baseline", "expected": "0001_baseline",
              "at_head": true, "latency_ms": 0.29}}
```

**200 when it can do its job, 503 when it cannot.** This used to answer
`{"status": "ok"}` from a function that touched nothing, which is the health
check that lies: a process whose database has gone away, or whose credentials
have expired, or which is pointed at a schema it does not expect, answered that
identically to a healthy one. All it proved was that uvicorn accepted the
socket, and the socket was never in doubt.

So it asks the database two cheap questions — `SELECT 1`, which also exercises
the pool's `pool_pre_ping` so a stale socket is found here rather than by the
next customer, and the stamped Alembic revision, one row from a one-row table.
Either failing is a 503, because the caller is a script or a load balancer that
reads the status code and nothing else; a body saying "degraded" behind a 200
is a body nobody reads.

Deliberately not row counts or table lists. This gets polled, and a health
check that slows down as the catalogue grows becomes the thing that takes the
shop down.

`../dev.sh status` reads it, and reports the three web panels beside it.

## Backups and restore

```bash
tools/backup.sh                                     # → ../backups/<dialect>-<stamp>
tools/backup.sh /somewhere/else.db                  # or a path you choose
tools/restore.sh ../backups/sqlite-20260907-173230.db
```

Both read `MB_DATABASE_URL` — the same value the application opens — so they
cannot back up one database while the app writes another, and pointing that
variable elsewhere is how you restore into a scratch copy instead of over your
own.

**SQLite does not go through `cp`.** A copy taken while anything is connected
can be internally inconsistent, because SQLite writes through a journal or a
WAL — and such a file opens cleanly and fails later, on one query, which is the
worst way for a backup to be broken. `Connection.backup` takes a read lock and
copies pages consistently, on a live database.

**Postgres goes through `pg_dump --format=custom`** run inside the container,
so no client needs installing on the host, and the format compresses and can be
restored selectively.

Each verifies what it wrote rather than trusting the byte count — SQLite with
`pragma integrity_check`, Postgres with `pg_restore --list`, which fails on a
truncated dump that a plain redirect can produce silently. A restore saves the
current state to `pre-restore-*` before overwriting anything, asks for
confirmation unless `MB_YES=1`, and afterwards says which revision the restored
database is at, because the schema has just been replaced wholesale.

## Demo account

| | |
|---|---|
| Phone | `+998901234567` |
| SMS code | `123456` (dev builds return it in the `/auth/otp/request` response) |
| PIN | `1234` |

The seeded account owns two addresses, two cards, three orders (one in transit,
one being packed, one delivered), four favourites, a three-line cart, reviews and
notifications — so every screen has something to show.

## Layout

```
app/
  core/config.py      settings (env prefix MB_)
  core/security.py    JWT, argon2 hashing, OTP generation
  db.py               engine + session
  models.py           32 tables
  schemas.py          request/response models
  services.py         serialisation + cart/order rules
  deps.py             auth dependencies
  routers/            13 routers, 60 endpoints
  seed.py             the design's content as data
media/                product photos served at /media
tests/                26 end-to-end tests
```

## Auth

Phone + SMS code, then a JWT pair.

1. `POST /api/v1/auth/otp/request` → in dev the response includes `dev_code`, so
   the apps run with no SMS gateway. Wire a real gateway in `request_otp` before
   shipping and drop `dev_code`.
2. `POST /api/v1/auth/otp/verify` → `{access_token, refresh_token}`. An unknown
   phone number creates the account (`is_new_user: true`).
3. `POST /api/v1/auth/refresh` rotates: a refresh token is single use, and the
   old one is rejected afterwards.

### Two callers, two ways to hold the refresh token

`/auth/verify` also sets the refresh token as a cookie — `mb_refresh`,
HttpOnly, SameSite=Lax, scoped to `/api/v1/auth` — and `/auth/refresh` accepts
it from either place, body first.

The mobile apps go on sending it in the body and their response shape is
unchanged: they have a keychain and no document to inject script into. A
browser has neither, and a refresh token readable from JavaScript is one
successful XSS away from being somebody else's session for the next sixty days.
So the backoffice sends no body at all and lets the cookie do it.

`/auth/logout` clears the cookie along with revoking the tokens.

### CORS

`MB_CORS_ORIGINS` is a comma-separated list of exact origins and defaults to
`http://localhost:5173,http://127.0.0.1:5173` — where the backoffice runs in
dev. A wildcard is *dropped* rather than honoured: the API answers with
credentials, and a browser refuses `Access-Control-Allow-Origin: *` together
with credentials, so `*` would not be permissive — it would be broken, and
broken in the browser's console rather than in ours.

```bash
MB_CORS_ORIGINS=http://localhost:5173,https://ofis.minibozor.uz uvicorn app.main:app
```

## The catalogue belongs to the platform

A seller attaches an offer to a card that already exists; they do not open
their own copy of it. That is the whole point of one card carrying several
offers — a copy per seller duplicates the catalogue and leaves the warehouse
holding the same goods in two places under two names. What a seller *can* do is
propose a card, which lands in moderation.

### A card has a state

| state | what it means |
|---|---|
| `draft` | being written, ours |
| `moderating` | proposed by a seller, waiting on us |
| `published` | in the shop |
| `rejected` | refused, with a reason the seller reads |
| `archived` | withdrawn; the orders that named it survive |

**Customer endpoints show `published` and nothing else.** Every path that
returns a product goes through `services.in_the_shop()` — the listing, the
filter sheet, the product page, similar products, the home rails, the
typeahead and the favourites list — and there is a test that walks all of them.
A basket line for a card that has left the shop stays in the basket and reads
as unavailable rather than disappearing.

Which moves are legal is `transitions.PRODUCT_TRANSITIONS`; a refusal needs a
reason and every move is written to `audit_log`.

### Two lists of the same rows, and why

`GET /categories` and `GET /brands` pass every name through `i18n.t`, which is
right for an app and wrong for the field that writes the source text: an admin
working with the panel in Russian would be shown the translation and save it
back as the Uzbek. So the editor has its own pair —
`GET /staff/catalog/categories` and `GET /staff/catalog/brands` — answering
with the row's own Uzbek whatever `Accept-Language` says, flat rather than a
level at a time, and carrying the counts that explain why a delete was refused.

The shopper's `/brands` now carries a count too. The field was always in the
shape and always nought — the figure was only ever computed in
`/products/filters`, scoped to one listing so the tick-boxes add up to the grid
beside them — and an A-to-Z of marques reading "(0)" against every one of them
tells a shopper nothing. It counts published cards only, through the same
`in_the_shop` narrowing every customer path uses, so tapping a brand opens a
listing of exactly that many. Brands with nothing in the shop are still listed:
the index is a directory, and dropping rows would change what an installed app
is shown.

### Doors

```
admin   POST   /staff/sellers                              take on a seller
admin   PATCH  /staff/sellers/{id}                         edit, stand down, link an account
admin   POST   /staff/catalog/products                     write a card (draft)
seller  POST   /staff/catalog/proposals                    suggest a card (moderating)
seller  GET    /staff/catalog/proposals                    …and what became of it
admin   GET    /staff/catalog/products?status=moderating   the queue
admin   POST   /staff/catalog/products/{id}/status         publish / refuse / withdraw
admin   GET    /staff/catalog/categories | /brands         the editor's lists
admin   POST   /staff/catalog/categories | /brands         …and PATCH, DELETE
admin   POST   /staff/catalog/products/{id}/images         …variants, specs
admin   POST   /staff/showcase/banners | /sections | /promos
admin   POST   /staff/showcase/banners/order               the whole order, one call
```

Three things about a card are **not** in its edit shape, because each has an
owner: the price belongs to an offer, the stock to the movement ledger, and the
status to a decision somebody made with a reason attached. `price` on *create*
seeds the cached figure so a card with no offers has a number to show;
`offers.refresh` overwrites it the moment an offer exists.

A refused card is the half a seller could not read. Approved, it appears in
the shop and they can find it there; refused, it went nowhere they could look
— and the refusal carries the reason they are supposed to act on. So
``GET /staff/catalog/proposals`` answers with the cards *this* seller proposed,
whatever state they are in, ``moderation_note`` filled in on the refusals. The
scoping is not a filter they choose: for a seller those are the only proposals
that exist. An admin has no shop, so they read every seller's, narrowable with
``seller_id``.

Linking an account to a seller grants that user the seller role — there is no
state where an account is attached to a seller and cannot act as one — and the
privilege change is audited. Standing a seller down withdraws their offers with
them.

### Migrating an existing database

```bash
.venv/bin/python -m tools.publish_catalogue          # dry run
.venv/bin/python -m tools.publish_catalogue --apply
```

Adds `status`, `proposed_by_id` and `moderation_note`, then publishes every
card that predates the column — they were all in the shop. The column defaults
to `DRAFT`, matching the model, so nothing written afterwards is published by
accident. Idempotent.

## Staff accounts

Staff sign in through the same OTP flow customers use — the role is the only
difference, so there is no second password store and no second login screen.

**All five at once**, which is what you want before opening the panels:

```bash
.venv/bin/python -m tools.dev_accounts            # what it would do
.venv/bin/python -m tools.dev_accounts --apply    # do it
```

The seed writes a customer and an admin and nothing else, so the operator,
warehouse, courier and seller accounts do not exist until somebody makes them
— which meant three of the five interfaces had nobody to let in, and the way
to find out was to sign in and be refused. This writes the set with fixed
numbers so the walkthrough can name them, is idempotent, never deletes, and
refuses to run unless `MB_ENV` is `dev`: fixed numbers on a fixed OTP code are
publicly known credentials.

**One at a time**, when you know which:

```bash
.venv/bin/python -m tools.make_staff +998900000002 operator "Dilnoza Rasulova"
.venv/bin/python -m tools.make_staff +998900000005 seller "Anvar Qodirov" --seller="Yunusobod Savdo"
.venv/bin/python -m tools.make_staff --list
```

Roles: `customer`, `admin`, `operator`, `warehouse`, `courier`, `seller`. The
seed writes one admin (`+998900000001`).

The three panels that consume these endpoints are
[`../backoffice`](../backoffice), [`../seller`](../seller) and
[`../courier`](../courier); [`../docs/walkthrough.md`](../docs/walkthrough.md)
walks one sale through all of them.

The optional PIN (screens 40–44) is a *local* re-entry lock, hashed with argon2
server-side so it can be verified across devices. It never replaces the JWT.

## The warehouse

Under this model (FBO) the goods sit in our warehouse and the seller owns them.
So the two sides of a shelf answer to different people: **a seller sets the
price, the warehouse sets the count.**

### The shelf is a ledger, not a number

`Offer.stock_left` and `OfferVariant.stock_left` are a running total of
`stock_movements`, and the invariant the tests hold us to is that the column
equals the sum of the ledger. Nothing assigns to a count; everything records a
*difference*, which is also what makes two people working the same shelf at
once safe — the second save adds to the first instead of erasing it.

| kind | where it comes from |
|---|---|
| `opening` | the balance the ledger inherited (written once, by the migration and the seed) |
| `intake` | `POST /staff/supplies/{id}/receive` |
| `sale` | an order paid for — at checkout for a card, at the door for cash |
| `cancel_return` | an order called off, whose goods never left |
| `customer_return` | a refund with `restock: true` |
| `write_off` | `POST /staff/offers/{id}/write-off` |
| `count_adjustment` | a stocktake, or `PUT /staff/offers/{id}/stock` |
| `seller_return` | `POST /staff/removals/{id}/collect` |

Every movement carries a kind, a reason, a person and a cause, so a disputed
count is not an opinion — it is `GET /staff/stock/movements`.

`PUT /staff/offers/{id}/stock` used to *set* the figure. It is now a stocktake
correction: it takes a required `reason` and writes the difference. For a full
recount use a `stock-count`, which snapshots what was expected first so a sale
during the count is not mistaken for a discrepancy.

### A basket line has to name a cell

A product with variants is counted on its **leaves** — the sizes where there
are sizes, the colours otherwise. So `POST /cart/items` requires one:

```
POST /cart/items {"product_id": 1}                      → 422  O'lchamni tanlang
POST /cart/items {"product_id": 1, "color_variant_id": 55} → 422  (the colours have sizes)
POST /cart/items {"product_id": 1, "variant_id": 59}    → 201
```

Not pedantry. A sale that names no leaf comes off the offer's total and off no
colour at all: the ledger still adds up, and the colour figures drift away from
it by exactly that much — permanently, because there is no working out
afterwards which colour the shirt was. Guessing one on the customer's behalf is
the same lie told earlier.

Both apps send a leaf in the ordinary flow. The one case they do not is a
colour whose every size has gone, and there the answer stays **409 out of
stock** — which is the answer they are written to expect. The same rule applies
on the way in: a supply line, a removal line and a write-off all have to name
a cell.

The suite checks two invariants everywhere, side by side
(`_stock_is_consistent()`):

1. an offer's running total equals the sum of its movements;
2. an offer's total equals the sum of its colours, and a colour equals the sum
   of its sizes.

The second is the one that cannot be repaired after the fact, which is why it
is checked rather than trusted.

### Holding

Goods in a basket, on an unpaid order, or picked for a seller to collect are
**held**: still ours to account for, nobody else's to buy. Sellable is the
shelf less what is held, and that is the figure the apps are shown.

Holding is *derived* from the things doing the holding, not stored — so a hold
cannot be leaked, released twice, or left behind by a crash. A basket line
carries `reserved_until` (30 minutes, pushed out whenever the line is touched),
so an abandoned basket stops holding the last one of something without a
sweeper having to notice.

A cash order is not a sale yet: its goods are held from the moment it is placed
and only leave the shelf when it is marked delivered.

### Flows

```
seller declares  POST   /staff/supplies                    → SUP-000123
warehouse counts POST   /staff/supplies/{id}/receive        → intake movements
warehouse counts POST   /staff/stock-counts                 → CNT-000042, expected frozen
                 POST   /staff/stock-counts/{id}/close      → count_adjustment movements
seller asks back POST   /staff/removals                     → RMV-000007
warehouse picks  POST   /staff/removals/{id}/prepare        → ready: held, not sold
seller collects  POST   /staff/removals/{id}/collect        → seller_return movements
anyone reads     GET    /staff/offers/{id}/shelf            → on hand / reserved / sellable
                 GET    /staff/stock/movements              → the ledger
```

The batch code is ours, not the seller's. A seller's own reference belongs to
their system: it may repeat, it may be missing, and two sellers may use the
same one on the same day.

### Migrating an existing database

```bash
.venv/bin/python -m tools.open_stock_ledger          # dry run
.venv/bin/python -m tools.open_stock_ledger --apply
```

Creates the seven warehouse tables, adds `cart_items.reserved_until`, and
writes the opening balances without which the running totals would disagree
with their own ledger before anybody had done anything. Idempotent.

## Paying sellers

```
admin   POST   /staff/payouts/periods                      open a run
admin   POST   /staff/payouts/periods/{id}/generate        work out every account
admin   POST   /staff/payouts/periods/{id}/close           freeze it
admin   POST   /staff/payouts/statements/{id}/pay          the money has left
seller  GET    /staff/payouts/statements                   my accounts, closed ones included
seller  GET    /staff/payouts/current                      how this period is going so far
seller  GET    /staff/payouts/tariffs                      what handling costs, by weight
admin   POST   /staff/payouts/tariffs                      …and PATCH, DELETE
```

### A number a seller reads before it is final says so

`GET /staff/payouts/current` runs the same arithmetic `generate` runs, over the
window covering today, and stores none of it. Its shape carries
`is_final: false` as a constant rather than a flag: a seller shown a figure and
paid a different one has been told the first number was provisional, which
makes every number provisional. It has no id, no lines with ids, and no status
that could become `paid` — the only door that produces a figure somebody is
paid is `close`, and that is an admin's.

Without it, "how is this month going" had no answer at all: `/statements` lists
the runs an admin has generated, so a seller mid-period was told nothing while
their sales, returns and days of storage were all in the database being counted
for them. What it deliberately omits is an adjustment — every other line is
derived from something that happened and can be recomputed at any moment; an
adjustment is a decision somebody wrote onto a statement, and until a statement
exists there is nothing to write it on.

When no run covers today — the last one closed and the next not yet opened,
while the selling carries on — the window is worked out instead: the day after
the last day any period already accounts for, through today. It comes back with
`period_id: null`, because it is not a period and calling it one would invite
somebody to close it.

### The weight bands are global, and that is a decision

A band is a term of a contract, so every change is `PATCH`ed one field at a
time and each field that actually moves writes its own `audit_log` row. "The
2 kg band was edited" is not a fact a seller disputing a charge can act on;
"the fee went from 14 000 to 19 000 on this day, by this person" is.

Two guards, both about ambiguity rather than tidiness. Two bands may not share
a ceiling: `band_for` takes the lightest band that still covers a parcel, so
with two the answer would depend on row order. And the heaviest band cannot be
deleted while a lighter one remains — it is the roof, and deleting it drops
every parcel above the band below into no band at all, handled free, with
nothing to report it.

**Not per seller.** The negotiated lever already exists and is per seller:
`Seller.commission_percent`, a percentage of what the goods are worth. A band
says what a two-kilogram parcel costs *us* to pick, carry and shelve, and that
does not become cheaper because of whose parcel it is. Beyond that, the two
rates on a band freeze differently — the handling fee is snapshotted onto the
order line the day it sells, while the storage rate is read live per period —
so a per-seller copy would need two different freezing rules on one table,
which is how a settlement model starts disagreeing with itself. When a seller
does negotiate handling separately it belongs on a contract row with dates,
read through `settlement.fulfilment_fee` and `settlement.storage_rate`.

**A change to a band never rewrites history.** A closed statement's lines are
frozen rows and a sold order line carries the fee it was sold at, so editing a
band changes what the next parcel is charged and nothing that has been settled.
There is a test that doubles a band a hundredfold between closing one run and
generating the next, and holds the closed one byte-identical while the open one
moves.

## Money and cards

Prices are integers of so'm; formatting (`1 090 000`) belongs to the apps.
Delivery is free from 250 000 so'm, otherwise 19 000 so'm.

`POST /payment-cards` deliberately takes a `processor_token` plus display fields
and never a PAN — collect the card in the payment provider's own SDK or webview
and post back the token. Nothing in this service stores card numbers.

## Tests

```bash
MB_DATABASE_URL="sqlite:///./test.db" .venv/bin/python -m pytest tests -q
```

## Postgres

SQLite for development — no server, and the file is the whole state. Postgres
for production. **One codebase, both databases**, and the suite runs on either.

### Bring it up

```bash
cp .env.example .env                     # then set MB_POSTGRES_PASSWORD
(cd .. && docker compose up -d db)       # Postgres 16, one volume
.venv/bin/uv pip install "psycopg[binary]"   # or: pip install -e ".[postgres]"
```

The database is one service of `../docker-compose.yml`, which is the whole
system — database, API and web app. `../dev.sh` brings all three up; `up -d db`
is the database on its own, for when the API is what you are running from this
venv. There is no compose file in this directory any more: two files declaring
one container named `minibozor_db` is one file too many.

That compose file reads the password from `.env` and does not contain one:
`.env` is gitignored, and a password committed to a repository is a password
for ever — it stays in the history after somebody "changes" it and it is the
same one on every machine that cloned. An unset `MB_POSTGRES_PASSWORD` stops
the container coming up rather than starting one anybody can reach.

The host port is `5434`, not `5432`: those are usually already another
project's, and finding that out by connecting to the wrong database is worse
than picking a free port. Override with `MB_POSTGRES_PORT`.

### Point the app at it

`MB_DATABASE_URL` is the only switch, and everything reads it — the app,
Alembic, the seed, the tools:

```bash
export MB_DATABASE_URL="postgresql+psycopg://minibozor:PASSWORD@localhost:5434/minibozor"
```

`postgresql+psycopg` — psycopg 3, not `psycopg2`. Per command instead, when you
want to leave your shell on SQLite:

```bash
MB_DATABASE_URL="postgresql+psycopg://..." .venv/bin/uvicorn app.main:app --port 8000
```

### Migrate and seed it

Exactly the same commands as on SQLite:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### The suite, on either database

```bash
# SQLite (the default)
rm -f test.db && .venv/bin/python -m pytest tests/ -q

# Postgres — its own database, so a test run cannot touch the dev one
docker exec minibozor_db psql -U minibozor -d postgres \
  -c "drop database if exists minibozor_test" -c "create database minibozor_test"
MB_DATABASE_URL="postgresql+psycopg://minibozor:PASSWORD@localhost:5434/minibozor_test" \
  .venv/bin/python -m pytest tests/ -q
```

Three tests in the suite exist only to hold the two dialects to the same
answer: the Cyrillic search test, the id test, and the column-type round trip.
They are unremarkable on whichever database you happen to be running and are
the point of running on both.

To check that Alembic and `create_all` agree on Postgres as well — the suite
checks it on SQLite, where the question is about the migration scripts rather
than the dialect:

```bash
docker exec minibozor_db psql -U minibozor -d postgres \
  -c "create database pg_createall" -c "create database pg_alembic"
MB_DATABASE_URL=".../pg_createall" .venv/bin/python -c "from app.db import init_db; init_db()"
MB_DATABASE_URL=".../pg_alembic"   .venv/bin/alembic upgrade head
.venv/bin/python -m tools.schema_diff ".../pg_createall" ".../pg_alembic"
```

### What actually differed between the two

Four things, and the interesting ones were silent.

**`lower()` is not the same function.** Every search here is written
`func.lower(column).like(needle)` with the needle lowered in Python, precisely
so that `LIKE`'s own case rules — SQLite ignores ASCII case, Postgres does not
— never come into it. But **SQLite's `lower()` is ASCII-only**:
`lower('Чайники')` is `'Чайники'`, unchanged, while Python's `.lower()` on the
needle is Unicode-aware. So a Russian search compared a mixed-case column
against a lowercase needle and matched *nothing* — on SQLite, which is every
developer's machine, in a shop that sells in three languages. Nothing raised;
no test searching in Latin noticed; and moving to Postgres would have quietly
fixed it, so it would have stayed invisible. `app/db.py` now replaces SQLite's
`lower` (and `upper`) with Python's, per connection, `deterministic=True`. The
nine call sites were already correct and were left alone — what was wrong was
one dialect's implementation of a standard function.

**A sequence is not a rowid.** On SQLite the next id is `max(rowid) + 1`, so
`DELETE FROM` leaves a table numbering from 1 again. A Postgres sequence is an
object of its own and `DELETE` does not touch it, so a second seed numbered the
same catalogue from 63 — same rows, same order, different ids. `reset()` now
uses `TRUNCATE ... RESTART IDENTITY CASCADE` on Postgres, limited to the tables
the models declare so that `alembic_version` survives. Sixteen tests that name
a row by id were the messenger; the real problem is that "reset" which leaves
the counters running is not a reset.

**Enum types outlive their tables.** Every `sa.Enum` is a `VARCHAR` on SQLite
and a real `CREATE TYPE` on Postgres — 24 columns, 21 types. `DROP TABLE` does
not drop the type a column used, so `alembic downgrade base` left all 21
behind and the next `upgrade head` died on `type "userrole" already exists`.
The round trip worked on SQLite and was a dead end on Postgres. The baseline's
`downgrade()` now drops them, guarded on the dialect.

**`render_as_batch` belongs to SQLite only.** SQLite cannot `ALTER` a column,
so batch mode rebuilds the table. Postgres can, and there batch mode is not
merely redundant: the rebuild is reflected from the database, so anything
SQLAlchemy does not reflect faithfully is silently dropped, and a one-line
`ALTER TABLE` becomes a full table copy holding a lock. It now follows the
dialect.

And four that were expected to differ and did not, because of decisions already
in the code: money is `int` so'm with no `Decimal` or `Numeric` anywhere;
every timestamp comes from `models.utcnow()`, which is naive UTC, against
`DateTime` columns with no timezone, so neither database converts anything;
there is no `func.now()` or `server_default` at all, so no clock is the
database's; and the three JSON columns hold lists that are read whole and never
queried into, so generic `JSON` is enough and `JSONB` would buy nothing but a
migration. The column-type round-trip test asserts all of this on whichever
database it runs on.

### Connection pooling

`app/db.py` gives the two dialects opposite settings, because a SQLite
"connection" is a file handle in this process and a Postgres one is a socket to
a server that limits how many it will accept. SQLite gets
`check_same_thread=False` — FastAPI hands a sync request's session across
threads — and `StaticPool` for `:memory:`, where a second connection would be
a second, empty database. Postgres gets `pool_size=5`, `max_overflow=10`,
`pool_recycle=1800` and `pool_pre_ping=True`: the recycle is shorter than
anything upstream that silently drops an idle connection, and the pre-ping
turns a stale socket into a transparent reconnect instead of the first request
after lunch failing.

### Not in this yet

Deploy, CI, backups and monitoring. `../docker-compose.yml` brings up a
database, an API and a web app to develop and test against — with the source
bind-mounted in and `--reload` on. It is not a production topology.
