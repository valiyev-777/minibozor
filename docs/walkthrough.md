# Walking the whole thing by hand

One sale, from a seller who does not yet have the product to a seller reading
what they are owed for it, through every interface that exists.

Every step below was run against a live stack before it was written down —
first through the API, then again by `curl` against `./dev.sh` — so the
endpoints, the payloads and the numbers are what actually happens, not what
ought to. **Three steps cannot be done by clicking**, and those are marked
`GAP` with the reason and the one command that gets you past them. They are
not fixed here; this document is about walking the system, not changing it.

---

## Before you start

```bash
./dev.sh                                              # everything, one command
cd backend && .venv/bin/python -m tools.dev_accounts --apply
```

The second command is not optional. The seed writes a customer and an admin;
the operator, warehouse, courier and seller accounts do not exist until you
make them, so three of the five interfaces have nobody to let in.

**This walk writes to your database** — a card, an offer, a batch, an order, a
statement. If that is your real development data, take a backup first; it is
one command and there is a restore beside it:

```bash
cd backend && tools/backup.sh                 # → backups/sqlite-<stamp>.db
# ... walk, then if you want it back:
tools/restore.sh ../backups/sqlite-<stamp>.db
```

Or walk against a scratch database instead and leave your own alone:

```bash
export MB_DATABASE_URL="sqlite:///$PWD/backend/walk.db"
cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m app.seed \
  && .venv/bin/python -m tools.dev_accounts --apply && cd ..
./dev.sh
```

## The cast

Every interface uses the same login: type the phone number, then the SMS code
**123456**. There is no password. Dev builds return the code in the response,
so no gateway is involved.

| Role | Phone | Interface | Address |
|---|---|---|---|
| admin | `+998900000001` | backoffice | <http://localhost:5173> |
| operator | `+998900000002` | backoffice | <http://localhost:5173> |
| warehouse | `+998900000003` | backoffice | <http://localhost:5173> |
| seller | `+998900000005` | seller cabinet | <http://localhost:5174> |
| courier | `+998900000004` | courier PWA | <http://localhost:5175> |
| customer | `+998901234567` | Android / iOS app | — (PIN `1234`) |

The backoffice shows a different sidebar to each of its three roles, so
"backoffice" below always says which of them you should be signed in as. If
you are on the wrong one the row simply is not in the menu.

---

## 0. Sign in to all three panels

Use three browser windows, or three profiles — each panel keeps its own
session, but they share `localhost`, so signing into one as a different role in
the same window will confuse you rather than the software.

**What you should see.** The backoffice lands the admin on **Moderatsiya** and
the warehouse on **Javon**; the seller cabinet lands on **Boshqaruv**; the
courier PWA lands on **Reys**. A role that reaches a screen that is not theirs
is a bug — the sidebar only lists what the role may open.

---

## 1. The seller proposes a product · seller cabinet

The catalogue belongs to the platform: a seller attaches a price to a card that
already exists and cannot open their own copy of one. What they *can* do is
propose a card, which lands in moderation.

1. Sign in at <http://localhost:5174> as `+998900000005`.
2. Go to **Katalog**.
3. Top right: **Yo'q tovarni taklif qilish**.
4. Fill in **Nomi** (`Choynak 1.7 L`), pick a **Turkum**, put something in
   **Taxminiy narx** (`189000`). A SKU is required and must be unique.
5. **Moderatsiyaga yuborish**.

**What you should see.** A dialog headed **Moderatsiyaga yuborildi** with the
badge **Moderatsiyada**. `POST /staff/catalog/proposals` → `201`, and the card
comes back with `status: "moderating"`.

It is *not* in the shop: `GET /api/v1/products/{id}` answers `404` for it,
because every customer path is narrowed to published cards.

> **GAP — a seller cannot see what became of their proposal.**
> The dialog says so itself, and it is now out of date: the endpoint it says
> does not exist was added later. `GET /staff/catalog/proposals` returns this
> seller's proposals with `status` and `moderation_note` — the refusal reason —
> and nothing in `seller/src` calls it. So an approved card turns up in the
> catalogue and can be found there, and **a refused one is invisible from the
> cabinet**. Until a screen is added, the seller reads it with:
> ```bash
> curl -s localhost:8000/api/v1/staff/catalog/proposals \
>   -H "Authorization: Bearer $SELLER_TOKEN" | python3 -m json.tool
> ```

---

## 2. The admin publishes it · backoffice

1. Sign in at <http://localhost:5173> as `+998900000001`.
2. **Moderatsiya** — it is the admin's landing screen, and the sidebar row
   carries a count.
3. Find the row. Press **E'lon qilish**.

**What you should see.** The count on the sidebar drops by one and the row
leaves the queue. `POST /staff/catalog/products/{id}/status` → `200` with
`status: "published"`, and the card is now `200` on the customer endpoint.

**Refusing instead** is the other half: **Rad etish** asks for a **Sabab** and
will not proceed without one — *"Sababsiz rad etib bo'lmaydi"*. The reason is
what the seller is supposed to act on, which is what makes the gap in step 1
worth knowing about.

---

## 3. The seller puts a price on it · seller cabinet

Publishing gave the card a place in the catalogue. It still has no price and
nothing on the shelf, so nobody can buy it.

1. Back to the seller cabinet, **Katalog**.
2. Search its name or SKU. The filter **Hali menda yo'q** is the useful one —
   cards this seller does not yet offer.
3. Press the row's action to open **Taklif qo'yish**.
4. Enter **Narxim (so'm)** — `189000`. **Chizilgan narx** is the struck-through
   one and is optional.
5. Save.

**What you should see.** A dialog **Taklif qo'yildi** showing **Narxingiz** and
**Javonda** — and Javonda reads **0**, which is correct and is the point of the
next step. `POST /staff/offers` → `201`.

The offer now appears under **Takliflarim**.

---

## 4. The goods arrive · seller declares, warehouse counts

Under this model the goods sit in *our* warehouse and the seller owns them. So
the two sides of the shelf answer to different people: **the seller sets the
price, the warehouse sets the count.** A seller cannot write a stock figure —
they would be promising goods nobody has received.

**Seller** — cabinet, **Partiyalar**:

1. Create a batch and add a line: the offer from step 3, quantity `5`.
2. Send it.

**What you should see.** A batch code the *platform* issued — `SUP-000001` —
not the seller's own reference. Status **declared**. `POST /staff/supplies` →
`201`.

**Warehouse** — backoffice as `+998900000003`, **Partiyalar**:

3. Open `SUP-000001`. Enter the received quantity per line — `5` — and book it
   in.

**What you should see.** Status **received**. Then on **Javon**, the offer reads
`on_hand 5`, `reserved 0`, `sellable 5`. `POST /staff/supplies/{id}/receive`
→ `200`; `GET /staff/offers/{id}/shelf` → one cell per countable place.

**Harakatlar** (movements) now has `intake` rows against it: the shelf figure
is the running sum of that ledger, not a number anybody typed.

---

## 5. The customer buys it

> **GAP — there is no customer app in a browser.**
> The shopper's 47 screens are the Android and iOS clients, built in Android
> Studio and Xcode. There is no web build, so this step cannot be clicked from
> the desktop at all.
>
> **On a device or emulator:** both debug builds point at this same API —
> `http://10.0.2.2:8000` from an Android emulator, `http://localhost:8000` from
> an iOS simulator. `./dev.sh` starts the backend on `0.0.0.0`, and
> `backend/run.sh` opens the `adb reverse` tunnel for a physical phone. Sign in
> as `+998901234567`, code `123456`, PIN `1234`.
>
> **From the desktop**, by API — this is the exact sequence, verified:
> ```bash
> A=http://localhost:8000/api/v1
> CODE=$(curl -s -X POST $A/auth/otp/request -H 'content-type: application/json' \
>   -d '{"phone":"+998901234567"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["dev_code"])')
> CUST=$(curl -s -X POST $A/auth/otp/verify -H 'content-type: application/json' \
>   -d "{\"phone\":\"+998901234567\",\"code\":\"$CODE\"}" \
>   | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')
> H="Authorization: Bearer $CUST"
>
> curl -s -X DELETE $A/cart -H "$H" -o /dev/null
> curl -s -X POST $A/cart/items -H "$H" -H 'content-type: application/json' \
>   -d '{"product_id":PUT_THE_ID_HERE,"quantity":2}'
> ADDR=$(curl -s $A/addresses -H "$H" | python3 -c 'import json,sys;print(json.load(sys.stdin)[0]["id"])')
> curl -s -X POST $A/orders -H "$H" -H 'content-type: application/json' \
>   -d "{\"address_id\":$ADDR}"
> ```

**What you should see.** An order code like `#A-104730`, `status: "placed"`,
and a total of `397000` — two at 189 000 plus 19 000 delivery, because free
delivery starts at 250 000 and this basket is under it.

**A card with sizes or colours needs one named.** `{"product_id": N}` alone is
a `422` for such a product: a sale that names no leaf comes off the offer's
total and off no colour at all, and there is no working out afterwards which
one it was. Add `"variant_id"` (and `"color_variant_id"` where the colours have
sizes). The card you proposed in step 1 has no variants, which is why the
plain form works for it.

Watch **Javon** in the warehouse panel while you do this: `sellable` drops and
`reserved` rises. The goods are held, not sold — holding is derived from the
basket and the unpaid order, never stored, so it cannot be leaked or released
twice.

---

## 6. The operator moves it along · backoffice

1. Sign in as `+998900000002`, **Buyurtmalar**.
2. Find the order. Press **Yig'ishga berish** → status **YIG'ILMOQDA**.
3. Press **Kuryerga topshirish** → status **YO'LDA**.

**What you should see.** The status label changes on each press, and the order
will not skip a step — `placed → shipped` is refused, because the legal moves
live in one table and nowhere else.

> **GAP — no panel can hand the order to a named courier.**
> `POST /staff/orders/{id}/courier` exists and works, and **nothing in
> `backoffice/src` calls it** — there is no courier picker on the orders screen.
> Without it the round is empty: `GET /courier/orders` answers `[]`, so the
> courier PWA shows no stops, and trying to deliver anyway is a `403`
> — *"Bu buyurtma sizga biriktirilmagan"*.
>
> So step 7 needs this one call first:
> ```bash
> A=http://localhost:8000/api/v1
> OPER=<operator token>       # same OTP flow as above, phone +998900000002
> CID=$(curl -s $A/staff/couriers -H "Authorization: Bearer $OPER" \
>   | python3 -c 'import json,sys;print(json.load(sys.stdin)[0]["id"])')
> curl -s -X POST $A/staff/orders/<ORDER_ID>/courier \
>   -H "Authorization: Bearer $OPER" -H 'content-type: application/json' \
>   -d "{\"courier_id\":$CID}"
> ```
> It answers `200` and the round has one stop.

---

## 7. The courier delivers · courier PWA

1. Open <http://localhost:5175> on a phone-shaped window and sign in as
   `+998900000004`.
2. **Smena** — open a shift. A courier collects cash at doors all day and hands
   it over at the end; without a shift there is nothing to reconcile against.
3. **Reys** — the round. The order from step 6 is the stop.
4. Open the stop, then deliver it. **Recipient name is required**; the photo is
   optional.

**What you should see.** The stop reads **delivered**, and the customer's own
order now says `delivered` too. `POST /courier/orders/{id}/deliver` → `200`.

**Every write from this app carries an `Idempotency-Key`** and it is required,
not optional — the app queues actions offline and will send one twice. Sending
the same key again replays the first answer instead of delivering twice.
**Outbox** is where a queued action waits; turn the network off in dev tools
and deliver, and it lands there.

The sale is only now a sale: not when the order was placed — it may be called
off — and not when it was paid, because cash orders are paid at the door.

---

## 8. The seller reads what they are owed · seller cabinet

**Right away**, before any admin does anything:

> **GAP — the running total is not on any screen.**
> `GET /staff/payouts/current` answers "how is this month going so far" with
> the same arithmetic a real statement uses, marked `is_final: false`, and
> nothing in `seller/src` calls it. Until it is on the dashboard:
> ```bash
> curl -s localhost:8000/api/v1/staff/payouts/current \
>   -H "Authorization: Bearer $SELLER_TOKEN" | python3 -m json.tool
> ```
> For this walk it answers `gross_sales: 378000` — the two units at 189 000 —
> with `is_final: false`, because goods keep arriving and the figure will move.

**Then the closed statement**, which is the number that gets paid. An admin
does the closing, in the backoffice under **Moliya**: open a period, generate,
close. Or by API:

```bash
A=http://localhost:8000/api/v1
ADMIN=<admin token>
H="Authorization: Bearer $ADMIN"
PER=$(curl -s -X POST $A/staff/payouts/periods -H "$H" -H 'content-type: application/json' \
  -d '{"starts_on":"2051-01-01","ends_on":"2051-12-31","label":"Sinov"}' \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
curl -s -X POST $A/staff/payouts/periods/$PER/generate -H "$H" -o /dev/null
curl -s -X POST $A/staff/payouts/periods/$PER/close -H "$H" -o /dev/null
```

Now, in the seller cabinet: **Hisobotlar**, and open the row.

**What you should see.** For this walk: **payable 134 000** made of **4 lines** —
the sale at 378 000, the commission taken off it, the handling fee, and storage.
Not one netted number: a seller looking at one line of one order wants the
price they set, the cut we took and the handling we charged as three figures.

`payable` equals the sum of the lines exactly. That is an invariant with a test
behind it — a total that can drift from its own composition is a total nobody
can defend in an argument.

Two things about it are deliberate and worth checking:

* **The commission is the rate it sold at**, not today's. Change the seller's
  `commission_percent` in the backoffice under **Sotuvchilar** and reopen the
  statement: the figure does not move. The rate was captured onto the order
  line the day it sold.
* **A closed statement is finished.** Change a weight band under **Moliya** and
  the closed statement does not move either, while the next open period is
  worked out at the new rate.

---

## The three gaps, together

None of these is a backend gap — every endpoint exists, works, and is
exercised by the test suite. They are screens that were not built, or were
built before the endpoint existed.

| What | Where it should live | Endpoint that exists | Effect |
|---|---|---|---|
| A seller cannot see a refused proposal or its reason | seller cabinet, near **Katalog** / a "Takliflarim" tab | `GET /staff/catalog/proposals` | a seller is asked to fix something without being told what was wrong |
| No panel can assign an order to a courier | backoffice **Buyurtmalar** | `POST /staff/orders/{id}/courier`, `GET /staff/couriers` | the courier's round is always empty; delivery is a 403 |
| The seller's running total is on no screen | seller cabinet **Boshqaruv** | `GET /staff/payouts/current` | "how is this month going" has no answer between payouts |

The `Propose.tsx` dialog also carries a comment saying the proposals endpoint
does not exist. It does now; the comment is stale.

## When something does not work

```bash
./dev.sh status          # which service is down, and why the backend is unhappy
tail -f .dev-logs/backend.log
tail -f .dev-logs/seller.log
```

A `401` everywhere in a panel means the token expired — sign in again; access
tokens last 30 minutes. A request that never leaves the browser, with a CORS
complaint in the console, means the panel's origin is not named in
`MB_CORS_ORIGINS`; all three dev ports are in the default, on both `localhost`
and `127.0.0.1`, because those are different origins to a browser.
