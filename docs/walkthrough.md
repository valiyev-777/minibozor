# Walking the whole thing by hand

One shirt, from a seller who has not sent it yet to that same shirt back on
the shelf after a customer changed their mind — through every interface that
exists.

Every step below was **walked in a browser** against a live stack before it
was written down, driving the three panels the way a person does: typing in
the form, pressing the button, reading what came back. So the screen names,
the button words and the numbers are what actually happens rather than what
ought to.

**Two steps cannot be done by clicking**, and both are the customer's: there
is no shopper's app in a browser. Those are marked `APP` with the API call
that stands in for the phone. Everything else is somebody on a screen.

---

## Before you start

```bash
./dev.sh                                              # everything, one command
cd backend && .venv/bin/python -m tools.dev_accounts --apply
```

The second command is not optional. The seed writes a customer and an admin;
the operator, warehouse, courier and seller accounts do not exist until you
make them, so four of the six interfaces have nobody to let in.

**This walk writes to your database** — a product, a batch, an order, a
return, a settlement line. If that is your real development data, take a
backup first; it is one command and there is a restore beside it:

```bash
cd backend && tools/backup.sh                 # → backups/sqlite-<stamp>.db
# ... walk, then if you want it back:
tools/restore.sh ../backups/sqlite-<stamp>.db
```

Or walk against a scratch database and leave your own alone:

```bash
export MB_DATABASE_URL="sqlite:///$PWD/backend/walk.db"
cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m app.seed \
  && .venv/bin/python -m tools.dev_accounts --apply && cd ..
./dev.sh
```

## The cast

Every interface uses the same login: type the phone number, then the SMS code
**123456**. There is no password. Dev builds answer with the code and the
login screen shows it, so no gateway is involved.

| Role | Phone | Interface | Address |
|---|---|---|---|
| seller | `+998900000005` | seller cabinet | <http://localhost:5174> |
| warehouse | `+998900000003` | backoffice | <http://localhost:5173> |
| operator | `+998900000002` | backoffice | <http://localhost:5173> |
| admin | `+998900000001` | backoffice | <http://localhost:5173> |
| courier | `+998900000004` | courier PWA | <http://localhost:5175> |
| customer | `+998901234567` | Android / iOS app | — (PIN `1234`) |

The backoffice shows a different menu to each of its three roles — one table,
`backoffice/src/lib/nav.ts`, draws the menu *and* guards the routes — so
"backoffice" below always says which of them you should be signed in as. A
role that types the path of a screen that is not theirs is sent to their own
landing screen rather than to an error.

Use separate browser windows or profiles. Each panel keeps its own session but
they share `localhost`, so signing into two of them as different roles in one
window will confuse you rather than the software.

---

## 0. Sign in to all three

**What you should see.** The seller lands on **Tovarlarim**, the warehouse on
**Topshiruvlar**, the operator on **Buyurtmalar**, the admin on
**Boshqaruv** — whatever each of them does first. The courier lands on
**Bugun**.

---

## 1. The seller adds a product · seller cabinet `:5174`

**Tovarlarim → Yangi tovar.** One form, and it is the whole submission: the
name, the category, the description, the photographs, the price, and a colour
with the sizes under it — each size with how many are coming.

Fill it in, add a picture, put one colour (`Oq`) with one size (`M`, quantity
`3`), and press **Topshirish**.

**What you should see.** A green toast naming the product and a batch code —
`SUP-000013` — and the screen you land on is the product, reading **Omborga
kutilmoqda**. The grid shows `E'lon qilingan 3`, `Omborda 0`, `Sotuvga tayyor
0`.

That nought is the point. Nothing you typed reached a stock figure: the
quantities became `declared_quantity` on a supply line, and the shelf does not
move until somebody counts the box. The product is not in the shop either —
`GET /products/{id}` is a 404 for it.

## 2. The warehouse counts it in · backoffice `:5173`, warehouse

**Topshiruvlar** opens on `status=declared`, which is the day's work. The
batch from step 1 is at the top; open it.

The receive screen shows the promise and an empty box beside it. **The boxes
start empty on purpose** — a pre-filled form is a form somebody accepts
without counting. Press **Hammasini to'liq** for the common case, or type what
you actually found; the difference column updates as you type. Write a note
(`Qadoq butun`) and press **Qabul qilish**.

**What you should see.** Back on the list, and the batch is gone from the
`Kutilmoqda` filter.

**And this is the step that publishes the product.** Go back to the seller's
product screen: it now reads **Sotuvda**, with `Omborda 3` and `Sotuvga tayyor
3`, and a per-cell **Olib ketaman** button that was not there before. There is
no approve button anywhere in the backoffice, because "approval" in this shop
is somebody confirming the goods turned up.

> **Try the other half.** Submit a second product and press **Rad etish**
> instead, with a reason. The batch is refused *and* the product goes down
> with it — the seller's screen reads **Rad etildi** with your sentence on it,
> in red, under the title. It is the only answer they get about why their
> product is not in the shop, which is why the reason is required.

## 3. The customer buys it

> **APP — there is no shopper's app in a browser.** Android and iOS are the
> fifth and sixth interfaces and they talk to this same API. The two customer
> steps in this walk go through it directly.

```bash
cd backend && .venv/bin/python - <<'PY'
import json, urllib.request
BASE = "http://localhost:8000/api/v1"

def call(path, token=None, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        method=method or ("POST" if data is not None else "GET"),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req) as res:
        raw = res.read()
        return json.loads(raw) if raw else None

call("/auth/otp/request", body={"phone": "+998901234567"})
me = call("/auth/otp/verify", body={"phone": "+998901234567", "code": "123456"})
token = me["access_token"]

product = int(input("product id from the seller's URL: "))
page = call(f"/products/{product}")
colour = next(v for v in page["variants"] if v["kind"] == "color")
size = next(v for v in page["variants"]
            if v["kind"] == "size" and v["parent_id"] == colour["id"])
call("/cart", token, method="DELETE")
call("/cart/items", token, body={"product_id": product,
                                 "color_variant_id": colour["id"],
                                 "variant_id": size["id"], "quantity": 1})
address = call("/addresses", token)[0]
order = call("/orders", token, body={"address_id": address["id"]})
print("order", order["code"], "id", order["id"])
PY
```

Keep the code and the id; the rest of the walk needs them.

## 4. The warehouse picks it · backoffice, warehouse

**Buyurtmalar** opens on `Yangi` for the warehouse — the orders with something
to do at a bench. Find the code and press **Yig'ildi**.

**What you should see.** The row moves to `Yig'ilmoqda`, and the button on it
becomes **Kuryerga berildi**. The buttons come from the order's own
`next_statuses`, so a delivered order offers neither.

There is no **Bekor qilish** on this screen and none on the row. A picker who
could call off a sale from the packing bench would be deciding that a customer
is not getting their order; the person who can telephone them is the operator,
and the server refuses a cancel from a warehouse account.

## 5. The operator sends a courier · backoffice, operator

**Buyurtmalar → the order's code.** The detail screen is the customer's own
view of the order — the same rendering the app shows, because an operator on
the telephone is being asked about what the customer is looking at.

Under it, **Kuryer biriktirish**: pick the courier, give them a position in
the round (`1`), press the button.

**What you should see.** A toast, and the courier's name on the order row back
on the queue.

Then, as the **warehouse** again, press **Kuryerga berildi**. The order is
`shipped` and on somebody's round.

## 6. The courier delivers · courier PWA `:5175`

Open it on a phone if you can — `npm run dev -- --host` in `courier/` puts it
on the LAN — or narrow a browser window. **Bugun** is the round: deliveries
and collections in one list, because they are the same thing to the person
doing them.

Tap the order. The address is the largest thing on the screen and the
telephone number is a `tel:` link, because those are what the screen is for
while walking up to the building.

Type who took it and press **Yetkazdim**.

**What you should see.** A toast, and the stop is gone from the round.

> **Try the cash guard.** On a cash order the box is pre-filled with what is
> owed. Change it to something else and press the button: the server refuses
> it and the toast is its own sentence — *"Naqd 148 000 so'm olinishi kerak,
> 100 000 ko'rsatilgan"*. Correct it and press again; it goes through. That
> second press working is not free — every write carries an
> `Idempotency-Key`, and `courier/src/api/keys.ts` bumps an attempt counter on
> a refusal precisely so a corrected figure is a new request rather than a
> replay of the refusal.

> **Try the other button.** **Yetkaza olmadim** needs a reason and does *not*
> change the order's status: an attempt is a row, not a state, and the order
> is still on its way. Press it three times and the operator can see three
> failures and decide to call the order off — which is the only place that
> decision lives.

## 7. The customer asks it back

> **APP** again — the second and last of the two.

```bash
cd backend && .venv/bin/python - <<'PY'
# ... the same `call` and sign-in as step 3 ...
order_id = int(input("order id: "))
request = call(f"/orders/{order_id}/return", token,
               body={"reason": "Rangi rasmdagidek emas"})
print("return request", request["id"])
PY
```

## 8. The operator decides the money · backoffice, operator

**Qaytarishlar → the order's code.** Two panels: the request, and what the
operator may do with it. Press **Tasdiqlash**.

**What you should see.** The status pill becomes `Tasdiqlangan`, and the
buttons change to the two refund ones — **Pulni qaytarish · Ha — javonga** and
**· Yo'q — hisobdan**. `restock` has no default on the server and none here:
what came back whole belongs on the shelf and what came back damaged belongs
on nobody's count, and a default would be a count moving, or failing to move,
by omission.

Leave the money for now, or pay it back — the goods are a separate question
and the rest of the walk is about them.

> **Optional: send a van.** **Yig'uv reyslari → Yangi reys** builds a
> collection run from the approved requests, and the courier's round grows a
> row for it. On the phone, mark each door **Oldim** or **Olmadim** with a
> reason and press **Reysni yopish** — one write for the whole run, because a
> half-sent run is one the warehouse cannot book in. Then, as the warehouse,
> **Omborga qabul qilish**.
>
> `collected` and `received` are two different people's claims and are kept
> apart on purpose: collapsing them would make "the courier collected it and
> it never reached us" unsayable.

## 9. The warehouse says what arrived · backoffice, warehouse

The same screen, `/returns/{id}`, shows the warehouse a different panel:
**Tekshirish**, with a note field and two buttons.

Write `Yorliqlari joyida` and press **Buzilmagan**.

**What you should see.** The verdict as a green pill, and the panel gone —
there is no second verdict, because the first one is what the seller was told
and what their deadline runs from.

## 10. The seller decides · seller cabinet

**Qaytarishlar.** The request is there with the warehouse's verdict on it, the
deadline in days — *"15 sen 2026 · 7 kun"* — and two buttons: **Sotuvga
qaytarildi** and **Olib ketaman**.

Press **Sotuvga qaytarildi**.

**What you should see.** A toast, a `Qayta sotuvga` pill, the decision's date,
and the buttons gone.

> **The buttons came from the server.** `seller_decisions` on the row is the
> list of moves still open, and a *damaged* parcel carries only
> `take_back` — damaged goods do not go back on sale, and that rule is
> enforced in `POST /staff/returns/{id}/decide` rather than copied into three
> clients. Inspect one as `Buzilgan` and the relist button is simply not
> there.

> **And nobody has to press anything.** If the seller says nothing for seven
> days, `app.returns.sweep_overdue` relists it for them — silence expires into
> the answer that costs them least. The sweep runs off the side of any returns
> list rather than from a scheduler this system does not have.

## 11. And the shelf tells the whole story

**Backoffice → Qoldiq harakati**, as the warehouse. Filter by nothing and find
the product's rows:

```
intake            +3   Qadoq butun
sale              -1   Yakuniy ko'ylak × 1
customer_return   +1   Qayta sotuvga
```

Three in, one sold, one back. The seller's product screen reads `Omborda 3`
again, and that figure is not stored anywhere — it is the sum of those three
rows. A disputed count is not an opinion; it is this list, and every row on it
names a person and a reason.

**Seller cabinet → Hisob** closes the loop: sold, returned, and what is
payable, with the lines they add up from and a warning that the period is not
final.

---

## What is still not clickable

Two steps, and they are the same one: **the customer**. Steps 3 and 7 go
through the API because the shopper's interface is the Android and iOS apps,
which are a separate stage of work and were deliberately not touched by the
panels rebuild.

Everything else in the flow is a screen. The three gaps this document used to
list — a seller who could not read why their product was refused, a panel that
could not hand an order to a courier, a running total on no screen — are all
closed, and each of them is a step above.

## When something does not work

```bash
./dev.sh status          # which service is down, and why the backend is unhappy
tail -f .dev-logs/backend.log
tail -f .dev-logs/seller.log
```

A `401` everywhere in a panel means the access token expired — they last 30
minutes, and the panel recovers silently from the refresh cookie, so a `401`
that survives a reload means the cookie is gone too. Sign in again.

A request that never leaves the browser, with a CORS complaint in the console,
means the panel's origin is not named in `MB_CORS_ORIGINS`; all three dev
ports are in the default, on both `localhost` and `127.0.0.1`, because those
are different origins to a browser.

A photograph that shows a grey square rather than a picture is a media path
whose file is missing — the panels resolve relative paths against
`VITE_API_URL` and fall back to the grey square rather than showing the
browser's broken-image glyph. `backend/media/` is where they live.

Every button that refuses shows the *server's* sentence, not ours. If a toast
says something surprising, it is worth reading: "placed holatidan shipped
holatiga o'tib bo'lmaydi" and "Bu ariza allaqachon tekshirilgan" are both the
system telling you something true about the state of a row.
