# Mini Bozor — receiving, labelling, publishing: rebuild brief

> **O'zbekcha, qisqa.** Bozordan 20 ta oq oyoq kiyim keldi. Men aytaman: *oq,
> 43 dan 10 ta, 42 dan 10 ta*. Tizim menga **yopishtirish uchun 20 ta yorliq**
> chiqaradi va **qaysi yacheykaga** qo'yishni so'raydi. Men qo'yaman —
> **o'sha zahoti ombor xaritasida ko'rinadi**. Tamom. "Qop", "pilla",
> "saralash" degan so'zlar yo'qoladi.
>
> Sotuvchi roli **o'chiriladi**. Telefon do'koniga chiqarish kartaning o'zida,
> uch qadamda: rasm, narx, kategoriya. Ombor **skaner bilan** ishlaydi: har
> ekranda yorliqni o'qitsang, o'sha narsa topiladi.

Paste this whole file into a fresh session. Read it all before touching a
file. The agent split is at the bottom — **§9**; run the waves in order.

Repo: `/home/muhammad-sodiq/minibozor`, branch `feature/one-warehouse-shop`.
Stack, conventions and the design system: see `docs/BUILD_PROMPT.md` §2–§4 and
the `backoffice-design` skill. Nothing about the ledger changes: stock is still
a ledger of moves, placements still equal the ledger, money still never moves
goods.

---

## 1. Why this is being redone

The receiving desk works and nobody wants to use it. Three complaints, all
true:

1. **The vocabulary is wrong.** The screen is built around a *sack* (`qop`,
   `pile`): open it, sort it, count each pile. The owner does not think in
   sacks. He thinks: *I bought twenty white shoes, ten in 43 and ten in 42.*
   The sack is how the goods arrived in the car, not what they are.

2. **The labels are somewhere else.** Booking goods in and printing the
   stickers that go on them are the same minute of work, and they are two
   screens (`/qabul`, then `/yorliqlar`). Worse, the sheet prints **one label
   per variant row** — so twenty shoes produce two stickers, and the person
   holding twenty shoes has to work out that they need to print the page ten
   times.

3. **The goods do not appear.** "Omborda ko'rinmayapti." After a receipt the
   screen congratulates you and the shelf map is somewhere else entirely.
   Nothing carries you from *what I just booked in* to *where it now is*.

And publishing is worse than all three: a separate screen, owned by a role
(`seller`) that the shop does not actually have, with the photographs, the
price and the filing spread across three panels.

**So the old paths come out.** This is not a patch on `/qabul` — the screen is
2,388 lines and most of it is machinery for a model we are dropping. Delete
what the new flow does not need.

---

## 2. The new receiving flow — one screen, three answers, a sheet

```
   Nima keldi?            Nechta?                  Qayerga?
   ┌───────────────┐      ┌──────────────────┐     ┌────────────────┐
   │ Oyoq kiyim    │      │  43  ▸ 10        │     │  B-01-02       │
   │ Oq            │  →   │  42  ▸ 10        │  →  │  (taklif)      │
   │ Nike          │      │  + o'lcham       │     │  yoki skanerla │
   └───────────────┘      └──────────────────┘     └────────────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────────┐
                    │  20 ta yorliq — chop etish       │
                    │  B-01-02 · ombor xaritasida ko'r │
                    └──────────────────────────────────┘
```

### 2.1 What the three answers mean

**Nima keldi** identifies *one card*. Either an existing card — found by
typing, or **by scanning a label that is already on a shoe** — or a new one
written here from kind + colour + brand. Unchanged from today except that
scanning is now a way in.

**Nechta** is a size→quantity table and nothing else. `43 → 10`, `42 → 10`.
Each row is a variant; the row is what makes "10 ta oq 43" a different product
from "10 ta oq 42". A kind the shop has only ever received without sizes (a
cap, a bag) shows one box and no size column — that rule already exists and
stays.

**Qayerga** is one cell, and it is **required**. Suggested from where this
model already lives, accepted by typing or **by scanning the cell's own
label**.

### 2.2 What comes out

One `POST`, and then the screen shows **the thing you wanted**:

- a sheet of **one sticker per unit** — twenty shoes, twenty stickers, in one
  print — ready to print without leaving the screen;
- the cell, as a link into the shelf map, with the goods already in it;
- one line of plain confirmation: `20 dona · B-01-02 · 2 400 000 so'm`.

### 2.3 What disappears

- the words `qop`, `pile`, `saralash` from every screen and label;
- `/yorliqlar` as the *only* way to print goods labels — the screen stays for
  reprints and for cell labels, but receiving prints its own sheet;
- the unopened-sack panel and the two-stage supply flow on this screen. The
  `supplies` table stays (it is the market run and the cost lives on it) but
  it is written *by* the receipt, never edited by hand.

---

## 3. Labels

A label is stuck on **one physical item**. Today's sheet is one row per
variant; it needs a count.

- `GET /warehouse/labels` gains `copies` per label, and the sheet repeats each
  label that many times. Receiving asks for the quantities it just booked.
- The barcode is the variant's own, permanent, never regenerated — that rule
  does not change. Twenty stickers carry the **same** barcode, because twenty
  identical shoes are twenty of one thing.
- The A4 layout must fit a common sticker sheet. Pick one and say which in a
  comment: 65 labels (38×21 mm, 5×13) is the usual one in this market.
- Printing must work from a phone browser too — the bench is a phone.

---

## 4. The warehouse becomes scanner-first

One component, one behaviour, every warehouse screen.

- A **scan target** that is always listening on `/qabul`, `/ombor`, `/terish`,
  `/sanash`. A barcode scanner is a keyboard: it types fast and ends with
  Enter. So: capture keystrokes that arrive faster than a human types, buffer
  them, act on Enter. No focused input required, and typing into a real field
  must still work — if an input has focus, the field wins.
- **One router for what was scanned.** A variant barcode, a SKU or a cell code
  all arrive as a string; `GET /warehouse/scan?code=…` answers what it is and
  what can be done with it. The screen decides what to do with the answer:
  - `/qabul` — a variant fills in the card; a cell fills in the destination.
  - `/ombor` — anything jumps the map to it and opens its panel.
  - `/terish` — a variant confirms the line being picked; a wrong one refuses
    loudly.
  - `/sanash` — a variant adds one to the counted quantity of its row.
- Manual entry stays everywhere. There is one scanner and four people.

`GET /warehouse/find` already resolves a name, a SKU or a barcode; the new
endpoint should reuse it rather than grow a second search.

---

## 5. Publishing — inside the card, three gates, no role

### 5.1 The seller role is deleted

`UserRole.SELLER` goes. Everything it guarded becomes the admin's:

- `deps.CatalogWriter` → admin only; `CatalogReader` keeps warehouse + admin.
- `OrderViewer` / `OrderMover` lose `SELLER`.
- `nav.ts`: the `SELLER` menu, `homeFor`, `densityFor`, `canReach`.
- `web/src/pages/staff.tsx` and `people.tsx`: the role list.
- `seed.py`: `SELLER_PHONE` and the seeded account.
- An Alembic revision for the enum (Postgres enums do not drop a value — the
  existing revision `3b4d3d7fc68b` added it; write the reverse properly, and
  move any account that holds the role to `admin` first).
- `docs/`, the Walleo pages and `dev.sh`'s sign-in table mention it — fix the
  ones in this repo; the Walleo pages are handled separately.

Anyone who can open the catalogue can publish. There is one shop and the
person who photographs the goods is the person who sells them.

### 5.2 The screen

`/sotuvga-chiqarish` is **deleted** (`web/src/pages/publish.tsx`, 392 lines).
Its job moves onto the product card in `/mahsulotlar`, which is where somebody
already is when they notice a card is not on sale.

A card that is not on sale shows **one panel at the top**, not three, and the
panel contains exactly what is missing:

```
  Do'konga chiqarish                            [ Chiqarish ]  ← disabled
  ─────────────────────────────────────────────────────────────
  ✓ Kategoriya   Oyoq kiyim ▾
  ✗ Narx         [ 240 000 ]  ← tannarx 150 000, +60% taklif
  ✗ Rasm         Qora ✓   Oq ✗  ← har rangga bitta
```

- Each gate is **editable in place**. No navigation, no second screen.
- The button enables the moment the three are satisfied, and says what is
  missing while it is not.
- The catalogue list keeps its `Rasmsiz` filter; the dashboard tile keeps
  linking to `/mahsulotlar?status=draft`.

### 5.3 Photographs must be easy

This is the part that is "juda noqulay" today and it is worth real work:

- **One photo per colour**, presented as a row of colour tiles: a tile with a
  photo shows it, a tile without shows a dashed camera box. Tap a tile →
  camera / file / paste, and it is done.
- On a phone, `<input type="file" accept="image/*" capture="environment">` —
  the camera opens directly; no upload dialog.
- Paste (`Ctrl+V`) anywhere on the panel attaches to the selected colour.
- Drag and drop a file onto a tile.
- Show the upload as it happens and replace the tile the moment it lands; a
  photograph that appears three seconds later reads as a failure.
- A colour with no photograph is still not published — that rule stays, and
  the reason is written on the tile rather than in a paragraph.

---

## 6. Rules that do not change

Do not "simplify" any of these away:

1. Stock is a ledger. Receiving writes one `RECEIPT` movement into the named
   cell. `StockPlacement` must equal the sum of movements; the suite asserts
   it after every operation.
2. Colour and size are two fields. Never one glued string.
3. One card is sized **or** sizeless, never both.
4. `xl` and `XL` are one size — tidied at every door that writes a variant.
5. A variant's barcode and SKU are permanent.
6. Three gates for the shop window: category, price, a photo **per colour**.
7. Idempotency keys on every warehouse write.
8. Every figure the office reads is defined once, on the server.

---

## 7. Acceptance — how we know it is done

Walk it, do not assume it. With `./dev.sh` up and the demo catalogue seeded:

1. As the warehouse user, receive **20 white shoes, 10×43 and 10×42**, into
   `B-01-02`, in one screen, without typing a size twice.
2. The screen then offers **20 stickers** — count them on the sheet — and a
   link to `B-01-02`.
3. Follow the link: the shelf map shows the goods in that cell.
4. Scan one of those barcodes on `/ombor`: the map jumps to `B-01-02`.
5. Scan the same barcode on `/qabul`: the card is filled in.
6. As the admin, open the new card in `/mahsulotlar`: one panel, three gates.
   Add a photo for each colour from a phone camera, set a price, pick a
   category, press one button. The card is on sale.
7. There is no `seller` anywhere: not in the menu, not in the staff role list,
   not in the enum, not in `dev.sh`'s table.
8. `pytest -q` green, `npm run lint` and `npm run build` clean.
9. The words `qop`, `pilla` and `saralash` appear nowhere on screen.

---

## 8. What to delete

Deleting is part of the job. When these are gone the diff is finished:

- `web/src/pages/publish.tsx`
- the sack/pile machinery in `web/src/pages/qabul.tsx` (the file should end up
  a fraction of its 2,388 lines)
- `UserRole.SELLER` and everything that names it
- `POST /warehouse/supplies` as a hand-driven flow, if nothing else uses it
  after the rewrite — check before removing; the market run still carries the
  transport cost

---

## 9. The agent split

Explicit file ownership. **No two agents in the same wave touch the same
file.** Each agent reports what it changed and stops.

### Wave 0 — recon (1 agent, read-only)

Read and report, change nothing:

- how `/qabul`, `publish.tsx`, `labels.tsx` and `warehouse.py` work today;
- every place `SELLER` is named (backend, web, docs, dev.sh, seed);
- what `GET /warehouse/labels` and `GET /warehouse/find` return;
- which tests cover receiving, publishing and roles.

Output: a list of files with line numbers, and anything in §1–§8 that is
already true or that the code contradicts. **Do not start Wave 1 until this
report is in** — the numbers in this brief were measured on 2026-09-14 and
the point of the recon is to catch what has moved.

### Wave 1 — backend (3 agents, parallel)

| Agent | Owns | Job |
| --- | --- | --- |
| **B1 · receiving** | `app/routers/warehouse.py`, `app/products.py`, `app/schemas.py` (pile/receipt section) | The receipt endpoint in the new shape: card + size×quantity + required cell → movements, supply row, and the label lines with their counts. Keep idempotency. |
| **B2 · labels + scan** | `app/routers/shelves.py`, `app/schemas.py` (label/scan section) | `copies` on labels; `GET /warehouse/scan`; reuse `find`. |
| **B3 · roles** | `app/models.py`, `app/deps.py`, `app/roles.py`, `app/seed.py`, `app/routers/admin.py`, `app/routers/staff.py`, `app/routers/dashboard.py`, `alembic/versions/*` | Delete `SELLER`. Move any account holding it to `admin` in the migration. |

`app/schemas.py` is shared: **B1 owns the pile/receipt classes, B2 owns the
label/scan classes**, and neither touches the other's. If that proves
impossible, B1 goes first and B2 rebases.

Tests: each agent writes its own in `backend/tests/test_api.py` — **append
only, at the end of the file**, and run the whole suite before reporting.

### Wave 2 — web (3 agents, parallel; starts when Wave 1 is green)

| Agent | Owns | Job |
| --- | --- | --- |
| **W1 · receiving screen** | `web/src/pages/qabul.tsx`, `web/src/lib/queries.ts` (receipt hooks) | §2, top to bottom. Delete the sack machinery. |
| **W2 · publishing** | `web/src/pages/products.tsx`, `web/src/components/card-editor.tsx`, `web/src/components/photo-step.tsx`, delete `web/src/pages/publish.tsx`, `web/src/App.tsx`, `web/src/lib/nav.ts` | §5.2 and §5.3. |
| **W3 · scan + labels** | `web/src/components/scan.tsx` (new), `web/src/pages/labels.tsx`, `web/src/pages/shelf-map.tsx`, `web/src/pages/counts.tsx`, `web/src/pages/picking.tsx` | §3 and §4. |

`queries.ts` is shared: **W1 owns the receipt hooks, W3 owns the scan and
label hooks, W2 owns the catalogue hooks.** Add hooks at the end of their own
section; do not reformat the file.

### Wave 3 — one agent, serial

Walk §7 in a browser against the running stack, fix what fails, update
`docs/BUILD_PROMPT.md` and the `backoffice-design` skill if a rule changed,
and commit.

### House rules for every agent

- The design system is not optional: no hex, no Tailwind palette colour, no
  pixel height for a control. Load the `backoffice-design` skill first.
- Uzbek on screen, English in comments. `Intl` is never used for formatting.
- A comment says **why**, not what. Do not narrate the code.
- Never hand-write an `ALTER`; autogenerate the Alembic revision.
- Run `pytest -q`, `npm run lint`, `npm run build` before reporting.
- If this brief and the code disagree, **say so** rather than guessing.
