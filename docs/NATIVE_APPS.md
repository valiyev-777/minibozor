# The customer apps, against the new API

`android/` and `ios/` are the shopping app. They were written against the
marketplace and the API is now one company with one warehouse, so parts of them
no longer compile and parts of them would fail at runtime.

**When this was written, neither had been compiled** — no JDK, no Android SDK
and no Swift toolchain, which is why the file exists instead of a green build.
Everything in §1–§3 was read out of the source and checked against the running
API's OpenAPI document, not against a compiler.

That is no longer true of **android/**: the toolchain is on this machine now
and the app builds. Compile before claiming anything about it —

```bash
export JAVA_HOME=/snap/android-studio/241/jbr
export PATH=$JAVA_HOME/bin:$PATH
~/.gradle/wrapper/dists/gradle-8.10.2-bin/*/gradle-8.10.2/bin/gradle \
  --offline :app:compileDebugKotlin
```

**ios/** still has no Swift toolchain here, so it is read, never built.

---

## 1. What moved under them

### Endpoints that no longer exist

| Path | Why |
|---|---|
| `GET /products/{id}/offers` | There are no offers. One company, one price, and the price is on the card. |
| `GET /payment-cards` | No card vault. A shopper pays by card at checkout or in cash at the door. |
| `POST /payment-cards` | ” |
| `POST /payment-cards/{id}/default` | ” |
| `DELETE /payment-cards/{id}` | ” |
| `GET /delivery/slots` | No windows are booked. Delivery is free and the shop says when, not the customer. |

The four `payment-cards` rows are **out of date**: the card vault came back and
`/payment-cards` is served again. Read them as history, not as the contract.

Both apps also still call the review endpoints (`products/{id}/reviews`,
`reviews/tags`, `me/reviews`, …) and `POST /cart/promo`. **Those went before
this rebuild**, with the panels; they are listed here because the apps have
never been updated for them either, and a build will complain about all of it
at once.

### Shapes that changed

**`ProductOut`**

* `seller` — gone. There is nobody else selling it.
* `colours` — **new**: `[{colour, hex, image_url, in_stock}]`, in the order a
  person chooses in.
* `variants` — **flattened**. Was a tree: a colour row with sizes hanging off
  it by `parent_id`. Is now one row per colour per size:

  ```jsonc
  { "id": 12, "colour": "Qora", "size": "42", "label": "Qora · 42",
    "sku": "KRS-01-QORA-42", "barcode": "200000000012",
    "price": 520000, "in_stock": true, "stock_left": 4 }
  ```

  `kind`, `value`, `image_url` and `parent_id` are gone. The photograph belongs
  to the **colour** now, not to the variant, and arrives in `colours`.

**`CartAddIn` / `CartItemOut`** — `color_variant_id` is gone. A line names one
variant, which *is* the colour-and-size pair. Two ids could disagree with each
other; one cannot.

**`CheckoutIn`** — `payment_card_id` is gone, and so is `slot_id`.
**`CheckoutPreviewOut`** — `card` is gone, and so is `slot`.

**`CartTotalsOut`** — `delivery_fee` stays and is always nought, because a
charge may come back in a later version. `free_delivery_threshold` is gone.

**`ProfileOverviewOut`** — `cards_count` is still answered, at nought, so the
profile screen keeps its tile rather than crashing on a missing key.

### What did *not* change

Auth and the OTP flow, the catalogue's listing and filter shapes, search,
favourites, addresses, **pickup points**, orders, returns, notifications, help
and legal. The base URL and the `adb reverse` tunnel are untouched:
`http://localhost:8000/api/v1` from a handset, `10.0.2.2` from an emulator.

Delivery slots used to be on that list and are not any more — see §2a.

---

## 2. What has been changed in the source

Mechanical, and each one verifiable by reading:

**android/**

* `data/remote/MiniBozorApi.kt` — deleted `offers()` and the four
  `payment-cards` calls.
* `data/remote/dto/Dtos.kt` — `VariantDto` flattened, `ColourDto` added,
  `ProductDto.colours` added and `ProductDto.seller` removed; `OfferDto`,
  `SellerDto`, `CardDto` and `CardRequest` deleted; `color_variant_id` removed
  from the cart request and the cart line; `payment_card_id` removed from
  `CheckoutRequest` and `card` from `CheckoutPreviewDto`.
* `data/repository/CatalogRepository.kt`, `data/repository/OrderRepository.kt`
  — the calls to the deleted endpoints removed.

**ios/**

* `Data/DTO/DTOs.swift` — the same changes, one for one.
* `Data/Repositories/CatalogRepository.swift`,
  `Data/Repositories/OrderRepository.swift` — the same removals.

The tree therefore **did not compile**, and that was deliberate. A DTO left
matching a dead contract compiles and then fails at runtime against the live
API, in front of a customer, with a decoding error nobody can place. Failing at
the call sites is the same information delivered where the work is.

Most of that list has since been worked through — and cards came back, so
`CardDto`, `CardRequest` and the checkout's card picker are live again rather
than deleted. As of 2026-09-15 `android/` compiles clean.

---

## 2a. The delivery window is gone — 2026-09-15

Delivery is free, in every app, on every order, and the customer no longer
picks an hour for it. `GET /delivery/slots` is off the API, the checkout no
longer sends `slot_id`, and screen 21 — the day chips and the time windows —
has been deleted on both platforms:
`android/ui/checkout/DeliveryTimeScreen.kt`,
`ios/Features/Checkout/DeliveryTimeView.swift`, with `SlotDto`/`SlotDayDto`
and `SlotDTO`/`SlotDayDTO`, the route, the repository call, and the strings
that only that screen used.

The checkout is one step shorter: **address (or pickup point) → payment →
confirm**. The readiness rules were relaxed with the step — Android's
`CheckoutStep.Time` is gone from the enum and from `missing`, iOS dropped the
`slotId != nil` clause from `ready` — because a step deleted from the screen
and left in the rule is a Tasdiqlash button that never lights up.

`delivery_fee` **stays** in the payload, at nought, so a charge can come back
in a later version without a client change. A zero fee prints **Bepul /
Бесплатно / Free**, and the "add X more for free delivery" nudge went from
both baskets — there is no threshold left to cross.
`free_delivery_threshold` is gone from both DTOs, because the server stopped
answering it in the same pass — checked against `backend/app/schemas.py`, not
assumed. Nothing would break if it came back: the Kotlin decoder is configured
with `ignoreUnknownKeys` and Swift's ignores extra keys by default.

Pickup points are untouched. So is the order's ETA: the server still sends
`eta_label`, and with no window booked it reads "Yetkazish sanasi
aniqlanmoqda" / "Дата доставки уточняется" / "Delivery date being confirmed" —
which is why the orders list, the order detail and the "order placed" screen
still print it.

**android/ was compiled** — `:app:compileDebugKotlin` is green, which also
proves no screen is left asking for a string that was deleted from all three
`strings.xml`. **ios/ was not**, there being no Swift toolchain here; every
deleted symbol was grepped for across both trees instead, and nothing refers
to one.

---

## 3. What is left, file by file

Each of these is a screen decision rather than a rename, which is why none of
them was made blind.

### The variant picker — the real work

`android/ui/product/VariantSheet.kt`, `VariantSheetViewModel.kt`,
`ui/product/ProductViewModel.kt`
`ios/Features/Product/VariantSheet.swift`, `ProductView.swift`

They currently split `variants` into colours and sizes by `kind`, and match a
size to a colour by `parent_id`. The new shape is one flat list, so:

1. the colour strip is `product.colours` — draw `image_url`, fall back to `hex`;
2. the size row is `variants.filter { $0.colour == chosen }`, in the order the
   server sent them;
3. the chosen cell is that one variant. Send `variant_id` alone;
4. the count under the picker is that variant's `stock_left`, which is already
   "what can be bought" — the shelf less what is promised — so no arithmetic;
5. `label` is ready to print. Do not assemble "Qora · 42" in the client; three
   clients would spell it three ways.

### The offers list — delete it

`android/ui/catalog/ListingScreen.kt`, `ListingViewModel.kt`,
`ui/product/component/ProductBlocks.kt` (`OfferRow`)
`ios/Features/Catalog/ListingView.swift`, `Features/Product/ProductBlocks.swift`

A screen that answers "who am I buying from" has no question to answer. Delete
the screen, its route and its row, and the "N takliflar" entry point on the
product page with them.

### Saved cards — delete them

`android/ui/profile/AccountListScreens.kt`, `AccountListViewModels.kt`,
`ui/profile/AddCardViewModel.kt`
`ios/Features/Profile/AccountViews.swift`, `ListViews.swift`,
`Features/Profile/AddCardModel.swift`

Delete the cards list, the add-card form and their routes. The profile row that
leads to them goes too — `cards_count` still answers nought, so the tile can
stay or go, but the destination cannot.

### Checkout

`android/ui/checkout/CheckoutViewModel.kt` (line ~267 sets `paymentCardId`)
`ios/Features/Checkout/CheckoutModel.swift`

Drop the card picker and the `paymentCardId` it fills in. `payment_method`
stays: `card` or `cash`, and that is the whole of the choice now.

### Reviews and the promo code

Every review call and `POST /cart/promo` answer 404. They were removed before
this rebuild. Either delete those screens or leave them behind a flag that is
off — but they cannot be shipped as they are.

---

## 4. How to check this

On a machine with the toolchains:

```bash
cd android && ./gradlew assembleDebug
cd ios && xcodebuild -scheme MiniBozor -destination 'generic/platform=iOS Simulator' build
```

The first build's error list *is* the checklist above. Run the API alongside it
— `./dev.sh` — and walk one purchase end to end: sign in, open a card, pick a
colour and a size, add it, check out with cash, and watch the order appear in
the web app's Buyurtmalar.
