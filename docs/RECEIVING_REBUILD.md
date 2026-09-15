# Mini Bozor — receiving, labelling, publishing: rebuild brief

> **O'zbekcha, qisqa.** Bozordan 20 ta oq oyoq kiyim keldi. Stolda aytaman:
> *oq, 43 dan 10 ta, 42 dan 10 ta* — va **Qabul** bosaman. Tizim darhol
> **20 ta yorliq** chiqaradi: 10 tasida 43, 10 tasida 42, o'sha tartibda.
> Har bittasiga yopishtiraman, javonga olib boraman va **yacheyka yorlig'ini
> skanerlayman** — tamom, o'sha zahoti ombor xaritasida ko'rinadi.
>
> Ya'ni yacheyka **oxirida** so'raladi, javon oldida turganda — stolda emas.
> "Qop", "pilla", "saralash" degan so'zlar yo'qoladi.
>
> **Qaror qilingani:** yorliq **58 mm termal printerda**, har dona uchun
> bittadan; skaner sifatida **qurol ham, telefon kamerasi ham**; bitta qabul —
> **bitta rang** (oq va qora kelsa, ikki marta kiritiladi); yorliqsiz qabul
> yo'q.
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

## 0. Decisions already taken — do not re-open these

The owner answered these on 2026-09-14. An agent that finds them inconvenient
should say so and stop, not choose differently.

| | Decision | Consequence |
| --- | --- | --- |
| Printer | **58 mm thermal**, one label per page | No A4 sheet module. `@page` is 58 × 40 mm |
| Labels | **One per unit, always** | No "label-less" receipt, no per-box label |
| Scanner | **Gun *and* phone camera** | Keyboard-wedge listener + `BarcodeDetector` |
| Colour | **One colour per receipt** | The multi-colour row comes out of the screen |
| Cell | **Asked last**, at the shelf | Two moments, one screen (§2) |
| Role | **`seller` is deleted** | Publishing is the admin's (§5) |

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

## 2. The new receiving flow — two moments, in the order the body moves

The owner described the motion, and it is not the motion the screen asks for:

> *Men tavarni olib keldim, shuncha deb kiritsam — nechta tavarim bo'lsa
> shuncha qog'oz chiqarib bersa, men har bittasiga yopishtirib, keyin omborga
> oborib qo'yaman.*

Enter → **paper** → stick → carry → put away. The cell is the **last** thing
that happens, and it happens at the shelf, not at the table. Asking for it
first — as the old screen and the first draft of this brief both did — is
asking somebody who has not walked anywhere yet where they are going to end
up. They guess, and a guess in the cell field is stock in the wrong place.

So: **one submission, two moments, one screen that stays open between them.**

```
   ┌── Moment 1 · stolda ───────────────────────────────────────┐
   │                                                            │
   │   Nima keldi?           Nechta?                            │
   │   ┌──────────────┐      ┌───────────────┐                  │
   │   │ Oyoq kiyim   │      │  43  ▸  10    │   →  [ Qabul ]   │
   │   │ Oq · Nike    │      │  42  ▸  10    │                  │
   │   └──────────────┘      └───────────────┘                  │
   │                                ↓                           │
   │              20 ta yorliq — chop etish 🖨                   │
   └────────────────────────────────────────────────────────────┘
                                    ↓  yopishtiradi, javonga olib boradi
   ┌── Moment 2 · javon oldida ─────────────────────────────────┐
   │                                                            │
   │   20 dona · yorliqlangan · javonga qo'yilmagan             │
   │   Qaysi yacheyka?  [ B-01-02 ]  yoki yacheyka yorlig'ini   │
   │                                  skanerlang  📷            │
   │                              →  [ Javonga qo'ydim ]        │
   └────────────────────────────────────────────────────────────┘
```

### 2.1 Moment one — what came, and how many

**Nima keldi** identifies *one card*: an existing card found by typing or **by
scanning a label already stuck on one of the shoes**, or a new card written
here from kind + colour + brand.

**Nechta** is a size→quantity table and nothing else. `43 → 10`, `42 → 10`.
Each row is a variant; the row is what makes "10 ta oq 43" a different product
from "10 ta oq 42". A kind the shop has only ever received without sizes (a
cap, a bag) shows one box and no size column — that rule already exists and
stays.

**Decided: one receipt is one colour.** White shoes and black shoes are two
receipts, each with its own sheet of labels, one after the other — and the
second one keeps the card, the kind, the brand and the cost, so it is the
sizes and the colour that are retyped and nothing else. The old screen's
multi-colour row goes; it was the single biggest source of complexity on a
2,388-line screen, and the thing it bought — one submission for a mixed sack —
is two taps saved a few times a week.

**Tannarx** — what one of these cost at the market — is asked here too, once
for the whole receipt. It has to be: this is the only moment anybody knows it,
and by the evening it is a guess. A guessed cost reaches the profit report
looking like a fact.

Pressing **Qabul** writes the goods in and **prints**. Nothing else is asked
for. The goods now exist, they are in `QABUL` — the receiving area, which is a
real place in this system and not a flag — and they have codes.

### 2.2 Moment two — where they went

The screen does not clear. It becomes one line and one question:

> **20 dona · yorliqlangan · javonga qo'yilmagan** — Qaysi yacheyka?

- Answered by **scanning the cell's own label**: one scan and the goods move.
  This is the fast path and it should be the obvious one.
- Or by typing the code, with the usual suggestion of where this model already
  lives.
- The screen may be closed and come back to it: the queue lives on `/qabul`
  and on the dashboard as **"Yorliqlangan, javonga qo'yilmagan"** with its
  age.

**Nothing is lost while that question is unanswered.** `QABUL` is already a
*sellable* place in this system (`models.SELLABLE_KINDS`): goods standing in
the receiving area can be sold, and the pick list simply sends the picker
there instead of to a shelf. The cell is what makes them quick to find, not
what makes them exist. That is why this can be two moments at all.

This is two taps, not two screens, and the second one is a scan.

**Do not turn this into the old two-stage sorting flow.** The difference
matters: that one asked a *second person* to *sort a sack* at a *later time*.
This is one person, one minute later, ten metres away, answering the one thing
they could not know before they walked.

### 2.3 What comes out

- a sheet of **one sticker per unit** — twenty shoes, twenty stickers, one
  print (§3);
- after the cell: the cell as a link into the shelf map, with the goods
  already in it, and one line of plain confirmation:
  `20 dona · B-01-02 · 2 400 000 so'm`.

### 2.4 What disappears

- the words `qop`, `pilla`, `saralash` from every screen and label;
- the unopened-sack panel and the hand-driven two-stage supply flow. The
  `supplies` row stays — it is the market run and the cost lives on it — but
  it is written *by* the receipt and never edited by hand;
- `/yorliqlar` as the only way to print goods labels. The screen stays for
  reprints and for cell labels.

---

## 3. The label — a thermal printer, one sticker per unit

**Decided: a 58 mm thermal label printer**, not an A4 sticker sheet. A roll
wastes nothing when twenty labels are wanted, each label peels off on its own,
and the printer lives on the bench. This changes the printing module: it is no
longer an A4 page of many labels, it is **one label per page, printed N
times**.

**Decided: every single unit gets one.** No "label-less" receipt, no one label
per box. A shoe without a sticker is a shoe the scanner cannot see, and half
the point of the rebuild is that the warehouse can be scanned.

### 3.1 The page

- Label stock: **58 × 40 mm** (the common roll for this class of printer). Put
  the size in one constant with a comment; a shop that buys 58 × 30 changes
  one line.
- CSS `@page { size: 58mm 40mm; margin: 0 }` and **one label per page**, so
  the driver advances the roll between labels. No grid, no sheet, no
  crop marks.
- Print `copies` pages for a quantity of `copies`: twenty shoes, twenty pages,
  one `window.print()`.
- **Grouped, in the order they were typed.** Ten 43s, then ten 42s — matching
  the piles on the table. Interleaved sizes make the person read every sticker
  before sticking it.
- The browser must be able to print without the header, footer and margins a
  browser adds by default. Say in the screen's own text which two boxes to
  untick the first time (`Headers and footers` off, `Margins: none`) — that is
  a five-minute support call every shop makes once.
- It must work from the phone browser as well as the desk: the bench is a
  phone, and a thermal printer on the same wifi prints from it.

### 3.2 One sticker

At 58 × 40 mm there is room for four things and no more:

```
   ┌────────────────────────────────┐
   │                                │
   │   43            Oq             │  ← size very big, colour beside it
   │                                │
   │   ▐││▌▐│▌││▐││▌▐│▌▐││▌         │  ← the barcode, full width
   │   MB-000007-OQ-43        3/10  │  ← code, and the counting aid
   └────────────────────────────────┘
```

- **The size is the biggest thing on it.** Somebody sorting a shelf reads the
  size from half a metre away; they scan only when they need certainty.
- **Numbered within its size** (`3/10`): not an identity, a counting aid. You
  know you are finished when you have used `10/10`, which is the only check
  there is that every shoe got one.
- **The barcode is the variant's own**, permanent, never regenerated. Twenty
  stickers carry the same barcode because twenty identical shoes are twenty of
  one thing. A sticker is not a serial number and this system does not track
  individual units.
- The price is **not** on the label. It changes; the sticker does not.

**Reprint is always available** — from the receipt line and from `/yorliqlar`.
Printers jam, and the alternative to a reprint is somebody writing a barcode
by hand.

### 3.3 The cell labels

`/yorliqlar` also prints cell labels (`B-01-02`), and those go on the shelf
edge. Same printer, same page size, but the code **large and human-readable**
with its barcode under it — a person reads the cell code far more often than
they scan it.

---

## 4. The warehouse becomes scanner-first

One component, one behaviour, every warehouse screen.

**Decided: both a scanner gun and the phone camera.** The gun is on the bench,
the phone is what somebody has in their hand at the shelf, and the two cost
almost nothing together because they end at the same place — a string.

- A **scan target** that is always listening on `/qabul`, `/ombor`, `/terish`,
  `/sanash`. A barcode scanner gun is a keyboard: it types fast and ends with
  Enter. So: capture keystrokes that arrive faster than a human types, buffer
  them, act on Enter. No focused input required, and typing into a real field
  must still work — if an input has focus, the field wins.
- A **camera button** beside it, for a phone with no gun. Use the browser's
  own `BarcodeDetector` where it exists (Android Chrome does), and when it
  does not, say so plainly and leave the manual field — do not ship a 300 KB
  decoding library to cover a browser this shop does not use. The camera
  closes itself the moment it reads one.
- **One router for what was scanned.** A variant barcode, a SKU or a cell code
  all arrive as a string; `GET /warehouse/scan?code=…` answers what it is and
  what can be done with it. The screen decides what to do with the answer:
  - `/qabul` — a variant fills in the card; a cell fills in the destination.
  - `/ombor` — anything jumps the map to it and opens its panel.
  - `/terish` — a variant confirms the line being picked; a wrong one refuses
    loudly.
  - `/sanash` — a variant adds one to the counted quantity of its row.
- Manual entry stays everywhere. There is one scanner and four people.

*(Corrected while building: there is no `GET /warehouse/find`.)*
`GET /warehouse/where-is` already resolves a name, a SKU or a barcode; the new
endpoint reuses its exact-match leg rather than growing a second search — but
it could not simply be called, because it resolves no cell code and drops a
variant with no placements, and the scan router needs both.

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

1. Stock is a ledger. *(Corrected while building: this rule was written from
   the old one-movement flow and §2 deliberately reverses it.)* Receiving
   writes a `RECEIPT` movement into `QABUL`, and shelving writes a `PUTAWAY`
   out of it into the cell. `StockPlacement` must equal the sum of movements;
   the suite asserts it after every operation.
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

1. As the warehouse user, receive **20 white shoes, 10×43 and 10×42** on one
   screen, without typing a size twice and **without being asked for a cell**.
2. The screen offers **20 labels** straight away — twenty pages of 58 × 40 mm,
   ten saying `43` then ten saying `42`, each numbered `n/10`, size biggest.
   Check it in the browser's print preview: one label per page, no browser
   header, no margin.
3. The same screen now asks the one remaining question. Scan `B-01-02`'s cell
   label — one scan — and the goods move there.
4. Follow the link it gives: the shelf map shows the goods in that cell.
5. Leave the second question unanswered on a second receipt, reload, and find
   it waiting on `/qabul` and counted on the dashboard.
6. Scan one of those barcodes on `/ombor`: the map jumps to `B-01-02`.
7. Scan the same barcode on `/qabul`: the card is filled in. Do it once with
   a scanner gun and once with the phone camera button.
7a. Receive the **black** ones as a second receipt: the card, the kind, the
   brand and the cost are still there; only the colour and the sizes are
   retyped.
8. As the admin, open the new card in `/mahsulotlar`: one panel, three gates.
   Add a photo for each colour from a phone camera, set a price, pick a
   category, press one button. The card is on sale.
9. There is no `seller` anywhere: not in the menu, not in the staff role list,
   not in the enum, not in `dev.sh`'s table.
10. `pytest -q` green, `npm run lint` and `npm run build` clean.
11. The words `qop`, `pilla` and `saralash` appear nowhere on screen.

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
| **B1 · receiving** | `app/routers/warehouse.py`, `app/products.py`, `app/schemas.py` (pile/receipt section), `app/routers/dashboard.py` (one tile) | The receipt in its two moments: `POST` writes the card, the variants, a `RECEIPT` movement into `QABUL` and the supply row, and answers with the label lines **and their counts**. A second door moves a receipt's goods from `QABUL` to a cell. A dashboard tile counts what is labelled and not yet shelved, with its age. Keep idempotency on both. |
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
| **W3 · scan + labels** | `web/src/components/scan.tsx` (new), `web/src/pages/labels.tsx`, `web/src/pages/shelf-map.tsx`, `web/src/pages/counts.tsx`, `web/src/pages/picking.tsx` | §3 and §4: the 58 mm one-label-per-page print, the keyboard-wedge listener, the `BarcodeDetector` camera button, and the four screens that answer a scan. |

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
