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

Three of the four gaps this cabinet opened with were closed in the backend
stage before this one — `GET /staff/sellers/me`, `GET /staff/catalog/browse`
and `.../browse/{id}` with the variant leaves on it. What is still missing:

- **A sales figure for the current period.** The dashboard deliberately
  leaves it out. It lives in a `SellerStatement`, which only exists once an
  admin generates the period, and computing an approximation here from order
  lines would put a number on screen that disagrees with the one the seller
  is paid against. Better a missing figure than two that differ. Something
  like `GET /staff/payouts/current` — sales so far this open period, labelled
  provisional — would fill it honestly.
- **A seller's own proposals.** `POST /staff/catalog/proposals` works and the
  response carries the card as submitted, but nothing lists a seller's
  proposals afterwards: `GET /staff/catalog/products` is admin-only and
  `/staff/catalog/browse` shows published cards only. So an **approved**
  proposal turns up in the catalogue by itself and can be priced, while a
  **refused** one is invisible from here — including its `moderation_note`,
  which is the sentence written for the seller to read. The submit dialog
  says so rather than pretending. `GET /staff/catalog/proposals` scoped to
  the caller would close it.

## Screens

| | |
|---|---|
| **Boshqaruv** | Four figures and two lists, all of them work to do. |
| **Katalog** | A grid of photographs: search, category, and "mine / not yet mine". Where a seller finds something to sell and prices it. |
| **Takliflarim** | Price and struck-through price. Stock is shown and locked — see below. |
| **Qoldiq** | On hand, held, sellable, at colour and size level, with the movement ledger. |
| **Partiyalar** | Declare a batch; declared against counted once received. |
| **Hisobotlar** | One period's account and every line that adds up to it. |

`Hisobotlar` detail is the one screen here built as a table rather than
cards, and deliberately: every other screen is read by recognising things,
that one by comparing figures down a column. Same rigour as the backoffice's,
for the same reason — nothing rounded, every line names its source, and the
sum of the lines is printed beside the total so the invariant is checkable
rather than trusted.

## Scripts

| | |
|---|---|
| `npm run dev` | Vite dev server on :5174 |
| `npm run build` | `tsc -b` in strict mode, then a production bundle |
| `npm run lint` | types only, no emit |
| `npm run gen` | regenerate `src/api/schema.d.ts` from the API |
