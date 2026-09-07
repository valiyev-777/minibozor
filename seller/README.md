# Mini Bozor · Sotuvchi kabineti

Vite + React + TypeScript + Tailwind. Talks to the FastAPI backend in
`../backend` over the same JSON API the backoffice uses.

## Why this is its own project

A seller is not staff. They are an outside user on their own hostname, and the
backoffice's code — moderation queues, other sellers' payouts, role
assignment — has no business being downloaded into their browser. Splitting
`backoffice/` by role would not achieve that: the bundle is still one bundle,
and a role check in React is a hint, not a boundary.

So: two applications, two builds, two deployments. Each generates its own
OpenAPI client and owns its own auth flow.

**Nothing is shared as a package, on purpose.** `api/client.ts`,
`lib/mutate.ts` and a handful of primitives began as copies of the
backoffice's. Setting up a monorepo workspace, a build step and a version for
two applications costs more than the two hundred lines it would save, and the
two are expected to diverge — this one is growing a seller's concerns and that
one an operator's. When a copy drifts, that is the design working.

## Running it

```sh
# 1. the API. It must name this origin: it answers with credentials (the
#    refresh cookie rides on them) and a browser refuses a wildcard together
#    with credentials.
cd backend
MB_CORS_ORIGINS=http://localhost:5173,http://localhost:5174 \
  .venv/bin/python -m uvicorn app.main:app --reload --port 8000

# 2. a seller: a `sellers` row with an account pointed at it. An admin does
#    this from the backoffice — Sotuvchilar → Hisob bog'lash — and linking is
#    what gives the account the SELLER role.

# 3. the cabinet
cd ../seller
npm install
npm run dev            # http://localhost:5174
```

Sign in with the phone number and the SMS code. In dev the code is always
`123456` and the login screen shows it, because `/auth/otp/request` echoes it
back when `MB_ENV=dev`.

**Only `seller` gets in.** An admin is turned away as firmly as a customer,
and told to use the backoffice — an admin signing in here would be looking at
a seller's account through a door built for the seller, without the audit
trail the backoffice writes when staff touch somebody's money.

> In dev both apps sit on `localhost`, so they share the refresh cookie: sign
> in to the backoffice and this app will resume that session and refuse it by
> role. That is the guard working, and it does not happen in production where
> the two have different hostnames.

## Regenerating the API client

`src/api/schema.d.ts` comes out of the backend's own OpenAPI document. Nothing
in it is hand-written, so when a field moves the build says so instead of a
screen quietly rendering `undefined`.

```sh
npm run gen                                   # against :8000
MB_API_URL=https://api.minibozor.uz npm run gen
```

`src/api/types.ts` names only the shapes a seller can actually reach. The
document describes a hundred and thirty endpoints, most of them an operator's
or an admin's, and listing them all would invite a screen that calls one and
puts a 403 in front of somebody.

## Conventions

- **Cards, not one big table.** The backoffice has a single `DataTable` and
  every screen contributes columns; right for somebody scanning hundreds of
  rows a day. A seller has a dozen offers and three batches, and for that many
  a row is the worse shape — status has to be a colour they see, not a word in
  the fifth column. `components/Card.tsx` holds `Panel`, `Row`, `Figure` and
  the loading/failed/empty states.
- **Bigger than the tool next door.** 15px base against the backoffice's 13,
  40px buttons against 28, and the answer to each screen's question set in
  `.figure`. Read a few times a week, sometimes on a phone, by somebody who
  does not do this all day.
- **Money is never rounded.** The API answers in whole so'm and `money()` only
  groups it. Amounts carry `.tabular` so a column can be compared by shape.
- **The backend's sentence is the error message.** `lib/mutate.ts` puts the
  API's own text in the toast. There is no "something went wrong" here; on the
  screen where somebody reads their own money a shrug is worse than silence.
- **Never re-derive a backend rule.** Which offer wins the shop comes from
  `is_winner`; what a supply may do next comes from its status and a 409 with
  an explanation. A copy of those rules in this codebase would be the copy
  that goes stale.
- **The access token stays in memory**, recovered on load from the HttpOnly
  refresh cookie this code cannot read and never tries to.

## The one thing a seller may not touch

Stock. `Offer.stock_left` is the sum of the warehouse's movement ledger, and a
seller who could type into it would be promising goods nobody has received.

The screens say so rather than showing a disabled box: the count carries a
padlock, `OffersPage` explains in a sentence where the number comes from and
what to do instead, the price dialog repeats it where somebody would go
looking, and `StockPage` shows the ledger — because a count that looks wrong
should be answerable with a list of movements rather than an argument.

## Endpoints this needs and the API does not have

Each of these is a screen or a figure that is missing rather than approximated.

- **`GET /staff/sellers/me`** — a seller cannot learn their own shop's name,
  commission rate or contact details. `/staff/me` answers with the *user*
  (phone, role) and nothing about the `sellers` row behind it, so the header
  greets a phone number and the cabinet cannot show "Chorsu Bozori · 8%
  komissiya". A brand-new seller with no offers yet has no way at all to
  confirm they are linked to the right shop.
- **A sales figure for the current period.** The dashboard deliberately leaves
  this out. It lives in a `SellerStatement`, which only exists once an admin
  generates the period, and computing an approximation here from order lines
  would put a number on screen that disagrees with the one the seller is paid
  against. Better a missing figure than two that differ. Something like
  `GET /staff/payouts/current` — sales so far this open period, unfrozen and
  labelled as provisional — would fill it honestly.
- **`GET /staff/catalog/products`** for sellers, or a narrower search.
  Creating an offer means naming a `product_id`, and the catalogue listing is
  admin-only. So this build has no "add an offer" screen at all: a seller can
  edit the offers an admin made for them and cannot make one. Proposing a
  *new* product works (`POST /staff/catalog/proposals`) but that is a
  different act.
- **`variant_ids` guidance on `POST /staff/offers`.** An offer on a product
  with colours must name every leaf, and there is no endpoint a seller can
  call to find out what the leaves are.

## What is not built yet

Items 5 and 6 of this stage, deliberately left for their own session because
each is independent of the four here:

- **Hisobotlar** — the seller's own statements and their lines. The endpoints
  exist and are already scoped to the caller (`GET /staff/payouts/statements`,
  `.../statements/{id}`), so this is a screen with no backend work. It needs
  the same rigour as the backoffice's: nothing rounded, and the sum of the
  lines shown beside the total.
- **Mahsulot taklif qilish** — `POST /staff/catalog/proposals`, plus showing
  `moderation_note` when a proposal comes back refused. Needs a category and
  brand list a seller can read; see the gap above.

## Scripts

| | |
|---|---|
| `npm run dev` | Vite dev server on :5174 |
| `npm run build` | `tsc -b` in strict mode, then a production bundle |
| `npm run lint` | types only, no emit |
| `npm run gen` | regenerate `src/api/schema.d.ts` from the API |
