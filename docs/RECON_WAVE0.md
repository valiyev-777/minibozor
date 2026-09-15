# Recon — Wave 0

> Read-only reconnaissance for `docs/RECEIVING_REBUILD.md` §9.
> Branch `feature/one-warehouse-shop`, measured **2026-09-15**.
> The brief's own numbers were measured 2026-09-14; this file records what moved.

## Headline findings

1. **Waves 1 and most of Wave 2 are already built.** Commit `5a0dd7e` ("Paper
   first, cell last, and the sticker is the thing that gets scanned") shipped
   §2, §3, §4, §5.1 and §8 in full — 43 files, +5350/−3933. The §9 agent table
   describes work that largely no longer exists. **Do not launch B1/B2/B3 or
   W1/W3 as written.**
2. **The brief is stale against itself by one commit.** `60e5834` edited only
   `docs/RECEIVING_REBUILD.md` (+257/−44), adding §5.2–§5.5, §5A and rewriting
   §9. So the brief is *newer* than the code for §5.2+ and *older* than the
   code for §1–§4. The remaining real work is **§5.2, §5.3, §5.4, §5.5 and
   §5A.1 only**.
3. **`pytest -q` is green: 203 passed, 1 warning, 115s.** Run against a
   scratchpad database with `-p no:cacheprovider`; the repo was not mutated.
   Dependencies live in `backend/.venv` (Python 3.14) — there is no system
   `pytest`.
4. **The working tree is dirty with 67 files of unrelated in-flight work**
   (delivery windows removed, nav/shell redraw, phone bottom bar,
   `photo-step.tsx` rewrite). It touches `nav.ts`, `App.tsx`, `products.tsx`,
   `dashboard.tsx`, `shell.tsx`, `queries.ts`, `types.ts`, `schemas.py`,
   `models.py`, `qabul.tsx` — every one of which §9 hands to an agent.
   **Commit or stash before any wave starts.**
5. **`queries.ts` does not split four ways.** Only the receipt block
   (1457–1604) and the scan+label block (1606–1622) are contiguous. W2, W2b
   and W3 would all edit lines 164–312.
6. **`schemas.py`'s B1/B2 split is clean; B3 has no home in it.** §5.3's
   palette and size-system schemas belong to B3, which §9 never grants the
   file.
7. **`GET /warehouse/find` never existed; `GET /warehouse/scan` now does**
   (`shelves.py:187`). §4's correction is right and already actioned.
8. **Three shared files are unassigned in §9:** `web/src/lib/types.ts`,
   `backend/app/i18n.py`, and `label-roll.tsx` + `barcode.tsx`.

---

## A. The four subjects, as they work today

### A.1 `web/src/pages/qabul.tsx` — 1,451 lines (not 2,388), already rebuilt to §2

The sack/pile machinery is **gone**; `qop`, `pilla`, `saralash` appear nowhere
in the file. What remains is exactly §2's two moments.

| Line | Symbol | What it is |
| --- | --- | --- |
| 73 | `type SizeLine` | `{size, qty}` — an array, so typed order survives |
| 75–101 | `type Draft` | one card, **one colour** (singular), `lines`, `unitCost`, `fare`, `named` |
| 107 | `type Open` | the receipt whose moment two is on screen |
| 127 | `QabulPage` | shell; holds `draft`, `open`, `done`, `scanSaid`, `scanFill` |
| 201 | `onScan` | scan router: cell → `putAway`, variant → fill the card, else refuse loudly |
| 246 | `<ScanTarget>` | always listening, on both moments |
| 332 | `MomentOne` | "nima keldi / nechta", the `Qabul` button |
| 512 | `Named` | the card identity line |
| 544 | `IdentifyCard` | find-or-create a card |
| 676 / 720 / 737 | `Maybe` / `Thumb` / `Chips` | duplicate warning, photo, learned vocabulary |
| 825 | `Counts` | the size→quantity table (§2.1's "nechta") |
| 1033 | `SizeRow` | one row |
| 1099 | `Place` | the cell field — moment **two** only |
| 1135 | `MomentTwo` | "N dona · yorliqlangan · javonga qo'yilmagan" |
| 1258 | `Labels` | prints the roll; carries the two-checkbox support text |
| 1321 | `Shelved` | `20 dona · B-01-02 · 2 400 000 so'm`, cell links into the map |
| 1398 | `WaitingQueue` | the §2.2 queue that survives a reload |

**§8 says to delete:** nothing left — the delete already happened.

### A.2 `web/src/pages/publish.tsx` — deleted

Removed in `5a0dd7e` (−392). The `/sotuvga-chiqarish` route is gone from
`App.tsx` and `nav.ts` (`nav.ts:155` carries the tombstone comment).

What replaced it is **not** a §5.2 form — it is two components mounted inside
`products.tsx`:

- **`web/src/components/card-editor.tsx` — 394 lines.** Four independent
  panels, each with its own save: `Words` (48), `Specs` (152), `Filing` (234),
  `Pricing` (312).
- **`web/src/components/photo-step.tsx` — 669 lines.** One photo strip per
  colour: cover first, camera / file / `Ctrl+V` / drag-drop, promote-to-cover,
  delete, optimistic preview. Exports `Photos`, `Capture`, `mediaUrl`.
- **`web/src/pages/products.tsx:748` `PublishPanel`** — the three gates (`Gate`
  at 857) and one **Do'konga chiqarish** button.

**Distance from §5.2:**

- ✅ §5.5 photographs — essentially done in `photo-step.tsx`
- ✅ §5.4 publishing lives on the card
- ✅ §5.2 ·5 spec rows — `Specs` exists, already one column
- ❌ §5.2 ·1 cascading category — `Filing:234` is a **flat chip list**; no
  cascade, no *Qabul qilish*, no breadcrumb
- ❌ §5.2 ·2 `0/90` counter, ·3 brand/model/country with "Mavjud emas",
  ·4 rich text editor, ·6 attribute picker + colour modal + size systems,
  ·9 folded sections, ·10 price table
- ❌ One column, one form: it is four sibling panels with four saves
- ❌ No `web/src/components/card-form/` folder
- ❌ No TipTap / Lexical / ProseMirror in `web/package.json`

### A.3 The print module — already 58 mm, one label per page

- **`web/src/components/label-roll.tsx` — 263 lines** (new in `5a0dd7e`), and
  **not in §9's ownership table at all**.
  - `:43` `const LABEL_STOCK = { w: 58, h: 40 }` with the one-line-to-change comment
  - `:46` `@page { size: 58mm 40mm; margin: 0 }`, injected at runtime because
    `@page` cannot read a CSS custom property
  - one label per page: **yes**. `copies`: **yes** — `copiesOf` (68) expands a
    line, `Sticker` (205) numbers each `n/total`, grouping follows typed order
  - cell labels: **yes** — `CellRoll` (153), `CellSticker` (228), per §3.3
  - `usePrintOnce` (246) — guard claimed after the timer, the StrictMode defect
    named in the commit message
- **`web/src/components/barcode.tsx` — 77 lines.** `bwip-js/browser`;
  `SCREEN = {scale:2,height:10}`, `STICKER = {scale:4,height:9}` — drawn large
  and scaled down by the page box for a 203 dpi head.
- **`web/src/pages/labels.tsx` — 236 lines.** Now the reprint bench; URL is the
  state (`?supply_id=`, `?variant_id=`, `?cells=1`). `LabelsPage` (29), `ByRun`
  (113) with a per-unit `copies` override, `ByVariant` (186).
- **`web/src/index.css:159–330`** holds `.label-page`, `.label-size`,
  `.label-bars`, `.label-page-cell` and the print-media block.

§3 is done, including the support-call text and the phone-browser path.

### A.4 `backend/app/routers/warehouse.py` — 1,090 lines

| Line | Endpoint | Note |
| --- | --- | --- |
| 93 | `GET /warehouse/vocab` | learned chips: kinds, brands, colours, sizes-by-kind, `sizeless`, `spec_keys` |
| 199 | `POST /warehouse/receipts` | **moment one.** Card stub + variants + one `Supply` (already `received`) + one `RECEIPT` movement per size into `QABUL`. Answers with `labels` and `copies`. **No cell asked for.** |
| 388 | `POST /warehouse/receipts/{id}/shelve` | **moment two.** `PUTAWAY` out of `QABUL` into the cell. Mistyped/retired cell refused (`_open_cell`, 888); already-shelved answers politely. |
| 494 | `GET /warehouse/receipts/waiting` | the queue, oldest first |
| 536 | `receipts_waiting(session)` | plain function, **imported by `dashboard.py:53`** so tile and queue cannot disagree |
| 634 / 661 | `GET /warehouse/supplies`, `/supplies/{id}` | read-only |
| 669 / 749 / 803 | `stock/empty`, `damage`, `movements` | |

**`POST /warehouse/supplies` no longer exists**, nor `/sorted` nor `/cancel`.
`test_api.py:1487` asserts 405/404/404. §8's fourth bullet is done.

Idempotency (`backend/app/idempotency.py`) on both receipt doors:

```
done = idem.replay(session, user, key, "receipt", payload)
...do the work...
idem.keep(session, user, key, "receipt", payload, out)
replayed = idem.commit(session, user, key, "receipt")
```

Key required via `Idempotency-Key`, body hashed with it, record committed in
the same transaction. `shelve` stamps `{"receipt_id": id, **payload}` so the
path parameter is part of the fingerprint.

---

## B. `SELLER` — inventory

**The role is already fully deleted.** Every remaining hit is the *marketplace*
seller (a different, long-gone concept), a historical note, or the unrelated
Uzbek noun `sotuvchi` in customer-app strings.

| Place | State |
| --- | --- |
| `backend/app/models.py:31–52` `UserRole` | `CUSTOMER`, `ADMIN`, `WAREHOUSE`, `COURIER` — no `SELLER` |
| `backend/app/deps.py:163` | `CatalogWriter = require_role(UserRole.ADMIN)` |
| `backend/app/deps.py:147,155,180` | `OrderViewer` / `CatalogReader` / `OrderMover` — clean |
| `backend/app/seed.py:58–60` | three phones; no `SELLER_PHONE` |
| `backend/app/roles.py`, `routers/admin.py`, `routers/staff.py` | no hit |
| `web/src/lib/types.ts:599–603` | four roles, with a comment saying why |
| `web/src/pages/staff.tsx:75` | `ROLES` derived from `ROLE_LABEL` — four |
| `web/src/lib/nav.ts:155` | tombstone comment only |
| `dev.sh:238–240` | `admin / ombor / kuryer` |
| `android/`, `ios/` | **no role hit** — only `sotuvchi` = "Seller" on the *customer* product page (`strings.xml:190,313,330,431–434`; `Localizable.strings:169,261–262,342–343`; `ProductBlocks.swift:275,300`). Marketplace copy on the buyer app, out of scope for §5.1. |

Docs mention it historically and correctly: `docs/BUILD_PROMPT.md:460–467,525`,
`docs/NATIVE_APPS.md:52`, `README.md:8`, `web/README.md:5`,
`shared/ui/button.tsx:10`.

### Alembic

- **`3b4d3d7fc68b`** — added the value. `:73`
  `op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SELLER'")`,
  Postgres only. Its docstring (79) already notes there is no
  `ALTER TYPE … DROP VALUE`.
- **`8a32e11a5130`** — 101 lines, `down_revision = '3b4d3d7fc68b'`. Does exactly
  what §5.1 asks: `:59` `UPDATE users SET role='ADMIN' WHERE role='SELLER'`,
  `:61` the same for `audit_log.actor_role`, then rebuilds the type.
  `downgrade()` re-adds it.
- **Head: `a91d2fc3352c`** (delivery windows), `down_revision = '8a32e11a5130'`
  — **untracked**, part of the in-flight work.
- **Dev DB is SQLite** (`docker-compose.yml:88`); the `postgres:16-alpine`
  service at `:28` is opt-in, tests use `sqlite:///./test.db`
  (`conftest.py:22`). The enum drop was never *needed* in dev and the migration
  guards on dialect.

**Verdict:** B3's "delete SELLER" half is complete. Only the §5.3 half remains.

---

## C. The endpoints

### `GET /warehouse/labels` — `shelves.py:1129–1215`

Query `supply_id`, `variant_id[]`, `cells: bool = False`. Response
`s.LabelSheetOut` (`schemas.py:1383`):

```
{ "products": [ ProductLabelOut ], "cells": [ CellLabelOut ] }
ProductLabelOut (schemas.py:1355): variant_id, product_title, variant_label,
                                   colour, size, sku, barcode, price, copies=1
CellLabelOut    (schemas.py:1376): code, rack, column_no, row_no
```

`copies` = summed `SupplyLine.quantity` per variant in `SupplyLine.id` order
(insertion order = typed order). Reprint by `variant_id` gives one copy each.
`copies <= 0` dropped. No selection → 400 `labels_need_a_selection`.

### `GET /warehouse/find` — **does not exist and never did.** The correction is right.

### `GET /warehouse/where-is` — `shelves.py:140–185`

Exact leg first via `_exact_variants` (`:1235`) — case-insensitive
`barcode == q OR sku == q` — then a `LIKE %q%` on `Product.title`. **`:177–182`
drops any variant whose `places` is empty**, and it **resolves no cell code**.
Both of §4's stated gaps are real.

### `GET /warehouse/scan` — **exists**, `shelves.py:187–251`

`code: str`, guarded by `StockViewer`, always 200. Reuses `_exact_variants`,
exact only. Three outcomes:

- `kind="variant"` → `ScanVariantOut` (`schemas.py:1395`) = `WhereIsOut` +
  `colour` + `size`, **kept even with empty `places`**
- `kind="cell"` → `LocationDetailOut` with `contents`; retired cells included
  so the screen can say "that cell was taken out"
- `kind="none"` → the echoed code

`ScanOut` at `schemas.py:1409`. Tested by `test_scan_and_labels.py:198–332`.

### §5.3 colours / size systems — **nothing exists**

No `colours` or `size_systems` table in `models.py` (last table is
`PickupLine:1387`). No `/admin/colours`, no `/admin/size-systems`. `ColourOut`
(`schemas.py:242`) and `ColourIn` (`:1713`) are the *variant grid's* colour, not
a palette. `pr.colours()` reads distinct strings off `product_variants.colour`;
`warehouse.py:129` and `admin.py:491` both treat colour as a free string.
**This is the largest untouched piece of the brief.**

---

## D. Tests

`pytest -q` → **203 passed, 1 warning, 115.46s, exit 0** (a harmless
`StarletteDeprecationWarning` about `httpx`).

| File | Lines | Covers |
| --- | --- | --- |
| `backend/tests/test_api.py` | **5,608** | the broad suite, 159 `test_` functions |
| `backend/tests/test_receiving.py` | 398 | §2 end to end |
| `backend/tests/test_scan_and_labels.py` | 324 | §3 `copies` + §4 `scan` |
| `backend/tests/test_roles.py` | 61 | §5.1 |
| `backend/tests/test_images.py` | 324 | covers, per-colour order (untracked) |
| `backend/tests/test_delivery.py` | 339 | in-flight work (untracked) |
| `backend/tests/test_schema.py` | 112 | |
| `backend/tests/conftest.py` | 175 | |

`test_receiving.py`: `test_twenty_white_shoes_from_the_bench_to_the_shelf` (88),
`…black_ones_are_a_second_receipt_on_the_same_card` (154),
`…second_receipt_of_the_same_variant_adds_up` (194), `…receipt_is_idempotent`
(226), `…shelve_is_idempotent…` (246), `…mistyped_cell_is_refused…` (274),
`…unanswered_question_waits_on_the_queue_and_the_dashboard` (299),
`…sold_straight_from_the_receiving_area_are_not_shelved_twice` (339),
`…ledger_reads_the_two_moments_back` (377).

`test_scan_and_labels.py`: `…labels_say_how_many_to_print_in_the_typed_order`
(138), `…summed_copies` (162), `…reprint_by_variant_id_is_one_copy_each…` (177),
`scan_answers_a_barcode…` (198), `…a_sku…` (224),
`…a_zero_stock_variant_with_an_empty_places_list` (239),
`…a_cell_code_with_what_stands_in_it` (268), `…refuses_an_unknown_code…` (301),
`…is_for_warehouse_eyes_only` (317).

`test_roles.py`: `test_the_enum_has_no_seller` (21),
`test_the_seed_writes_no_seller` (31),
`test_catalog_writes_refuse_the_bench_and_accept_the_owner` (41).

**Note:** §9's "append at the end of `test_api.py`" is already contradicted —
the last three agents each wrote their own file. Follow the repo's convention
(one file per subject), not the brief.

---

## E. Ownership check — collision flags

All §9 paths exist except `publish.tsx` (**gone**, W2 is told to delete it),
`scan.tsx` (**exists**, W3 is told it is new) and `card-form/` (correctly new).

### 🚩 `backend/app/schemas.py` (2,965) — B1/B2 clean, **B3 homeless**

- B1: `CardPriceIn` 1173, `ReceiptSizeIn` 1189, `ReceiptIn` 1196,
  `ReceiptLabelOut` 1244, `ReceiptOut` 1263, `ReceiptShelveIn` 1279,
  `ReceiptShelvedOut` 1285, `ReceiptWaitingOut` 1303, `RetireIn` 1320,
  `VocabOut` 1326
- B2: `ProductLabelOut` 1355, `CellLabelOut` 1376, `LabelSheetOut` 1383,
  `ScanVariantOut` 1395, `ScanOut` 1409
- Contiguous and adjacent — separable. But §5.3's palette/size-system schemas
  are B3's and §9 never grants B3 the file. **Add a third region or give B3
  `schemas_reference.py`.**
- 87 uncommitted lines removed here (delivery windows). Base on a clean tree.

### 🚩 `web/src/lib/queries.ts` (1,622) — **does not split four ways**

Sections: `reads` 143, `writes` 560, `writing a card` 738, `last mile` 896,
`returns` 1216, `one order` 1296, `pickup runs` 1324, `the catalogue's photos`
1360, `damaged goods` 1419, **`receiving (receipts)` 1457**,
**`scan + labels` 1606**.

| Agent | Hooks | Where |
| --- | --- | --- |
| **W1** | `useVocab` 172, `useReceive` 1518, `useShelveReceipt` 1559, `useWaitingReceipts` 1583, `useRunLabels` 1597 | 1457–1604 contiguous **except `useVocab` at 172** |
| **W2** | `useCategories` 255, `useVariants` 266, `useProduct` 274, `useSpecs` 282, `useImages` 290, `usePriceCard` 741, `useFileCard` 758, `useWriteSpecs` 816, `useCreateProduct` 829, `useRetireVariant` 842, `useSetGrid` 855, `useAddImage` 872, `usePublish` 886, `useWriteCategory` 1034, `useDeleteImage` 1372, `useMakeCover` 1403 | **scattered over 255–1418** |
| **W2b** | `useProducts` 240, `useDashboard` 312 | **inside W2's range** |
| **W3** | `useLabels` 232, `useWhereIs` 164, `useScan` 1617 | **inside W2b's and W2's ranges** |

Three agents would edit lines 164–312. **Either W2/W2b agree a hard boundary,
or a serial pre-pass splits `queries.ts` into a `queries/` folder.** 89
uncommitted lines here too.

### 🚩 Shared files §9 did not anticipate

| File | Lines | Needed by |
| --- | --- | --- |
| `web/src/lib/types.ts` | 1,117 | W1 (`Receipt`, `WaitingReceipt`), W2 (`AdminProduct`, `AdminImage`, `Spec`, new colour/size types), W2b (`AdminProduct`), W3 (`ProductLabel` 209, `CellLabel` 218, `LabelSheet` 225, `RollProductLabel` 1093, `ScanAnswer` 1112) — **four-way, unowned** |
| `backend/app/i18n.py` | — | B1 (`receipt_needs_a_colour` 346, `receipt_sized_or_not` 361, `receipt_needs_a_name` 379, `receipt_already_shelved` 700, `tile_labelled_unshelved` 695), B2 (`labels_need_a_selection` 893), B3 (palette strings) — **three-way, unowned** |
| `web/src/components/label-roll.tsx` | 263 | W3 needs it for §3 but §9 lists only `labels.tsx`; also imported by W1's `qabul.tsx:41` |
| `web/src/components/barcode.tsx` | 77 | imported by `label-roll.tsx:30`; unowned |
| `web/src/components/photo-step.tsx` | 669 | W2 owns it; imported by W2b's `products.tsx:63`, W1's `qabul.tsx:43`, plus `orders.tsx:52`, `returns.tsx:66`, `pickups.tsx:48`. **Changing `mediaUrl`'s signature breaks five screens.** |
| `web/src/components/card-editor.tsx` | 394 | W2 owns it; imported by W2b's `products.tsx:61`. The §9 "agree the props first" note is real and **already wired** — W2 must keep `Words`/`Specs`/`Filing`/`Pricing` exported until W2b lands. |
| `backend/app/models.py` | 1,406 | B3's; 25 uncommitted lines |
| `web/src/components/data-table.tsx` | 1,000+ | W2b needs the table half of §5A.1's toggle; unowned and dirty |
| `backend/tests/test_api.py` | 5,608 | §9 sends all three B agents to one tail — the worst merge shape |

### Non-collisions worth noting

- `backend/app/routers/shelves.py` (1,468) is B2's alone — large surface, no overlap.
- `backend/app/routers/dashboard.py` — B1's "one tile" (`labelled_unshelved`,
  94–112) **already exists** and imports `receipts_waiting` from `warehouse.py`.
- `web/src/App.tsx` (124) — already clean of the publish route.

---

## F. The verdict list

### Already true — do not redo

| § | Claim | Evidence |
| --- | --- | --- |
| §2 | One submission, two moments, one screen | `qabul.tsx:127,332,1135` |
| §2 | No cell at the bench | `warehouse.py:199`, `ReceiptIn` has no cell |
| §2.1 | One receipt, one colour | `qabul.tsx:80`, `ReceiptIn.colour` |
| §2.1 | Cost asked once, at the bench | `Draft.unitCost`, `Draft.fare` |
| §2.1 | Sizeless kinds show no size column | `VocabOut.sizeless` (`warehouse.py:146`) |
| §2.2 | Cell answered by scanning its label | `qabul.tsx:201` → `putAway` |
| §2.2 | Queue survives a reload, on `/qabul` and the dashboard | `warehouse.py:494`, `dashboard.py:94`, `qabul.tsx:1398` |
| §2.2 | `QABUL` is sellable, nothing is lost | `models.SELLABLE_KINDS`; `test_receiving.py:339` |
| §2.4 | `qop` / `pilla` / `saralash` gone from every screen | zero hits in `web/src/` (but see contradiction 3) |
| §2.4 | Supply row written by the receipt, never by hand | `warehouse.py:634`; `test_api.py:1487` |
| §3.1 | 58 × 40 mm, one label per page, one constant | `label-roll.tsx:43,46` |
| §3.1 | `copies` pages, grouped in typed order | `label-roll.tsx:68,94`; `shelves.py:1163` |
| §3.1 | The two-checkbox support text on screen | `qabul.tsx:1300` |
| §3.2 | Size biggest, `n/copies`, permanent barcode, no price | `label-roll.tsx:205`; `index.css:204` |
| §3.3 | Cell labels, code large with barcode under it | `label-roll.tsx:153,228`; `index.css:265` |
| §4 | Keyboard-wedge gun + `BarcodeDetector`, focused field wins | `scan.tsx:45,53,107,233` |
| §4 | One router, `GET /warehouse/scan` | `shelves.py:187` |
| §4 | Listening on all four screens | `qabul.tsx:246`, `shelf-map.tsx:352`, `picking.tsx:223`, `counts.tsx:76,200` |
| §4 | The `find` / `where-is` correction | verified exactly |
| §5.1 | `UserRole.SELLER` deleted everywhere, enum included | §B; `test_roles.py`, `test_api.py:4204` |
| §5.4 | Publishing lives on the card | `products.tsx:748` |
| §5.5 | Camera / paste / drag-drop / optimistic / per-colour rule | `photo-step.tsx` |
| §5A.2 | Dashboard redrawn | `dashboard.tsx:16–41,174,321` |
| §6.1 | `RECEIPT` into `QABUL` then `PUTAWAY` out — the corrected rule | `warehouse.py:199,388`; `test_receiving.py:377` |
| §6.7 | Idempotency on both warehouse writes | `warehouse.py:213,415` |
| §7.13 | `pytest -q` green | 203 passed |
| §8 | `publish.tsx` deleted | `5a0dd7e`, −392 |
| §8 | Sack machinery gone from `qabul.tsx` | 2,388 → 1,451 |
| §8 | `POST /warehouse/supplies` removed | 405 |

### The code contradicts the brief — take these to the owner

1. **§9's whole premise is spent.** B1, B2, the roles half of B3, W1 and W3 have
   no work left. Re-scope to: one backend agent for §5.3 reference data, one or
   two web agents for §5.2/§5.4, one web agent for §5A.1.
2. **§1 and §8 cite 2,388 lines for `qabul.tsx`.** It is 1,451 and already
   rebuilt; further shrinking would now delete working §2 code.
3. **§7.14 is violated once, innocently.** `data-table.tsx:645` uses
   `aria-label={open ? "Saralashni yopish" : "Saralash"}` — that is *sorting a
   table*, the correct Uzbek word, on every one of the ten shared tables.
   **Do not let an agent rename it.** The criterion needs a carve-out.
4. **§9 says `scan.tsx` is new.** It exists, 336 lines, and five screens import it.
5. **§9 gives `schemas.py` to B1 and B2 only, but §5.3 is B3's.**
6. **§9's `queries.ts` four-way split is not achievable** as the file stands.
7. **§9 sends three backend agents to one `test_api.py` tail.** The repo now
   uses per-subject test files.
8. **§5.2's "one long form in one column" does not exist.** `card-editor.tsx`
   is four sibling panels with four saves; `Filing:234` is a flat chip list
   where §5.2 ·1 wants a cascade. This is the real remaining work, and it is
   *larger* than §9 implies because it replaces a shipped, working editor
   rather than a deleted screen.
9. **The one allowed dependency is unpicked** — no TipTap, no Lexical. §5.2 ·4
   blocks on that decision.
10. **`colours` and `size_systems` do not exist in any form** — no tables,
    seeds, endpoints, schemas or migration. §5.3 is 100% greenfield and
    §5.2 ·6 blocks on it entirely.
11. **`web/src/lib/types.ts:305–320` still declares `PileSize` and `Pile`,**
    and nothing imports them. Dead types from the deleted flow.
12. **The tree is dirty with 67 files of unrelated in-flight work**, including
    an untracked head migration `a91d2fc3352c` and untracked `test_delivery.py`
    / `test_images.py`. No wave can start against this base.
