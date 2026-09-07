# Mini Bozor · Backoffice

Vite + React + TypeScript + Tailwind. Talks to the existing FastAPI backend in
`../backend` over its JSON API — there is no second backend and no second ORM,
because the business logic (`transitions.py`, `inventory.py`, `offers.py`,
`audit.py`) lives in FastAPI and a second model layer over the same database
would mean writing every schema change twice.

Three panels so far, in one application:

- **Operator** — returns, review moderation, order status, delivery windows.
- **Warehouse** — the shelf, incoming batches, stocktakes, removals, and the
  movement ledger.
- **Admin** — moderation, the catalogue, sellers, roles, the shop window, the
  card editor (a product's words in three languages, its photographs, its
  colour/size tree and its spec table), and the finance screens: payout runs,
  each seller's account, and what the fees are.

The sidebar is drawn from the signed-in role, so an operator sees the queues, a
warehouse hand sees the shelves, and an admin sees all three — with headings,
which appear only when more than one job is on screen. Two more are planned
(seller, and a courier app), so most of what is in `src/components` exists to
be shared rather than to serve one panel.

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

The panel refuses anybody whose role is not `operator`, `warehouse` or
`admin`, and says which role it found rather than showing an empty screen.

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

## Conventions the next two panels should keep

- **`src/components/DataTable.tsx`** — the one table. Sorting, paging, the
  empty state and the loading skeleton are settled there; a page contributes
  only its columns. It handles both paging shapes the API uses: pass `server`
  for an endpoint that answers with a `Page`, nothing for one that answers with
  a list.
- **`src/components/ConfirmDialog.tsx`** — the one confirmation. Anything
  irreversible goes through it, and a decision's own fields go in as
  `children`, so there is one dialog rather than one per verb.
- **`src/lib/utils.ts` → `mediaSrc`** — the one place a relative media path
  becomes a URL. The API answers with `products/x.png` or `uploads/<uuid>.webp`
  and never a whole URL, because it does not know how a client reaches it;
  every client prefixes its own base.
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
- **`src/components/SortableList.tsx`** — rows arranged by dragging. Pointer
  events, not HTML5 drag-and-drop: `draggable`/`dragstart` does nothing under a
  finger and cannot be driven by synthesised mouse events, so the one
  interaction on the showcase screen would be the one thing untestable. Every
  row also carries up/down buttons, because a list that can only be dragged
  cannot be rearranged with a keyboard at all.
- **`src/components/ui/tabs.tsx`** — sections inside one screen, with no
  routing. The showcase is three tables and the catalogue is three more; a
  sidebar row each would turn a menu of nine into a menu of fifteen. The
  sidebar is for finding the *area* you work in.
- **An order goes as a whole.** `POST .../order` takes every id and answers 400
  to a list that repeats or omits one. So an arrangement is held locally while
  somebody is making it and sent in one request when they save — never a
  request per row, which could be left half applied. Until Save the shop keeps
  the old order, and the panel says so.
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

## The card editor

`src/pages/ProductEditPage.tsx` and `src/pages/product/`. Five decisions in it
are worth keeping.

- **Three languages, one form.** A language switcher, not three forms or three
  columns: they are one card said three ways, and the thing an editor does
  most is read the Uzbek while typing the Russian. The Uzbek lives on the row;
  Russian and English live in the `translation` table and ride along in the
  same PATCH. A blank translation is never marked as an error — it is what the
  fallback is for, and the empty field shows the Uzbek as its placeholder so
  what the app will actually display is visible without switching tabs.
- **Creating and editing are different screens.** A photograph, a colour and a
  spec row all hang off an id. The new-card form takes only what `POST
  /staff/catalog/products` accepts and then redirects into the full editor;
  holding a whole card in the browser to replay on save would mean a
  half-failed replay leaves a card in a state nobody chose.
- **The guards come from the API.** `GET .../variants` answers with
  `can_delete`, `can_add_size` and the sentence for each, produced by the same
  functions the write endpoints refuse with. So a greyed-out button and a 409
  are one rule rather than two copies of it. Re-deriving "a variant with
  movements cannot be deleted" in TypeScript would be the copy that goes stale.
- **What is not on the form is named on the form.** Price, stock and status
  each have an owner that is not this screen — an offer, the movement ledger,
  a moderation decision. The `Elsewhere` panel says where each one lives and
  shows the current value, because an editor who finds a blank space goes
  hunting through five tabs for a field that was never going to be there.
- **The seller's form is not this form.** A seller proposes cards through
  `POST /staff/catalog/proposals`, is not staff, and never reaches this panel;
  their editor will live in a seller's own account. Nothing here is abstracted
  to serve both yet — what a seller needs is not known, and generalising now
  would be guessing.

## The finance screens

`src/pages/PayoutsPage.tsx`, `src/pages/payout/` and
`src/pages/StatementPage.tsx`. Every figure on them is money somebody is paid,
which changes how they are built.

- **Nothing is rounded, ever.** The API answers in whole so'm and each figure
  goes through `money()` untouched — `toLocaleString` only groups an integer.
  `signedMoney()` writes the sign as a word rather than leaving a minus glyph
  to read as a dash at 12px: a deduction and a credit share one column, and
  they have to be distinguishable at a glance.
- **Amounts are `tabular` and right-aligned**, so a column of them can be
  scanned by shape instead of read digit by digit.
- **The invariant is shown, not hidden.** `StatementPage` adds the lines up
  itself and prints the sum beside the total. The backend holds that they are
  equal; a page that only printed `payable` could not tell anybody when that
  stopped being true, so when they disagree it says so and says not to pay.
- **The irreversible buttons are not where a hand lands.** Closing sits apart
  from the repeatable Generate beside it; paying and correcting live in the
  page header, away from the rows a cursor travels over. Every confirmation
  repeats the sum, and the close dialog says in plain words what freezing
  does to a late refund.
- **Every line names its source** — order line, return, offer — because
  "9 100 000" is a number to argue with and its composition is an account to
  read. That column is the reason the screen exists.
- **A negative payable is coloured and named.** A period of refunds and
  storage against no sales means the seller owes us; a debt shown in the same
  ink as a credit is a debt nobody notices.

## Endpoints the panel wants and the API does not have

- **Editing the weight bands.** `GET /staff/payouts/tariffs` is the only door
  on to `fulfilment_tariffs` — there is no POST, PATCH or DELETE. So the
  Tariflar tab is read-only and says so on the screen rather than offering a
  form that could not save. The two rates on a band are contract terms, so
  editing them probably wants an audit row and per-seller overrides, which is
  a stage of its own.
- **Storage rate constants.** `STORAGE_PER_UNIT_DAY`, `STALE_AFTER_DAYS` and
  `STALE_MULTIPLIER` live in `app/settlement.py` and are not exposed at all,
  so the panel cannot show the surcharge rule beside the storage lines it
  explains. The line's own note spells the arithmetic out instead.

## Endpoints added for it

The catalogue list could be read-only against what already existed. Editing
could not, and four of these were not in the plan:

- `GET /staff/catalog/categories`, `.../brands` — the rows' own Uzbek, plus
  the counts that explain a refused delete. The customer endpoints translate
  as they go, which would have an editor working in Russian save the
  translation back as the source.
- `GET /staff/catalog/summary` — how many cards sit in each state, for the
  sidebar badge, so the queue is not downloaded to render an integer.
- `GET /staff/catalog/products/{id}` now answers with the description, the
  flags and the translations — the list shape stays lean.
- `GET .../images` — the gallery **with ids**. `DELETE .../images/{image_id}`
  had always existed and nothing ever told the panel what `image_id` was.
- `PUT .../images/order` — the whole list at once, like the showcase. The
  first photograph is the cover.
- `GET .../variants` — the tree with the two guards on it.
- `GET .../specs` — with ids and translations. The table is only ever replaced
  whole, so a form that could not read the Russian back would delete it by
  saving an unrelated row.

## Scripts

| | |
|---|---|
| `npm run dev` | Vite dev server on :5173 |
| `npm run build` | `tsc -b` in strict mode, then a production bundle |
| `npm run lint` | types only, no emit |
| `npm run gen` | regenerate `src/api/schema.d.ts` from the API |
