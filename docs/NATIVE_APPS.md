# The customer apps, against the new API

`android/` and `ios/` are the shopping app. They were written against the
marketplace and the API is now one company with one warehouse, so parts of them
no longer compile and parts of them would fail at runtime.

**Neither has been compiled.** This machine has no JDK, no Android SDK and no
Swift toolchain, which is stated in the brief and is why this file exists
instead of a green build. Everything below was read out of the source and
checked against the running API's OpenAPI document, not against a compiler.

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

**`CheckoutIn`** — `payment_card_id` is gone. **`CheckoutPreviewOut`** — `card`
is gone.

**`ProfileOverviewOut`** — `cards_count` is still answered, at nought, so the
profile screen keeps its tile rather than crashing on a missing key.

### What did *not* change

Auth and the OTP flow, the catalogue's listing and filter shapes, search,
favourites, addresses, delivery slots and pickup points, orders, returns,
notifications, help and legal. The base URL and the `adb reverse` tunnel are
untouched: `http://localhost:8000/api/v1` from a handset, `10.0.2.2` from an
emulator.

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

The tree therefore **does not compile**, and that is deliberate. A DTO left
matching a dead contract compiles and then fails at runtime against the live
API, in front of a customer, with a decoding error nobody can place. Failing at
the call sites is the same information delivered where the work is.

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
