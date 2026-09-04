# Mini Bozor API

FastAPI backend for the Mini Bozor Android and iOS apps. The schema and the
endpoint shapes come straight from the 47-screen design — each screen usually
maps to a single request, and every summary in `/docs` quotes its screen number.

## Run it

```bash
python3 -m venv --without-pip .venv        # this machine has no ensurepip
python3 /path/to/pip.pyz --python .venv/bin/python install -e ".[dev]"
# on a normal machine: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

cp .env.example .env
.venv/bin/python -m app.seed               # load the design's content
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- Product images: <http://localhost:8000/media/products/gazelle.png>

`--host 0.0.0.0` matters: the Android emulator reaches the host at
`http://10.0.2.2:8000`, an iOS simulator at `http://localhost:8000`, and a
physical device at your machine's LAN address.

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

## Staff accounts

Staff sign in through the same OTP flow customers use — the role is the only
difference, so there is no second password store and no second login screen.

```bash
.venv/bin/python -m tools.make_staff +998900000002 operator "Dilnoza Rasulova"
.venv/bin/python -m tools.make_staff +998900000005 seller "Anvar Qodirov" --seller="Yunusobod Savdo"
.venv/bin/python -m tools.make_staff --list
```

Roles: `customer`, `admin`, `operator`, `warehouse`, `courier`, `seller`. The
seed writes one admin (`+998900000001`).

The backoffice that consumes these endpoints is in [`../backoffice`](../backoffice).

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

```bash
.venv/bin/pip install "psycopg[binary]"
export MB_DATABASE_URL="postgresql+psycopg://minibozor:minibozor@localhost:5432/minibozor"
```

Tables are created on startup. Add Alembic before the first production deploy —
`SQLModel.metadata.create_all` will not migrate an existing schema.
