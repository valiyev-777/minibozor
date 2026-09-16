# Mini Bozor — kartadan eshikkacha

The whole path a pair of shoes takes, from the admin writing its card to a
courier handing it over — and the rebuild that makes the software follow it.

> **O'zbekcha, qadamma-qadam.**
>
> 1. **Admin** tovarni ko'rib turib **kartasini yaratadi** — to'liq ma'lumot,
>    bittalab. U omborda emas; tovar qayerga kelgan bo'lsa, o'sha yerda.
> 2. Tizim **nechta dona bo'lsa — shuncha yorliq** chiqaradi.
> 3. Admin yopishtiradi va **omborga jo'natadi**.
> 4. Ombor **har bittasini bittalab skanerlab** qabul qiladi.
> 5. **Kam chiqsa** — adminga "shuncha chiqdi" deb xabar ketadi; **admin
>    tasdiqlaydi**. Ortiqcha chiqsa — "1 ta ortiqcha" deyiladi va qolganlari
>    bilan birga sotilaveradi.
> 6. Adminda **"omborda bor"** chiqadi — endi **do'konga chiqarish** mumkin.
> 7. Sotilsa: omborchi javondan oladi va **skanerlaydi** — *oldim*.
> 8. Omborchi **"yig'ildi, kuryer kerak"** deydi → **kuryerlarga xabar**
>    (taxtada chiqadi, **ovoz** beradi).
> 9. Omborchi **qadoqlaydi, qadoqqa yorliq yopishtiradi, skanerlab** kuryerga
>    beradi.
> 10. Kuryer yetkazadi va **"yetkazdim"** deydi. Tugadi.

Paste this whole file into a fresh session. Read it all before touching a
file. The agent split is **§11**; run the waves in order.

Repo: `/home/muhammad-sodiq/minibozor`, branch `feature/one-warehouse-shop`.
Stack and conventions: `docs/BUILD_PROMPT.md` §2–§4. The look: the
`backoffice-design` skill, loaded **before** any screen work.

---

## 0. Decisions — do not re-open these

The owner answered these on 2026-09-15 and 2026-09-16. An agent that finds one
inconvenient says so and stops; it does not choose differently.

| | Decision |
| --- | --- |
| Who writes the card | **The admin**, wherever the goods reached him — not the warehouse bench |
| Who prints and sticks | **The admin**, before sending |
| Who picks the cell | **The warehouse worker**, when accepting |
| How goods are counted in | **One scan per unit.** Twenty shoes, twenty scans |
| Short delivery | Warehouse reports the number → **the admin confirms** it before the paperwork closes |
| Over delivery | Say "1 ta ortiqcha", **accept it**, sell it with the rest. It does not block |
| Publishing | Only once stock has been **accepted into the warehouse** |
| Courier is told | On the board, **with a sound**; a browser notification too |
| Printer | 58 mm thermal, one label per page, **one label per unit** |
| Scanner | Gun (keyboard wedge) **and** phone camera |
| Colours | A seeded **palette with swatches** — ticked, never typed |
| Sizes | Named **size systems** (EUR/UK/US/RUS, kiyim) — offered, never typed |
| Language | **Uzbek only.** No Russian field, anywhere |
| Role | `seller` is gone. Admin, ombor, kuryer, mijoz |

---

## 1. What is already built — do not rebuild it

`docs/RECON_WAVE0.md` measured the tree on 2026-09-15. Everything below works
and is tested (203 tests green). **Read that file before planning anything.**

| Already there | Where |
| --- | --- |
| The 58 × 40 mm thermal roll, one label per page, `copies`, `n/total`, grouping | `web/src/components/label-roll.tsx` |
| Cell labels, code large with its barcode under it | same file, `CellRoll` |
| The barcode drawing | `web/src/components/barcode.tsx` |
| Reprint bench, URL as state | `web/src/pages/labels.tsx` |
| Scan: keyboard wedge **and** `BarcodeDetector`, focused field wins | `web/src/components/scan.tsx` |
| One scan router | `GET /warehouse/scan` — `shelves.py:187` |
| Scanning already listening on four screens | qabul, shelf-map, picking, counts |
| Receipt → `QABUL`, then putaway → cell, idempotent, ledger-true | `warehouse.py:199,388` |
| The cell answered by scanning its own label | `qabul.tsx:201` |
| A queue that survives a reload, on `/qabul` and the dashboard | `warehouse.py:494`, `dashboard.py:94` |
| `seller` deleted everywhere including the enum | §B of the recon |
| Publishing living on the product card | `products.tsx:748` |
| Photographs: camera, paste, drag-drop, per colour | `photo-step.tsx` |
| **The card form itself** — category cascade, colour modal, attributes, rich text, price table, gate panel | `web/src/components/card-form/*` — 3,133 lines |
| **The colour palette and the size systems, as data** | `app/colours.py`, `app/sizes.py`, `models.Colour`, `models.SizeSystem` |
| **The catalogue card** | `web/src/components/product-card.tsx` |

> ⚠️ **Most of that is uncommitted.** Measured 2026-09-16 in a dirty working
> tree. It is real, working code that nobody has committed yet. **Wave 0's
> first job is to get it committed** — every one of these files is on an
> agent's ownership list below, and an agent that starts on top of
> uncommitted work cannot be reviewed, reverted or merged.

**So this rebuild is not a rewrite.** The two halves exist and work. What is
missing is the **document between them** — and the consequences of there being
one.

### What is genuinely new

The card form exists. What does **not** exist is the journey around it:

1. The **shipment** — a declared consignment with states and a discrepancy
   loop (§4). Nothing like it is in the tree.
2. The card form's **tail**: quantities, cost, *Jo'natish*, and the label roll
   — the form writes a card today, it does not send goods (§3.2).
3. The warehouse's **scan-count** in front of the existing put-away (§5).
4. Publishing **gated on accepted stock** — the fourth gate (§6).
5. Picking **one scan per unit**, a **parcel label**, a **handover scan** (§7).
6. The courier being **told, with a sound** (§8).

And one rule to re-check rather than assume: **the card form must write no
stock.** If its submit currently books anything into the room, that is the
first thing to change.

---

## 2. The journey

```
   ADMIN  (tovar qayerda bo'lsa)        OMBOR                    KURYER
   ─────────────────────────────        ──────────────────       ────────────
   1 kartani yaratadi
     · toifa, nom, brend
     · rang (palitradan)
     · o'lcham + nechta
     · tannarx
   2 yorliq chiqadi  🖨
   3 yopishtiradi ──jo'natdim──▶  4 har donani skanerlaydi
                                     18 / 20 ⚠
                  ◀──"18 ta chiqdi"──┤
   5 tasdiqlaydi ──────────────────▶ │
                                     └─ yacheykani skanerlaydi
                                        → javonda
   6 "omborda bor" ✓
     do'konga chiqaradi
        (kategoriya · narx · rasm)

        ⋯⋯⋯⋯⋯⋯⋯⋯ mijoz buyurtma beradi ⋯⋯⋯⋯⋯⋯⋯⋯

                                  7 javondan oladi, skanerlaydi
                                  8 "yig'ildi" ──xabar + ovoz──▶ keladi
                                  9 qadoqlaydi, yorliqlaydi,
                                    skanerlab beradi ───────────▶ 10 yetkazadi
                                                                    "yetkazdim" ✓
```

**The one rule that holds it together:** the ledger records what was *found*,
never what was *declared*. The admin's twenty is a claim on a document; the
warehouse's eighteen scans are eighteen movements. That is why a shortfall is
a conversation and not a correction — nothing wrong was ever written down.

---

## 3. The admin's card form

One long form, one column, in the order a person knows the answers, with
everything optional folded behind a button. The owner pointed at Uzum's
*Tovarni yaratish* and said: this shape. Two things do **not** come with it:

- **No Russian.** Uzum asks for every field twice because it sells in two
  languages. Every doubled input is a single input here, and the form is half
  as long for it.
- **No marketplace furniture.** No fiscal code, no seller code, no moderation
  state, no 360° photographs.

*"Juda qulay dizayn, ortiqcha narsalarsiz, kerakli narsalar bilan."*

### 3.1 The sections, in order

**1 · Mahsulot toifasi** — first, because it decides what the rest of the form
offers. Cascading selects, one per level, each appearing when its parent is
chosen: `Kiyim → Oyoq kiyim → Erkaklar → Krossovka`. One button under them,
**Qabul qilish**; after it the selects collapse into a breadcrumb with an
**O'zgartirish** beside it. `categories.parent_id` already nests to any depth.

**2 · Tovar nomi** — one line, `0/90`. The counter is not decoration: a name
that runs past the card in the phone app is truncated in the one place it
matters.

**3 · Brend · Model · Mamlakat** — three selects, each with a **"Mavjud emas"**
checkbox, because market goods often genuinely have none and the alternative
is somebody typing "yo'q". Brand reads `brands` through its alias lookup.

**4 · Rang** — **from the palette, ticked, never typed.** A modal of named
colours with their swatches: `Oq`, `Qora`, `To'q qizil`, `Sarg'ish`,
`Feruza`… This is what stops `qora` / `Qora` / `QORA` becoming three colours.
`+ yangi rang` adds to the **palette**, not only to this card.

One card may come in several colours. Each colour gets its own quantity block
(§3.1·5) and its own photograph block (§3.1·7).

**5 · O'lcham va nechta** — pick the size system once (`Erkaklar poyabzali
EUR`, `Kiyim`, `O'lchamsiz`), then a row per size with a quantity:

```
   Oq        43 ▸ 10     42 ▸ 10          20 dona
   Qora      43 ▸  5                       5 dona
                                 ──────────────────
                                 Jami      25 dona
```

A system the shop has not used before is added in the same modal as the
colours. **`O'lchamsiz`** is a real choice for a cap or a bag — one box, no
size column.

**6 · Tannarx** — one number for the shipment. It has to be asked here: this
is the only moment anybody knows it, and by the evening it is a guess. A
guessed cost reaches the profit report looking like a fact. Transport cost is
optional beside it.

**7 · Har bir rang uchun rasm** — a block per colour, headed by its swatch and
name. First photo is that colour's cover; `+ Rasm qo'shish` adds more. Camera,
paste and drag-drop all work (`photo-step.tsx` already does this).

**8 · Tavsif** — a **rich text editor**, not a textarea: bold, italic, lists,
one heading level, nothing else. The phone app renders it, so the editor must
not be able to produce what the app cannot draw. Store HTML, sanitise on the
way in, keep plain text alongside for search. Use TipTap or Lexical — do not
hand-roll `contenteditable`.

**9 · Xususiyatlar** — free rows, `Material · Charm`. **One column of inputs,
not two.** Add with a button, remove with the bin at the end, `0/255` each.
This is `product_specs`, which exists.

**10 · Folded away until wanted** — a heading and a **Qo'shish** button each:
`O'lchovli to'r`, `Tarkib`, `Parvarish`, `Sertifikatlar`. A form that shows
eleven empty textareas is a form nobody finishes.

**11 · Narx** — optional here. The selling price can be set now or at
publishing time; the form offers a markup against the cost (`+60%`) and says
which figure it is working from.

### 3.2 What the form does at the end

One button: **Yorliqlarni chiqarish va jo'natish**.

1. The card is written (`draft`), with its variants, colours, sizes and photos.
2. A **shipment** is written with the declared quantities (§4).
3. The label roll opens — **25 labels**, grouped by colour then size in the
   order they were typed, each numbered `n/10`.
4. The screen then shows one line: *"25 dona · yorliqlar chiqarildi · omborga
   jo'natildi"*, and the card's own page is one click away.

**No stock is written.** The goods are in the admin's hands, not in the
building, and the ledger does not record journeys nobody has made.

### 3.3 The palette and the size systems are data

Two seeded tables, editable by the admin, never hard-coded:

- `colours` — `name` (`Sarg'ish melanj`), `hex`, `sort`.
  `product_variants.colour` keeps holding the **name**, so nothing about the
  ledger changes.
- `size_systems` + their values — `Erkaklar poyabzali EUR` → `39 … 46`;
  `Kiyim` → `S M L XL XXL`; `O'lchamsiz` → one empty value.

Seed both with what this shop sells, in Uzbek. Anything already in the
database keeps working: a colour not yet in the palette is still a valid
string, and the form offers to add it.

---

## 4. The shipment — the document between the two halves

**Reuse `supplies` and `supply_lines`.** They already exist, they already mean
"a consignment and what was in it", and `stock_movements.supply_id` already
links goods to one. What they need is a life.

### 4.1 Its states

```
   yaratildi ──jo'natdim──▶ yo'lda ──birinchi skan──▶ sanalmoqda
                                                          │
                                       ┌──────────────────┤
                            hammasi to'g'ri        kam/ortiq chiqdi
                                       │                  │
                                       ▼                  ▼
                                    yopildi ◀──admin tasdiqladi──
```

- **`yaratildi`** — the admin is still writing. Nothing is anybody's problem.
- **`yo'lda`** — declared, labelled, sent. It appears on the warehouse's list
  with its age, and on the dashboard.
- **`sanalmoqda`** — the first unit has been scanned. Now it has a live count.
- **`yopildi`** — the paperwork is done and the numbers are agreed.

### 4.2 The discrepancy

At the end of counting the screen states the plain fact:

> **18 / 20** — `Oq 43` dan 2 ta yetmadi.

- **Short → the admin decides.** The warehouse presses *"Adminga yuborish"*;
  the admin sees the shipment with both numbers and either **confirms** — the
  shipment closes at 18, and the two that never arrived are recorded as never
  having arrived — or **refuses**, and it stays open for a second look, which
  is exactly what happens when a box was under the table.
- **Over → say it and accept it.** *"1 ta ortiqcha"*. It is scanned in like
  the rest and sold with the rest. The admin is told; nothing blocks. That is
  the owner's own decision and it is the right one — the goods are on the
  shelf whatever the paper says.

**Nothing is deleted or written off.** The eighteen that arrived have
eighteen movements. The two that did not have none. The difference is a
sentence on a document, not an adjustment in the ledger.

---

## 5. The warehouse accepts

The receiving screen keeps its shape — the put-away half is built and works —
and gains a counting phase in front of it.

```
   ┌── 1 · Qaysi jo'natma ──────────────────────────────────┐
   │   Admindan · 25 dona · 2 soat oldin      [ Boshlash ]  │
   └────────────────────────────────────────────────────────┘
   ┌── 2 · Sanash ──────────────────────────────────────────┐
   │                                                        │
   │            18 / 25            🔊 har skanda ovoz       │
   │                                                        │
   │   Oq   43   ██████████  10/10 ✓                        │
   │   Oq   42   ███████░░░   7/10                          │
   │   Qora 43   █░░░░░░░░░   1/5                           │
   │                                                        │
   │   [ Tugatdim ]                                         │
   └────────────────────────────────────────────────────────┘
   ┌── 3 · Javonga ─────────────────────────────────────────┐
   │   Qaysi yacheyka?  yorliqni skanerlang 📷  yoki [B-01-02]│
   └────────────────────────────────────────────────────────┘
```

- **One scan per unit** (the owner's decision). Each scan writes one `RECEIPT`
  movement of 1 into `QABUL`, linked to the shipment. The ledger *is* the
  count — there is no second counting table to keep in step, and a session
  interrupted by a dead battery has simply received fewer.
- **Every scan answers:** a rising tick for a unit that belongs to this
  shipment, a flat buzz for one that does not, and a line saying which it was.
  A scanner without a sound is a scanner somebody watches instead of working.
- **A label from another shipment** is refused by name: *"Bu boshqa
  jo'natmadan — MB-000012"*.
- **More than declared** is accepted with a warning, per §4.2.
- **Then the cell**, exactly as it works today: scan the cell's label, or type
  it. Put-away may be split — scan a second cell and carry on.

The shipment list is the screen's front door and it survives a reload.

---

## 6. Publishing

The card sits in `draft` from the moment the admin writes it. It goes on sale
when four things are true — three about the card and one about the room:

```
   ✓ Kategoriya
   ✓ Narx
   ✓ Har rangga rasm
   ✓ Omborda bor          ← accepted into the warehouse, not merely declared
```

The fourth is what makes *"adminda 'omborda bor' chiqadi"* real: a card whose
goods are still in the admin's car cannot be sold, and the shop cannot promise
what the shelf has not seen.

The panel sits at the top of the card in `/mahsulotlar`, each gate editable in
place, one button that says what is missing while it is disabled.

---

## 7. Picking, packing, handing over

**7.1 · Terish — one scan per unit.** The pick list names the cell in walk
order; the picker scans each unit as it comes off the shelf. A wrong unit is
refused loudly. This closes the same gap the receiving count closes: the
figure is what was scanned, not what was intended.

**7.2 · "Yig'ildi, kuryer kerak".** One button when the list is complete. The
goods are in `YIGIM`; the order is ready; the couriers are told (§8).

**7.3 · Qadoq yorlig'i.** The parcel gets its own label — the **order code** as
a barcode, the customer's name and district under it, printed on the same
thermal roll. It goes on the outside of the parcel.

**7.4 · Topshirish.** The courier arrives; the warehouse scans the parcel
label and hands it over. That scan is the handover: the order moves to the
courier's own place in the ledger (`KURYER-n`) and the courier's round gains
a stop. Two people, one scan, no form.

**7.5 · Yetkazdim.** The courier's screen, as it works today — with the cash
figure when it is cash.

---

## 8. The courier is told, and hears it

*"Online bo'lsa taxtaga boradi, ovoz chiqadi, notification chiqsa ham
bo'ladi."*

- The available-orders board refreshes on its own while it is open.
- A **new order on the board plays a sound** — one short tone, once per order,
  and never for an order that was already there when the screen opened.
- A **browser notification** when the tab is in the background and permission
  has been given. Ask for permission at a sensible moment — when the courier
  first opens their round — never on load.
- Nothing here is a push server. A courier with the app closed finds the work
  when they open it; that is the honest scope for now and it should be said in
  the code rather than half-built.

---

## 9. Rules that do not change

1. **Stock is a ledger of moves.** Placements equal the sum of movements; the
   suite asserts it after everything that touches the room.
2. **The ledger records what was found.** A declaration is a document.
3. Colour and size are two fields, never one glued string.
4. One card is sized **or** sizeless, never both.
5. `xl` and `XL` are one size, tidied at every door that writes a variant.
6. A variant's barcode and SKU are permanent — reprinted, never regenerated.
7. Idempotency keys on every warehouse and courier write.
8. Every figure the office reads is defined once, on the server.
9. Uzbek on screen, English in comments, `Intl` never used for formatting.

---

## 10. Acceptance — walk it, do not assume it

With `./dev.sh` up:

1. As the **admin**, create a card for **25 shoes**: `Oq 43×10`, `Oq 42×10`,
   `Qora 43×5`. Colour ticked from the palette, sizes offered by the system,
   never typed.
2. The form prints **25 labels**, grouped `Oq 43`, `Oq 42`, `Qora 43`, each
   numbered `n/10`. One label per page, no browser header, no margin.
3. **No stock exists yet** — the shelf map is unchanged, the card cannot be
   published, and the reason given is "omborda yo'q".
4. As the **warehouse**, open the shipment and scan **23** of the units, one
   by one. Each scan makes a sound; the counter climbs; a label from another
   shipment is refused by name.
5. Press *Tugatdim*: the screen says **23 / 25** and names what is missing.
   Send it to the admin.
6. As the **admin**, see both numbers and confirm. The shipment closes at 23.
7. As the **warehouse**, scan a cell and put the goods away; the shelf map
   shows them.
8. As the **admin**, the card now says **omborda bor**; add the price and a
   photo per colour, press one button, and it is on sale.
9. Order one from the phone app. As the **warehouse**, scan it off the shelf,
   press *Yig'ildi*, print the parcel label.
10. On a **courier** screen that was already open, the order appears **and a
    sound plays**.
11. The warehouse scans the parcel label to hand it over; the courier delivers
    and marks it delivered.
12. Scan an over-count on a second shipment: it is accepted, the admin is
    told, nothing blocks.
13. `pytest -q` green, `npm run lint` and `npm run build` clean.
14. No Russian anywhere. No `qop` / `pilla` on any screen — but **leave
    `Saralash` alone** where it means *sorting a table*
    (`data-table.tsx:645`), which is the correct word.

---

## 11. The agent split — wide, and without collisions

The owner is running these on a fast model and wants **as many in parallel as
the work allows** — *"lekin sifat tushmasin"*. Both halves of that sentence are
load-bearing, and they pull against each other in exactly one place: two agents
editing one file. So the split below buys parallelism by **giving every agent
its own files**, and pays for quality with **a contracts wave in front and a
proof wave behind**.

### The shape

```
   Wave 0 ·  1 agent   ·  commit the tree, re-measure          ~15 min
   Wave 1 ·  1 agent   ·  contracts: tables, schemas, types    ~30 min
   Wave 2 ·  8 agents  ·  the work, all at once                 ── parallel ──
   Wave 3 ·  2 agents  ·  drive it, and test it                ~45 min
```

Waves are **barriers**: nothing in wave 2 starts until wave 1 reports, because
every one of them builds on the same table and the same types. Inside a wave,
nobody waits for anybody.

---

### Wave 0 — one agent, read-only except for one commit

1. **Commit the working tree first.** It holds the card form, the palette, the
   size systems and the catalogue card — real work nobody has committed.
   Split it into honest commits; do not squash it into one.
2. Re-measure §1 against the committed tree and correct it in place: what is
   built, what is not, with file and line.
3. Answer three questions the rest depends on:
   - does the card form's submit write **any** stock today?
   - what exactly do `Supply`, `SupplyLine` and `SupplyStatus` hold, and who
     reads `stock_movements.supply_id`?
   - is picking already one-scan-per-unit, or a quantity field?
4. **Stop and report.** If §1 is materially wrong, say so — wave 1 is written
   against it.

---

### Wave 1 — one agent, the contracts

Small, and everything waits on it, so it is alone in its wave.

**Owns:** `app/models.py` (shipment fields only), `alembic/versions/*`,
`app/schemas.py` (**one new block, at the end, marked
`# --- shipment ---`**), `web/src/lib/types.ts` (one block at the end).

**Writes:**
- the shipment's states on `Supply`, its declared lines, who declared, who
  counted, the difference and its confirmation — **the tables and the
  migration only, no endpoint logic**;
- every Pydantic shape wave 2 will return;
- the matching TypeScript types;
- **eight empty hook files** — `web/src/lib/queries.shipments.ts`,
  `queries.palette.ts`, `queries.orders.ts` … each re-exported from
  `queries.ts` in **one** edit made here and never again. This is what stops
  eight agents fighting over a 1,928-line file, and it is worth the small
  ugliness of a split module.

**Done when** `alembic upgrade head` runs, `pytest -q` is green, `tsc` is
clean, and every wave-2 agent has a type to build against.

---

### Wave 2 — eight agents, parallel

| # | Agent | Owns — nobody else touches these | Job |
| --- | --- | --- | --- |
| 1 | **Jo'natma · admin** | `app/routers/shipments.py` (new), `tests/test_shipments.py` (new) | §4: create a shipment from the form, list them, the admin's **confirmation** of a difference. |
| 2 | **Jo'natma · ombor** | `app/routers/warehouse.py`, `tests/test_receiving.py` | §5 on the server: the scan-count door — one movement per scanned unit, linked to the shipment — the live count, refusing a label from another shipment, closing with a difference. |
| 3 | **To'rtinchi darvoza** | `app/products.py`, `app/routers/admin.py`, `tests/test_publishing.py` (new) | §6: a card cannot go on sale until its goods are **accepted**, and the reason says which. Plus: the card form writes **no stock** (fix it if it does). |
| 4 | **Terish skani** | `app/routers/picking.py`, `tests/test_picking.py` | §7.1: one scan per unit off the shelf, a wrong unit refused. |
| 5 | **Qadoq va topshirish** | `app/routers/operations.py`, `app/routers/shelves.py` (label door only), `tests/test_handover.py` (new) | §7.3–7.4: the parcel label's data, and the handover as a scan. |
| 6 | **Kuryerga xabar** | `app/routers/courier.py`, `app/notifications.py`, `tests/test_courier_board.py` (new) | §8 on the server: what the board must expose so a screen can refresh and know an order is **new**. |
| 7 | **Forma dumi** | `web/src/components/card-form/*`, `web/src/lib/queries.shipments.ts` | §3.2: quantities per colour, the cost, **Yorliqlarni chiqarish va jo'natish**, the label roll, and the line that follows it. The form exists — this is its tail, not a rewrite. |
| 8 | **Qabul ekrani** | `web/src/pages/qabul.tsx` | §5 on screen: the shipment list, the scan-count with its **sounds**, then the put-away that already works. Move nothing that belongs to the admin — delete it and let agent 7's form own it. |
| 9 | **Terish va kuryer ekrani** | `web/src/pages/picking.tsx`, `web/src/pages/courier.tsx`, `web/src/components/parcel-label.tsx` (new) | §7 and §8 on screen: scan per unit, the parcel label, the board that refreshes and **makes a sound**. |

That is nine; run all nine. `app/schemas.py` is the only shared file left and
wave 1 has already written every shape any of them needs — **if an agent needs
a new one, it adds it at the end of its own marked block and says so in its
report.**

**Each agent owns its own test file.** A new file per agent is why nine agents
can run `pytest` at the same time without merge pain.

---

### Wave 3 — two agents

| Agent | Job |
| --- | --- |
| **Yurib chiqish** | Walk **every numbered step of §10** in a browser against the running stack. Not screenshots — **drive it**: type, scan (a scan is a fast keystroke burst ending in Enter, so it can be simulated), press, and assert on what changed in the database. Fix what fails. |
| **Sinov supurgisi** | Read the nine agents' tests as one body. Fill the holes between them — the seams are where parallel work leaks: a shipment closed twice, a scan after closing, a difference confirmed by the wrong person, an order picked from a shipment that was never accepted. Re-assert the room adds up. |

---

### How to launch them

One session per agent. Give each the same three lines and its own row:

```
Read docs/CARD_TO_DOOR.md in full, then docs/RECON_WAVE0.md.
You are Wave 2 · agent N. You own ONLY the files in your row of §11.
Do not edit a file another agent owns — if you need one changed, say so and stop.
```

---

### House rules — this is where the quality is

- **Own your files, nothing else.** A one-line fix in somebody else's file is
  how a wave of nine becomes a merge nobody can read.
- **Load the `backoffice-design` skill** before any screen work. No hex, no
  Tailwind palette colour, no pixel height for a control.
- **Tests are not the last wave's job.** An agent reports done when its own
  `pytest -q` is green, and `npm run lint` and `npm run build` are clean.
- **A screenshot proves a page rendered, not that it works.** Drive the
  interaction and assert on what changed.
- **The ledger rules in §9 are not negotiable.** An agent that needs to break
  one has found a design bug — report it, do not work around it.
- **A comment says why, not what.**
- Never hand-write an `ALTER`; autogenerate the Alembic revision.
- **If this brief and the code disagree, stop and say so.** Nine agents
  guessing in the same direction is nine times the wrong answer.
