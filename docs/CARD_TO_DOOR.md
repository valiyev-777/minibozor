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

**So this rebuild is not a rewrite.** It is: move *who* does the first half,
put a document between the two halves, and finish the three things that were
never built — the card form, the colour palette, the size systems.

### What is genuinely new

1. The admin's **card form** (§3) and the fact that it, not the bench, is
   where a card is born.
2. The **shipment** — a declared consignment with a discrepancy loop (§4).
3. The warehouse's **scan-count** in front of the existing put-away (§5).
4. Publishing **gated on accepted stock** (§6).
5. Picking **one scan per unit**, a **parcel label**, a **handover scan** (§7).
6. The courier being **told, with a sound** (§8).

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

## 11. The agent split

Explicit file ownership. **No two agents in a wave touch the same file.** Each
reports what it changed and stops. `docs/RECON_WAVE0.md` is required reading
for every one of them.

### Wave 0 — recon (1 agent, read-only)

The last recon is one day old and still mostly true. Re-check only:

- what `POST /warehouse/receipts` and `/putaway` do today, exactly;
- `Supply` / `SupplyLine` / `SupplyStatus` as they stand, and every reader of
  `supply_id`;
- what `qabul.tsx` would keep and what would move to the admin's side;
- whether the working tree is clean — the last recon found 67 files of
  in-flight work, and **nothing starts until that is committed**.

### Wave 1 — backend (3 agents, parallel)

| Agent | Owns | Job |
| --- | --- | --- |
| **B1 · shipment** | `app/routers/warehouse.py`, `app/models.py` (Supply\*), `app/schemas.py` (shipment section), `alembic/versions/*` | §4 in full: states, the declared lines, the scan-count endpoint that writes one movement per unit, the discrepancy, the admin's confirmation. Keep idempotency. |
| **B2 · reference data** | `app/colours.py` + `app/sizes.py` (new), `app/routers/admin.py`, `app/schemas.py` (palette section), `app/seed.py` | §3.3: the palette and the size systems, seeded in Uzbek, with their read/write doors. |
| **B3 · orders** | `app/routers/picking.py`, `app/routers/operations.py`, `app/routers/courier.py`, `app/notifications.py` | §7 and §8 on the server: pick-by-scan, the parcel label's data, the handover scan, and what the courier board must expose for a live refresh. |

`schemas.py` is shared — **B1 owns the shipment classes, B2 the palette
classes, B3 the order ones.** Nobody reformats the file.

### Wave 2 — web (3 agents, parallel; starts when Wave 1 is green)

| Agent | Owns | Job |
| --- | --- | --- |
| **W1 · the card form** | `web/src/components/card-form/*` (new), `web/src/pages/products.tsx`, `card-editor.tsx` | §3 in full, and §6's gate panel. The largest piece in the brief. Publish the component's props **on day one** — W2 mounts it. |
| **W2 · receiving** | `web/src/pages/qabul.tsx`, `web/src/pages/labels.tsx` | §5: the shipment list, the scan-count with its sounds, then the put-away that already works. Move what belongs to the admin into W1's form rather than duplicating it. |
| **W3 · orders** | `web/src/pages/picking.tsx`, `web/src/pages/courier.tsx`, `web/src/components/scan.tsx` | §7 and §8 on screen: pick-by-scan, the parcel label, the handover, the board that refreshes and **makes a sound**. |

`queries.ts` and `types.ts` are shared and do **not** split cleanly — the
recon says so. Add to the end of your own area, never reformat, and expect one
merge conflict each; resolve it by keeping both.

### Wave 3 — one agent, serial

Walk §10 in a browser against the running stack. Fix what fails. Update
`docs/BUILD_PROMPT.md` and the `backoffice-design` skill if a rule changed.
Commit.

### House rules

- Load the `backoffice-design` skill before any screen work. No hex, no
  Tailwind palette colour, no pixel height for a control.
- **One new dependency is allowed**: the rich text editor (§3.1·8). Pin it and
  say in the commit why.
- A comment says **why**, not what.
- Never hand-write an `ALTER`; autogenerate the Alembic revision.
- Run `pytest -q`, `npm run lint`, `npm run build` before reporting.
- **A screenshot proves a page rendered, not that it works.** Drive the
  interaction and assert on what changed.
- If this brief and the code disagree, **say so** rather than guessing.
