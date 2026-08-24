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

The optional PIN (screens 40–44) is a *local* re-entry lock, hashed with argon2
server-side so it can be verified across devices. It never replaces the JWT.

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
