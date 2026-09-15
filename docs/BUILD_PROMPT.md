# Mini Bozor — rebuild brief (paste this into a fresh Claude Code session)

You are working in `/home/muhammad-sodiq/minibozor`, git branch
`feature/marketplace-back-office`. Read this whole brief before touching a file.
Work in the phases at the bottom, in order, and stop at the end of each phase to
report what you did.

---

## 1. What this project becomes

Mini Bozor stops being a multi-seller marketplace and becomes **one company with
one physical warehouse**.

The business, in one paragraph: the shop owner goes to the wholesale market and
brings back sacks. **Nobody delivers to us — there is no supplier company.** A
sack is mixed: black and white shoes in six sizes in the same bag, with no
labels, no barcodes and no photographs. So the first real step in the warehouse
is *sorting* — open the sack, separate by colour and size, count each pile,
photograph each colour. Only then does the system know what arrived, and only
then do the goods appear in the online catalogue. Each pile gets a barcode label
that **we generate and print**. A worker then carries the goods to a shelf and
records the cell. When a customer orders, the system names the exact cell, in
walk order, so the parcel is assembled fast and handed to a courier.

There are **no sellers**. There is no seller cabinet, no settlement, no payout,
no per-seller offer. Price and stock belong to the product itself.

## 2. What exists today

```
backend/      FastAPI + SQLModel + Alembic. app/ is 18,552 lines, tests/ 8,054,
              190 endpoints, 66 models. Built for the multi-seller model.
design/       imported design: tokens.json, icons.json, per-screen HTML,
              Mobile App.dc.html  — the visual language to follow
shared/       theme.css (design tokens, Tailwind v4) + ui/ (a few components)
android/      Kotlin + Jetpack Compose — the CUSTOMER shopping app
ios/          Swift + SwiftUI — the CUSTOMER shopping app
dev.sh        starts Postgres + API + web apps in dependency order
docs/         this file
```

`backoffice/`, `seller/` and `courier/` were three separate Vite panels. They
have been deleted. They are replaced by **one** web app (see §6).

Environment facts you must not rediscover:

- Python lives in `backend/.venv` — it has `pip` and `uv`. There is no global python.
- Postgres runs via `docker compose up -d db` from the repository root, on host port **5434**.
  Credentials come from `backend/.env` (gitignored).
- `MB_DATABASE_URL` selects SQLite or Postgres; one codebase runs on both.
- The API refuses to start if the Alembic revision is behind head. Keep that.
- Tailwind is **v4** — `@import "tailwindcss"`, CSS-first config, no
  `tailwind.config.js` colour palette.
- There is no `gradlew` and no `java` on PATH, so you cannot build the Android
  app. Do not try. The phone also blocks synthetic input, so you cannot drive it.
- Dev login everywhere: phone number, then SMS code `123456`. Dev builds return
  the code in the response body. No password, no SMS gateway.

## 3. Decisions already made — do not re-litigate these

1. **Single warehouse, no sellers.** Delete `Seller`, `Offer`, `OfferVariant`,
   `SellerStatement`, `StatementLine`, `SettlementPeriod`, `FulfilmentTariff`,
   `app/settlement.py`, `app/offers.py`, `app/routers/payouts.py`,
   `app/routers/listings.py`, `app/routers/cards.py`, and the seller half of
   returns. `price` and `stock` move onto `Product` / `ProductVariant` as real
   columns, not a cache of anything.
2. **The database starts empty.** No demo catalogue, no fake orders. The owner
   will enter real products by hand. Seed only: the warehouse cells (three units
   of 4 × 4 today — from a list, see decision 9), the staging locations, the dev
   accounts, and an empty category tree the owner fills in.
3. **A new Alembic baseline.** Delete the 4 existing revisions and autogenerate
   one initial migration from the new models. Never hand-write an `ALTER`.
4. **We generate the barcodes, and there is no barcode scanning in this build.**
   Market goods arrive with no usable barcode of their own, and the owner's phone
   cameras read codes badly. Every field that takes a code is a **text input**.
   That input must work unchanged when a USB/Bluetooth scanner gun is plugged in
   later: the gun types the code and presses Enter, so listen for Enter and
   submit. Do not add a barcode-scanning library. **Photographs are a different
   matter** — the phone camera is the only source of product photographs there
   will ever be, so the product form takes them through a plain `capture`-enabled
   file input.
5. **One web app, not three panels.** React + TypeScript + Vite + Tailwind v4 +
   shadcn/ui, installable as a PWA, role-based navigation. Works on a phone and
   on a desktop with the same code.
6. **The customer apps stay native.** Do not rewrite `android/` or `ios/`. Only
   adjust their API calls where the contract changed, and say clearly in your
   report which files would need editing since you cannot build them.
7. **Stock is a ledger.** Never assign a stock figure. Every change is a row in
   `stock_movements` recording the difference, with a from-location and a
   to-location. The current figure is derived and the tests must hold the
   invariant that the stored figure equals the sum of the ledger.
8. **An unsorted sack is a draft, not stock.** A `Supply` in `draft` is a sack
   standing in `QABUL` that nobody has opened yet: nothing in it is in the
   catalogue, nothing is sellable, and no movement has been written. Sorting the
   sack *is* filling in the draft's lines, and closing the draft is what brings
   the goods into existence. This exists because the van arrives at nine in the
   evening and sorting five sacks that night is not going to happen — the
   alternative is goods in the building that the system has never heard of.
9. **The shelf units are data, not constants.** 48 cells is where the owner
   starts, not where they end. Racks, columns and rows are rows in the database
   and the shelf map draws whatever is there, so a fourth unit or a second room
   later is a seed change and not a code change. A settings screen for adding
   racks is **not** wanted now — a correct data model and a seed script are.
   Do not write `3`, `4` or `48` as a constant anywhere.
10. **There is no supplier entity.** No supplier table, no contracts, no phone
   numbers — the owner buys at the market themselves. A market run records,
   optionally, *where* it was bought (`Chorsu`, `Ippodrom` — free text with
   autocomplete from previous runs) and, optionally, what the transport cost.
   The buyer is simply the signed-in user. Everything else about cost lives per
   line.
11. **No photograph, no sale.** Market goods arrive with no pictures, so the only
   photographs that will ever exist are the ones taken at the receiving desk. A
   product with no photograph **stays in `draft`**: it is in stock, it sits in a
   cell, it counts towards the figures, and it does **not** reach the customer
   apps. The dashboard names how many products are held back for want of a
   picture and links to the screen that fixes it. A catalogue of grey squares
   sells nothing and makes the whole shop look broken, so this is a rule and not
   a warning.
   **A photograph belongs to a colour, not to a variant.** Two colours × six
   sizes is two pictures, not twelve. Do not ask anyone to photograph a size.
   **Do not add a background-removal library.** The owner shoots against a sheet
   of white paper; that is the decision. `rembg` and friends mean onnxruntime and
   a 150MB model for a problem a 15,000 so'm sheet of paper already solves.

## 4. The domain model

### Locations — the new heart of the system

The old code has no concept of *where* something physically is. That is the
central addition.

The warehouse is **one room with 3 shelf units. Each unit has 4 columns and 4
rows — 16 cells per unit, 48 cells in total.**

Cell codes: `<rack letter>-<column, 2 digits>-<row, 2 digits>`, so `A-01-01`
through `C-04-04`. Row 01 is the **bottom** row (that is how a person reads a
shelf), column 01 is leftmost.

One `Location` table covers both real cells and staging areas:

| kind | code | meaning |
|---|---|---|
| `bin` | `A-01-01` … `C-04-04` | a real shelf cell (48 rows) |
| `receiving` | `QABUL` | just off the van, not yet shelved |
| `packing` | `YIGIM` | picked for an order, waiting for a courier |
| `courier` | `KURYER-<user id>` | in a courier's bag |
| `damaged` | `BRAK` | broken, not sellable |
| `returns` | `QAYTGAN` | came back from a customer, not yet inspected |

Columns: `id, code, kind, rack, column_no, row_no, capacity, is_active, note`.
`rack`/`column_no`/`row_no` are null for the non-`bin` kinds.

**Goods are always in exactly one location.** There is no "unplaced" status
flag — being in `QABUL` *is* the unplaced state, and it is visible, countable
and alertable. Every warehouse operation is a move between two locations:

```
van → QABUL        receipt      (a Supply is closed)
QABUL → A-02-03    putaway      (worker records the cell)
A-02-03 → YIGIM    pick         (an order line is picked)
YIGIM → KURYER-7   handover     (courier takes the parcel)
KURYER-7 → out     delivered
A-02-03 → BRAK     damage
counted difference adjust
```

`StockMovement`: `id, variant_id, from_location_id (null = outside world),
to_location_id (null = left the building), qty, kind, reason, actor_id,
supply_id, order_id, created_at`.

`StockPlacement`: `location_id, variant_id, qty` — unique on the pair. This is
the derived current state and the thing the shelf map reads. It must always
equal the ledger; add a test that proves it.

### How goods are grouped into cells

A cell holds **many variants**. That is not a compromise, it is arithmetic: one
shoe model is 2 colours × 6 sizes = 12 variants, and there are 48 cells, so one
cell per variant would fill the whole room with four models.

The working discipline is **one model per cell** — every colour and every size of
that model together. That fits 48 models in the room, and it leaves a picker
choosing between sizes of one model instead of hunting the room. Small goods
(socks, accessories) share a cell with a divided box. When a model outgrows its
cell it takes a second one, and the system knows both and names the right one in
the pick list.

The software **supports** this and does not enforce it: `StockPlacement` is keyed
by (location, variant), so any mix is representable. What the software must do is
make a mixed cell safe to work in — see the pick screen in §6.

### What `QABUL` means

Sorted goods in `QABUL` **are sellable** — they are in the building, and the pick
list simply tells the picker to fetch them from the receiving area instead of a
shelf. An **unsorted sack is a different thing entirely**: it is a draft supply,
not stock, and nothing in it can be sold because nobody yet knows what it is.

### The rest

- `User` — roles: `admin`, `warehouse`, `courier`, `customer`.
- `Category` (tree), `Brand`.
- `Product` — the card: title (uz/ru), slug, category, brand, description,
  `status` (`draft` | `active` | `archived`), cover image and gallery. `status`
  gates every customer read. A product holds a display price and **no stock of
  its own**. Its images are keyed by **colour**, several per colour with the
  first one the cover, and every variant of that colour shows them; a product
  cannot leave `draft` until every colour it has has at least one image.
- `ProductVariant` — **the unit of stock; everything hangs off this.** Colour and
  size, its own `sku`, its own `barcode`, its own price and its own quantity.
  "Krossovka — 50 dona" is a sentence this system cannot express; "qora / 42 — 3
  dona" is what it stores. A product with no real variation still gets one
  default variant, so stock always has exactly one thing to hang off.
  The product form must generate the **colour × size matrix in one step** — pick
  the colours, pick the sizes, get the variants — because typing twelve variants
  by hand for every shoe model is how a warehouse stops being used.
  A variant's barcode is permanent: when the same goods arrive again the label is
  **reprinted**, never regenerated.
- `Supply` — a **market run**, not a delivery: date, optional place, optional
  transport cost, buyer = the signed-in user, and lines of (variant, qty, unit
  cost). `status` is `draft` — a sack in `QABUL`, unopened, invisible to
  everything else — or `received`. Closing it requires every line to name a real
  variant; it then writes the receipt movements into `QABUL` and flips those
  products to `active`. A closed run cannot be reopened: correct it with an
  adjustment, so the ledger keeps the truth about what was believed at the
  time.
- `PutawayTask` — what is sitting in `QABUL` waiting to be shelved, with age.
- `PickTask` / `PickLine` — per order, each line naming the location to fetch
  from, **sorted in serpentine walk order** (A-01-01 → A-01-02 → … → A-02-04 →
  A-02-03 …) so the picker walks the room once.
- `StockCount` + `StockCountLine` — cell-by-cell recount; the difference becomes
  an `adjust` movement with the counter's name on it.
- `Order`, `OrderItem`, `OrderEvent`, `Address`, `DeliveryRun`.
- Keep as-is: auth/OTP, `app/i18n.py` and the translation table, `app/images.py`,
  `app/idempotency.py`, `app/audit.py`, the order state machine, the courier
  flow, and the holding logic in `app/stock.py` (basket and unpaid-order holds).

Target size: roughly **35 models and ~70 endpoints**, down from 66 and 190. If
you end up near the old numbers, you have kept something you were told to delete.

## 5. The API

Group the routers by who calls them:

- `auth` — request code, verify, refresh, me.
- `catalog` (public) — categories, product list, product detail, search. Reads
  only `status = active`.
- `cart`, `orders`, `addresses`, `profile` (customer) — unchanged in shape.
- `admin/products` — create, edit, publish, archive; image upload; variants;
  price. This is where the owner adds goods.
- `admin/dashboard` — the figures in §6.
- `warehouse/supplies` — start a run (a draft of N unopened sacks), list the
  drafts with their age, fill in a draft's lines while sorting, close it.
- `warehouse/locations` — the map: every location with its contents and fill
  level; one location's contents; a `where-is?` lookup by product or barcode.
- `warehouse/putaway` — what is in `QABUL`; move a quantity to a cell.
- `warehouse/pick` — the queue, claim a task, mark a line picked, complete.
- `warehouse/counts` — start a count of a cell, submit counted figures.
- `warehouse/labels` — the data for a printable label sheet (product labels and
  cell labels).
- `courier` — my tasks, take a task, attempt, deliver, my earnings.

Every mutating warehouse and courier endpoint takes an idempotency key, the way
the existing courier code does.

## 6. The web app

One Vite app at `web/`, port **5173**, `VITE_API_URL` from the environment (do
not compile a hostname in). Update `dev.sh` so it starts this one app instead of
the three that are gone.

Stack: React 19, TypeScript strict, Vite, Tailwind v4, shadcn/ui (add components
with the CLI, into `web/src/components/ui`), TanStack Query for all server
state, React Router, react-hook-form + zod for forms, lucide-react icons,
Recharts for the dashboard, `vite-plugin-pwa` for installability, `jsbarcode` or
`bwip-js` to render printable labels client-side.

Import `shared/theme.css` right after Tailwind and use its tokens — do not
invent new colour names. Follow `design/tokens.json` and `design/icons.json`.

Interface language is **Uzbek**. `Intl` with `uz-UZ` falls back silently and
cannot be trusted here, so format money and dates by hand: `1 250 000 so'm`,
`08.09.2026`, `14:30`. Put those two functions in one file and use them
everywhere.

One login screen. After sign-in the navigation is built from the role:

**admin** — Dashboard, Mahsulotlar, Kategoriyalar, Buyurtmalar, Ombor, Kuryerlar,
Xodimlar, Hisobotlar
**warehouse** — Ombor xaritasi, Qabul, Joylashtirish, Terish, Sanash, Yorliqlar
**courier** — Mening ishlarim, Tarix, Daromad

### The shelf map is the centrepiece

Give this screen real design effort. It is the screen the owner will judge the
whole system by.

- The room, drawn as **three shelf units side by side**, each a 4×4 grid of
  cells. Bottom row at the bottom. Rack letter and column/row numbers labelled
  on the edges, the way a real shelf is labelled.
- Each cell shows its code, how many distinct products and how many units it
  holds, and a fill bar against its capacity. Colour runs from empty through
  comfortable to full — using theme tokens, readable in light and dark, and
  never colour alone (a number or a bar carries the same information).
- Above the racks, the staging areas as their own row of tiles: `QABUL`,
  `YIGIM`, `BRAK`, `QAYTGAN`, and one tile per courier who is holding something.
  A `QABUL` tile with anything older than an hour in it is the one thing on this
  screen that should be impossible to ignore.
- Clicking a cell opens a side sheet listing what is in it, with a "move from
  here" action.
- A search box at the top: type a product name or paste a barcode and the cells
  holding it light up while everything else dims. This is the "find it fast"
  feature the whole warehouse exists for.
- It must be usable on a phone: the three racks stack vertically, cells stay
  tappable, the sheet becomes a bottom sheet.

### The other warehouse screens

- **Qabul** — two stages, because a sack does not always get opened on the day
  it arrives.
  *Stage one, thirty seconds:* how many sacks arrived, the date, optionally where
  from. Saved as a draft. The sacks now stand in `QABUL` and the dashboard starts
  counting their age.
  *Stage two, sorting:* open a draft and record what was actually in the sack.
  The product field **searches existing cards first** — typing "krossovka" shows
  the matching cards with their photographs, and choosing one means entering only
  a quantity and a cost. "Yangi karta" exists but is deliberately the second
  option, because the same goods arriving a second time as a third new card is
  how a catalogue rots. A new card is created inline: name, category,
  colours, sizes, price, and a photograph per colour.
  *The photograph step, which is the one people will skip if you let them:*
  three ways in — the phone camera (a `capture` file input), a file from the
  gallery, and **paste from the clipboard**, because the wholesaler's picture is
  usually already sitting in Telegram and Ctrl+V is the fastest path there is.
  The camera view carries a square guide frame and one line of instruction
  ("oq fonda · bitta tavar · qo'l ko'rinmasin"): consistency across the
  catalogue matters far more than the quality of any single shot, and a guide
  frame is what buys it. Store the result padded to a square on white, on top of
  what `app/images.py` already does. A colour left without a picture keeps the
  product in `draft` — say so on the form, at the moment it happens, naming the
  colour.
  A running total of what the run cost. "Qabul qilish" closes it, prints one
  label per variant, and writes the goods into `QABUL`.
- **Joylashtirish** — the `QABUL` queue, oldest first, with age in plain words
  ("2 soat 10 daqiqa"). Pick a line, type or scan the cell code, confirm. Show
  the cell's current fill before confirming so nobody overfills a cell.
- **Terish** — the pick queue. Open a task and get the lines in walk order. Each
  line leads with the **variant**, not the cell code: the cell is where you walk
  to, but the variant is the thing you must not get wrong. Model first, then
  colour and size in the largest type on the screen, then the cell code, then the
  quantity. If that cell holds more than one variant, say so on the line — a
  picker reaching into a cell of black and white shoes needs to be told to look.
  One tap confirms a line; completing the task hands the parcel over. This is the
  screen where a scanner gun will pay for itself later: the picker scans the item
  and the system refuses the wrong colour.
- **Sanash** — choose a cell, see what the system thinks is in it, type what is
  actually there, submit; the difference is recorded with the counter's name.
- **Yorliqlar** — an A4 label sheet in the browser's print dialog: product
  labels (name, SKU, barcode) and a full set of 48 cell labels with big codes.

### Dashboard

Unsorted sacks and how long they have been standing; today's orders and their
value; sorted goods still waiting in `QABUL` and for how long; cells over 80%
full and cells empty; low-stock variants; products held back from sale for want
of a photograph; couriers out with parcels; last 14 days of sales as one chart;
the variants that move most. Every number
links to the screen where you act on it — a dashboard figure that is not a link
is a dead end.

## 7. Hard rules

- Never assign a stock figure. `move()` records a difference.
- Never hand-write a migration. `alembic revision --autogenerate`, then read
  what it produced before applying it.
- The parity test between the models and the schema stays, and so does the test
  that placements equal the ledger.
- `ruff` clean, line length 100.
- The existing test suite is written against the multi-seller domain. Rewrite it
  against the new one — do not delete tests to make the suite pass, and do not
  leave the suite red at the end of a phase.
- Comments explain **why**, in the voice the existing files use. Do not narrate
  what the line already says.
- Do not add a dependency without saying why in your report. Two are already
  refused: a barcode-scanning library and a background-removal library.

## 8. Phases

Stop and report after each one.

1. **Cut.** Delete the seller/offer/settlement/payout layer and everything that
   only served it, including its tests and schemas. Leave the app importable and
   the remaining tests honest. Report the endpoint and model count before and
   after.
2. **Model.** The new location, placement, movement, supply, putaway, pick and
   count models. Fresh Alembic baseline. Seed the racks from data — three units
   of 4 columns × 4 rows today, so 48 cells, but read from a list and not from a
   constant — plus the staging locations and the dev accounts. Prove the ledger
   invariant with tests, including that a placement equals the sum of its
   movements.
3. **API.** The routers of §5, with the idempotency and audit behaviour the old
   code already had. `/docs` should read like a warehouse, not a marketplace.
4. **Web app skeleton.** `web/` up on 5173, login, role-based shell, theme
   tokens wired, formatting helpers, `dev.sh` updated.
5. **Warehouse screens.** The shelf map first and properly, then qabul,
   joylashtirish, terish, sanash, yorliqlar.
6. **Admin and courier screens.** Products, categories, orders, dashboard,
   courier task screens.
7. **Native apps.** List exactly what in `android/` and `ios/` breaks against
   the new API, and make the source changes you can make without building.

## 8b. What the receiving desk became (2026-09-09, built and walked)

> Parts of this section were superseded on 2026-09-15 — the receiving door,
> the printer and the publishing screen. **§8d is what is true now**; the
> bullets below have been corrected in place where they would otherwise send
> somebody at an endpoint that no longer exists.

The brief above described `Qabul` as two stages with a sorting table. It was
built that way and it had a dead end in it: writing a card needed a category,
the seed writes none, and the warehouse role may read categories but not write
one. It also asked for goods one variant at a time. What replaced it, and what
any further work must not undo:

- **A card can be a stub.** `Product.category_id` is nullable and `price`
  starts at 0. `app.products.unready` names the three gaps — category, price,
  a photograph per colour — and `POST .../status` refuses on all three.
- **`POST /warehouse/receipts` is the receiving door.** One request writes or
  reuses the card, generates the codes, makes the cells for the sizes that
  arrived, and receives the goods into `QABUL`. It does not ask for a cell —
  that is `POST /warehouse/receipts/{id}/shelve`, answered at the shelf (§8d).
- **The vocabulary is learned, not configured.** `GET /warehouse/vocab`
  answers with the kinds, makes, colours and per-kind sizes that have come
  through the door. No vocabulary screen. `+ yangi` writes a brand the first
  time somebody types it, because two black trainers of different makes are
  two cards.
- **`Product.kind`** is the desk's word ("Krossovka"), not the category, and
  it is what the chips are built from. **`Product.snapshot_url`** is the
  identification photograph taken at the bench — never shown to a
  customer; its job is telling two black trainers apart in a search result.
- **The queue of stubs** is the `Rasmsiz` filter on `/mahsulotlar`; the screen
  `/sotuvga-chiqarish` that used to hold it is deleted (§8d). Its count still
  rides in the rail and on the dashboard, linking to
  `/mahsulotlar?status=draft`.
- **Cost is captured at the bench** (`ReceiptIn.unit_cost`, required) and the
  selling price at the desk (`POST .../products/{id}/price`, every cell at
  once). A guessed cost is worse than an empty one: it reaches the profit
  report looking like a fact.
- **The printer arrived** on 2026-09-15: a 58 mm thermal roll, one sticker per
  unit, printed by the receipt itself (§8d). The code format did not change,
  as promised here.
- **Counts add, and nothing saves until submit.** Both were bugs in the screen
  this replaced.

**Walk the flow before reporting a phase done.** Sign in, do the thing, look at
what happens. Every defect in the list above was found that way and none of
them by the test suite, because each phase's tests passed in isolation.

## 8c. The shop window (2026-09-09, the role removed 2026-09-15)

The brief says "no sellers". That still holds for the *marketplace* seller —
`Seller`, offers, settlement, payouts and statements are gone, and a test
proves no such endpoint exists. A `seller` **role** was added here as a shop
assistant; it was deleted on 2026-09-15 (§8d). There is one shop, and the
person who photographs the goods is the person who sells them. What survives
of this section is the part about the card, not the part about who holds it.

- **The bench's business with a card ends when the goods are on a shelf.** The
  warehouse writes the stub through `POST /warehouse/receipts` and may not
  price goods or put them on sale: `deps.CatalogWriter` — **admin only** now —
  guards the price, the words, the specs and the status switch. The bench
  keeps `CatalogReader`, so it still reads categories and hangs the
  identification snapshot.
- **Two lists.** `unready` is refused: a category, a price, a photograph per
  colour. `listing_gaps` is not: a subtitle, a description, a specification
  table, a second photograph. The apps hide a block whose field is empty — no
  description means no description panel rather than an empty one — so a thin
  card looks sparse rather than broken, and this second list is the only thing
  that would ever make somebody finish one.
- `GET`/`PUT .../products/{id}/specs` exist now. The schema was there and the
  door was not: the cabinet that used to call it went with the sellers, and the
  phone had been rendering an empty block ever since.
- Dev accounts: admin `…001`, warehouse `…002`, courier `…003`.

## 8d. Receiving, labelling and publishing rebuilt (2026-09-15)

The desk worked and nobody used it. The full argument is in
`docs/RECEIVING_REBUILD.md`; this is what the code now does, and what further
work must not undo.

- **Receiving is two moments, not two screens.** `POST /warehouse/receipts`
  takes one card, **one colour**, a size→quantity table in the order it was
  typed, and the cost — and writes a `RECEIPT` movement into `QABUL`. No cell
  is asked for at the bench: asking somebody who has not walked anywhere yet
  where they will end up gets a guess, and a guess in the cell field is stock
  in the wrong place. `POST /warehouse/receipts/{id}/shelve` answers that one
  question at the shelf, usually by scanning the cell's own label. A mistyped
  or retired cell is refused and the goods stay in `QABUL`; a receipt already
  shelved answers politely rather than moving anything twice.
- **Nothing is lost between the two moments.** `QABUL` is a `RECEIVING`
  location and `RECEIVING` is in `models.SELLABLE_KINDS`: goods standing there
  can be sold and picked. The cell makes them quick to find, not real.
  `GET /warehouse/receipts/waiting` and the dashboard tile
  `labelled_unshelved` carry the unanswered question across a reload.
- **One sticker per unit, on a 58 mm thermal roll.** The receipt answers with
  its label lines and their `copies`; `web/src/components/label-roll.tsx`
  prints one 58 × 40 mm page per unit, grouped in the order the sizes were
  typed, each numbered `n/copies`. The size is the biggest thing on the
  sticker, the price is not on it at all, and the barcode is the variant's own
  — twenty identical shoes carry twenty identical stickers, because a sticker
  is not a serial number.
- **The warehouse is scanner-first.** `GET /warehouse/scan?code=…` is one
  router for a barcode, a SKU or a cell code and always answers 200 with a
  typed verdict (`variant` / `cell` / `none`) — a zero-stock variant answers
  too, which is why `where-is` could not simply be reused.
  `web/src/components/scan.tsx` is the one component: a document-level
  keyboard-wedge listener for the gun (a focused field always wins) and a
  `BarcodeDetector` camera button for the phone. Manual entry stays on every
  screen: there is one scanner and four people.
- **Publishing lives on the card.** `/sotuvga-chiqarish` is deleted. A card
  that is not on sale opens with one panel in `/mahsulotlar` holding the three
  gates — category, price, a photograph per colour — each editable in place,
  and one button that says what is missing until it is not.
- **`UserRole.SELLER` is gone**, including from the Postgres enum (revision
  `8a32e11a5130` moves any account holding it to admin first, because the type
  cannot simply drop a value).
- **The words `qop`, `pilla` and `saralash` are gone from every screen.** The
  sack was how the goods arrived in the car, not what they are.

## 9. What to ask about

Ask before: adding a dependency not named here, changing the cell code format,
changing the role names, turning the one-model-per-cell discipline into a rule
the software enforces, or deleting anything in `design/`. Everything else in
this brief is decided — build it.
