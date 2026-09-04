# Mini Bozor · Backoffice

Vite + React + TypeScript + Tailwind. Talks to the existing FastAPI backend in
`../backend` over its JSON API — there is no second backend and no second ORM,
because the business logic (`transitions.py`, `inventory.py`, `offers.py`,
`audit.py`) lives in FastAPI and a second model layer over the same database
would mean writing every schema change twice.

Two panels so far, in one application:

- **Operator** — returns, review moderation, order status, delivery windows.
- **Warehouse** — the shelf, incoming batches, stocktakes, removals, and the
  movement ledger.

The sidebar is drawn from the signed-in role, so an operator sees the queues, a
warehouse hand sees the shelves, and an admin sees both. Three more are planned
(admin, seller, and a courier app), so most of what is in `src/components`
exists to be shared rather than to serve one panel.

## Running it

```sh
# 1. the API, from the repo root
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# 2. an account with a role, if there isn't one yet
.venv/bin/python -m tools.make_staff +998900000002 operator "Dilnoza Rasulova"
.venv/bin/python -m tools.make_staff --list

# 3. the panel
cd ../backoffice
npm install
npm run dev            # http://localhost:5173
```

Sign in with the phone number and the SMS code. In dev the code is always
`123456` and the login screen shows it, because `/auth/otp/request` echoes it
back when `MB_ENV=dev`.

The panel refuses anybody whose role is not `operator` or `admin`, and says
which role it found rather than showing an empty screen.

### Why the port matters

The API answers with credentials — the refresh cookie rides on them — and a
browser refuses `Access-Control-Allow-Origin: *` together with credentials. So
the backend names its origins instead (`MB_CORS_ORIGINS`, defaulting to
`http://localhost:5173`), and Vite is pinned to that port. Serving the panel
somewhere else means adding that origin:

```sh
MB_CORS_ORIGINS=http://localhost:5173,https://ofis.minibozor.uz uvicorn app.main:app
```

There is deliberately no dev proxy. A proxy would make everything same-origin
in dev and leave the cross-origin problem to be discovered in production.

## Regenerating the API client

`src/api/schema.d.ts` is generated from the backend's own OpenAPI document.
Nothing in it is hand-written, so when a field moves the build says so instead
of a screen quietly rendering `undefined`.

```sh
# with the API running on :8000
npm run gen

# or against another instance
MB_API_URL=https://api.minibozor.uz npm run gen
```

`src/api/types.ts` only gives the generated shapes shorter names. If a
regeneration breaks it, the backend changed something and the panel needs to
follow — that is the point.

## Conventions the next four panels should keep

- **`src/components/DataTable.tsx`** — the one table. Sorting, paging, the
  empty state and the loading skeleton are settled there; a page contributes
  only its columns. It handles both paging shapes the API uses: pass `server`
  for an endpoint that answers with a `Page`, nothing for one that answers with
  a list.
- **`src/components/ConfirmDialog.tsx`** — the one confirmation. Anything
  irreversible goes through it, and a decision's own fields go in as
  `children`, so there is one dialog rather than one per verb.
- **`src/lib/mutate.ts`** — the one way a change is sent, and the one way a
  failure is shown. The backend answers 403, 409 and 422 with a specific,
  already-translated sentence; it goes straight into the toast. There is no
  "something went wrong" anywhere in this codebase, and adding one would
  replace an answer with a shrug.
- **`src/components/Layout.tsx`** — the sidebar is data. A `NavItem` carries
  the roles it belongs to, so a new panel adds rows rather than forking the
  layout.
- **Never re-derive backend rules.** Buttons come from `next_statuses` on the
  response, which the backend builds from `app/transitions.py`. `src/lib/labels.ts`
  translates status *names* and nothing else — an illegal move is refused by
  the API with a 409 and an explanation, which is what the operator sees.
- **The access token stays in memory.** Not `localStorage`: it is short-lived
  and recovered on load from the HttpOnly refresh cookie, which this code
  cannot read and never tries to.
- **Dense and plain.** An operator sees hundreds of rows a day. The mobile
  app's design system is not reused — that product is looked at, this one is
  worked in.

## The warehouse floor is a different room

The operator's panel is read at a desk. The warehouse one is read on a tablet
held at arm's length by somebody wearing gloves and holding a scanner. That is
a different set of constraints, not a different design system: same tokens,
same `DataTable`, same `ConfirmDialog`.

- **`<Page floor>`** turns on warehouse density — bigger type, taller rows —
  with three CSS rules in `index.css`. Nothing is built twice.
- **`size="lg"`** on `Button` is the gloved-thumb target.
- **`ScanInput`** (`src/components/ui/scan.tsx`) is the whole scanner
  integration. A barcode scanner is a keyboard that types fast and presses
  Enter, so there is no API to talk to — there is one requirement, and it is
  that the caret is already in the field when the trigger is pulled. It takes
  focus and keeps taking it back: on blur, on a click anywhere in the panel,
  and when the window comes forward. A scan that lands on the page instead of
  in the field is a line silently not counted.
- **`CountStepper`** is a quantity a thumb can drive, with a numeric keyboard.
- A scan that matches nothing says so. There are no per-variant barcodes in
  this model, so a scan identifies the *product* — where a batch has two sizes
  of it, the panel says "several lines, choose one" rather than guessing.

The receive and count screens keep the declared or expected figure beside the
count with the difference between them, live. A discrepancy is worth seeing
while somebody is still standing in front of the shelf and can go and look
again; reading it afterwards in a report is too late to be useful.

## Scripts

| | |
|---|---|
| `npm run dev` | Vite dev server on :5173 |
| `npm run build` | `tsc -b` in strict mode, then a production bundle |
| `npm run lint` | types only, no emit |
| `npm run gen` | regenerate `src/api/schema.d.ts` from the API |
