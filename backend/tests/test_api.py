"""End-to-end coverage of the flows the 47 screens depend on."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, col, func, select

from app import audit
from app import offers as of
from app import schemas as s
from app import stock as st
from app.core.config import settings
from app.db import engine
from app.deps import AdminUser
from app.models import (
    AuditLog,
    Brand,
    CartItem,
    Category,
    DeliverySlot,
    Notification,
    Offer,
    OfferVariant,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    PromoCode,
    Review,
    ReviewStatus,
    Seller,
    SellerStatement,
    StockMovement,
    StockMovementKind,
    User,
    UserRole,
    VariantKind,
    utcnow,
)
from app.seed import ADMIN_PHONE

API = "/api/v1"


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"


# --------------------------------------------------------------------------- 01-06


def test_phone_login_creates_a_user(client: TestClient) -> None:
    phone = "+998995554433"
    requested = client.post(f"{API}/auth/otp/request", json={"phone": phone})
    assert requested.status_code == 200
    code = requested.json()["dev_code"]

    verified = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})
    assert verified.status_code == 200
    body = verified.json()
    assert body["is_new_user"] is True
    assert body["access_token"] and body["refresh_token"]


def test_wrong_otp_is_rejected(client: TestClient) -> None:
    phone = "+998991112200"
    client.post(f"{API}/auth/otp/request", json={"phone": phone})
    bad = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": "999999"})
    assert bad.status_code == 400


def test_refresh_token_rotates(client: TestClient) -> None:
    phone = "+998997778899"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code}).json()

    refreshed = client.post(f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert refreshed.status_code == 200

    replayed = client.post(f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert replayed.status_code == 401, "a refresh token must be single use"


def test_protected_route_needs_a_token(client: TestClient) -> None:
    assert client.get(f"{API}/cart").status_code == 401


# --------------------------------------------------------------------------- 07-16


def test_home_is_one_request(client: TestClient) -> None:
    body = client.get(f"{API}/home").json()
    assert body["city"] == "Toshkent"
    assert len(body["banners"]) >= 1
    assert len(body["categories"]) == 10, "the home grid is a 5x2 tile grid"
    keys = [s["key"] for s in body["sections"]]
    assert keys == ["deals", "for-you", "shoes", "electronics"]
    assert all(s["products"] for s in body["sections"])


def test_catalog_tree(client: TestClient) -> None:
    roots = client.get(f"{API}/categories").json()
    clothing = next(c for c in roots if c["slug"] == "kiyim-poyabzal")
    assert clothing["has_children"] is True

    children = client.get(f"{API}/categories", params={"parent": "kiyim-poyabzal"}).json()
    assert {c["slug"] for c in children} >= {"krossovkalar", "futbolka-toplar"}


def test_listing_filters_and_sorts(client: TestClient) -> None:
    cheap_first = client.get(
        f"{API}/products", params={"category": "kiyim-poyabzal", "sort": "price_asc"}
    ).json()
    prices = [p["price"] for p in cheap_first["items"]]
    assert prices == sorted(prices)

    nike = client.get(f"{API}/products", params={"brand": "nike"}).json()
    assert nike["total"] >= 3

    discounted = client.get(f"{API}/products", params={"discounted": True}).json()
    assert all(p["discount_percent"] for p in discounted["items"])


def test_filter_sheet(client: TestClient) -> None:
    body = client.get(f"{API}/products/filters", params={"category": "kiyim-poyabzal"}).json()
    assert body["price_min"] <= body["price_max"]
    assert body["brands"][0]["product_count"] >= body["brands"][-1]["product_count"]
    assert "42" in body["sizes"]
    assert {f["key"] for f in body["flags"]} == {
        "next_day_delivery", "free_delivery", "discounted", "is_original"
    }


def test_search(client: TestClient) -> None:
    landing = client.get(f"{API}/search").json()
    assert "iPhone 15" in landing["popular"]

    hits = client.get(f"{API}/search/suggest", params={"q": "gazelle"}).json()
    assert hits and "Gazelle" in hits[0]["title"]


def test_product_detail_and_reviews(client: TestClient) -> None:
    listing = client.get(f"{API}/products", params={"q": "Gazelle"}).json()
    product_id = listing["items"][0]["id"]

    product = client.get(f"{API}/products/{product_id}").json()
    assert product["images"]
    assert {v["label"] for v in product["variants"]} >= {"42", "Ko'k"}
    assert product["specs"][0]["key"] == "Material"
    assert product["delivery_note"]

    summary = client.get(f"{API}/products/{product_id}/reviews/summary").json()
    assert summary["total"] >= 2
    assert sum(b["count"] for b in summary["distribution"]) == summary["total"]

    reviews = client.get(f"{API}/products/{product_id}/reviews").json()
    assert reviews["items"][0]["author_name"].endswith(".")


# --------------------------------------------------------------------------- 17-24


def test_cart_lifecycle(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)

    product = client.get(f"{API}/products", params={"q": "futbolka"}).json()["items"][0]
    added = client.post(
        f"{API}/cart/items", json=_pick(product["id"], 2), headers=auth
    )
    assert added.status_code == 201
    cart = added.json()
    assert cart["totals"]["items_count"] == 2

    item_id = cart["items"][0]["id"]
    bumped = client.patch(
        f"{API}/cart/items/{item_id}", json={"quantity": 3}, headers=auth
    ).json()
    assert bumped["items"][0]["quantity"] == 3
    assert bumped["totals"]["subtotal"] == product["price"] * 3

    emptied = client.patch(
        f"{API}/cart/items/{item_id}", json={"quantity": 0}, headers=auth
    ).json()
    assert emptied["items"] == []


def test_free_delivery_threshold(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)
    cheap = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]

    cart = client.post(
        f"{API}/cart/items", json=_pick(cheap["id"], 1), headers=auth
    ).json()
    assert cart["totals"]["delivery_fee"] > 0

    expensive = client.get(f"{API}/products", params={"sort": "price_desc"}).json()["items"][0]
    cart = client.post(
        f"{API}/cart/items", json=_pick(expensive["id"], 1), headers=auth
    ).json()
    assert cart["totals"]["subtotal"] >= cart["totals"]["free_delivery_threshold"]
    assert cart["totals"]["delivery_fee"] == 0


def test_promo_code(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_desc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)

    ok = client.post(f"{API}/cart/promo", json={"code": "MINI10"}, headers=auth).json()
    assert ok["totals"]["discount"] == round(ok["totals"]["subtotal"] * 0.1)

    bad = client.post(f"{API}/cart/promo", json={"code": "NOPE"}, headers=auth)
    assert bad.status_code == 400


def test_a_free_slot_does_not_make_delivery_free(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A slot's price is a surcharge, not the whole fee.

    Picking a daytime slot, which costs nothing extra, used to replace the
    standard fee with that nothing — so a small order shipped free and the
    confirm screen showed no delivery line at all.
    """
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)

    cart = client.get(f"{API}/cart", headers=auth).json()
    base = cart["totals"]["delivery_fee"]
    assert base > 0, "a cheap order should not already qualify for free delivery"

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    days = client.get(f"{API}/delivery/slots", headers=auth).json()
    free = next(
        s for day in days for s in day["slots"] if s["price"] == 0 and s["available"]
    )

    totals = client.post(
        f"{API}/checkout/preview",
        json={"address_id": address["id"], "slot_id": free["id"]},
        headers=auth,
    ).json()["totals"]

    assert totals["delivery_fee"] == base
    assert totals["total"] == totals["subtotal"] - totals["discount"] + base


def test_a_paid_slot_adds_to_the_standard_fee(
    client: TestClient, auth: dict[str, str]
) -> None:
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)

    base = client.get(f"{API}/cart", headers=auth).json()["totals"]["delivery_fee"]
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    days = client.get(f"{API}/delivery/slots", headers=auth).json()
    paid = next(s for day in days for s in day["slots"] if s["price"] > 0 and s["available"])

    totals = client.post(
        f"{API}/checkout/preview",
        json={"address_id": address["id"], "slot_id": paid["id"]},
        headers=auth,
    ).json()["totals"]

    assert totals["delivery_fee"] == base + paid["price"]


def test_checkout_places_an_order(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_desc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    slot = client.get(f"{API}/delivery/slots", headers=auth).json()[1]["slots"][0]
    card = client.get(f"{API}/payment-cards", headers=auth).json()[0]

    preview = client.post(
        f"{API}/checkout/preview",
        json={"address_id": address["id"], "slot_id": slot["id"], "payment_card_id": card["id"]},
        headers=auth,
    ).json()
    assert preview["address"]["id"] == address["id"]
    assert preview["totals"]["total"] > 0

    created = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "slot_id": slot["id"], "payment_card_id": card["id"]},
        headers=auth,
    )
    assert created.status_code == 201
    order = created.json()
    assert order["code"].startswith("#A-")
    assert order["status"] == "placed"
    assert len(order["events"]) == 4
    assert order["events"][0]["done"] is True
    assert order["events"][-1]["done"] is False

    assert client.get(f"{API}/cart", headers=auth).json()["items"] == []


def _pick(product_id: int, quantity: int = 1, *, colour_id: int | None = None) -> dict:
    """The body for POST /cart/items, naming a leaf.

    A product with variants will not go into a basket without one: a sale that
    names no colour takes the count off the offer's total and off no colour at
    all, and there is no working out afterwards which one it was. So the tests
    choose the same way the apps do — the leaf with the most of it left, so
    that "add N" has somewhere to come from.
    """
    body: dict = {"product_id": product_id, "quantity": quantity}
    with Session(engine) as session:
        leaves = of.leaf_variants(session, product_id)
        if not leaves:
            return body
        pool = [
            leaf for leaf in leaves if colour_id is None or leaf.parent_id == colour_id
        ] or leaves
        offer = of.winning_offer(session, product_id)
        chosen = max(
            pool,
            key=lambda leaf: st.sellable(session, offer, leaf.id) if offer else 0,
        )
        if chosen.kind is VariantKind.SIZE:
            body["variant_id"] = chosen.id
            if chosen.parent_id is not None:
                body["color_variant_id"] = chosen.parent_id
        else:
            body["color_variant_id"] = chosen.id
    return body


def _variantless_product(client: TestClient) -> dict:
    """A product counted once, for the tests that talk about a whole shelf.

    A product with colours has its shelf counted per colour, so emptying it
    means buying every cell of the grid. These tests are about the product's
    own figure, so they take one that has no cells.
    """
    listing = client.get(f"{API}/products", params={"page_size": 60}).json()["items"]
    with Session(engine) as session:
        return next(
            item
            for item in listing
            if item["in_stock"] and not of.leaf_variants(session, item["id"])
        )


def test_the_basket_cannot_hold_more_than_the_shelf(
    client: TestClient, auth: dict[str, str]
) -> None:
    """The only ceiling was ninety-nine, which is not a ceiling: the basket
    would hold thirty of something there were three of, and the shortfall
    surfaced at checkout or not at all."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    left = client.get(f"{API}/products/{product['id']}").json()["stock_left"]

    added = client.post(
        f"{API}/cart/items",
        json=_pick(product["id"], left + 10),
        headers=auth,
    ).json()
    item = added["items"][0]
    assert item["quantity"] == left
    # And the stepper is handed the same figure to stop its own plus button.
    assert item["stock_left"] == left

    # The stepper itself cannot push past it either.
    patched = client.patch(
        f"{API}/cart/items/{item['id']}",
        json={"quantity": left + 5},
        headers=auth,
    ).json()
    assert patched["items"][0]["quantity"] == left


def test_buying_takes_the_item_off_the_shelf(client: TestClient, auth: dict[str, str]) -> None:
    """The sold count was being raised on every order and the stock beside it
    was not, so a product could be bought any number of times and still claim
    the same 25 remaining."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    before = client.get(f"{API}/products/{product['id']}").json()
    quantity = 3

    client.post(f"{API}/cart/items", json=_pick(product["id"], quantity), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(f"{API}/orders", json={"address_id": address["id"]}, headers=auth)
    assert created.status_code == 201

    after = client.get(f"{API}/products/{product['id']}").json()
    assert after["stock_left"] == before["stock_left"] - quantity
    assert after["sold_count"] == before["sold_count"] + quantity
    # And the card carries it too, so a tile can say when there are few.
    card = next(
        item
        for item in client.get(f"{API}/products", params={"page_size": 60}).json()["items"]
        if item["id"] == product["id"]
    )
    assert card["stock_left"] == after["stock_left"]


def test_the_last_one_sold_goes_out_of_stock(client: TestClient, auth: dict[str, str]) -> None:
    """Nothing was setting in_stock, so a product could sit at zero remaining
    and still offer a basket button on every tile in the catalogue."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    left = client.get(f"{API}/products/{product['id']}").json()["stock_left"]

    client.post(f"{API}/cart/items", json=_pick(product["id"], left), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    placed = client.post(f"{API}/orders", json={"address_id": address["id"]}, headers=auth)
    assert placed.status_code == 201

    sold_out = client.get(f"{API}/products/{product['id']}").json()
    assert sold_out["stock_left"] == 0
    assert sold_out["in_stock"] is False
    # And it cannot be put back in the basket.
    rejected = client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    assert rejected.status_code == 409


def test_a_variant_is_counted_apart_from_the_shelf(client: TestClient) -> None:
    """The page shows one colour in one size at a time and used to answer "how
    many" with the sum of all of them — so a shirt with two left in black
    claimed twenty-five while the picture on screen was of the black one."""
    product = client.get(f"{API}/products/1").json()
    colors = [v for v in product["variants"] if v["kind"] == "color"]
    sizes = [v for v in product["variants"] if v["kind"] == "size"]
    assert len(colors) > 1 and len(sizes) > 1, "seeded with colours and sizes"

    # Two views of one shelf rather than a grid: each kind carries its own
    # counts, and each kind's counts add back up to the product's total.
    for kind in (colors, sizes):
        assert all(v["stock_left"] is not None for v in kind)
        assert sum(v["stock_left"] for v in kind) == product["stock_left"]

    # A variant counted down to nothing says so, rather than only counting zero.
    assert all(v["in_stock"] == (v["stock_left"] > 0) for v in colors + sizes)


def test_buying_a_colour_takes_it_off_that_colour(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Only the product's own count was coming down, so a colour could be
    bought out and go on offering itself at the top of the page."""
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/1").json()
    colors = [v for v in product["variants"] if v["kind"] == "color"]
    chosen, other = colors[0], colors[1]
    quantity = 2

    added = client.post(
        f"{API}/cart/items",
        json=_pick(product["id"], quantity, colour_id=chosen["id"]),
        headers=auth,
    ).json()
    # The stepper's ceiling is the chosen cell of the grid, not the product's
    # whole shelf — and that cell belongs to the colour under test.
    assert added["items"][0]["color_variant_id"] == chosen["id"]
    assert 0 < added["items"][0]["stock_left"] <= chosen["stock_left"]

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    assert client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).status_code == 201

    after = client.get(f"{API}/products/{product['id']}").json()
    after_colors = {v["id"]: v for v in after["variants"] if v["kind"] == "color"}
    assert after_colors[chosen["id"]]["stock_left"] == chosen["stock_left"] - quantity
    # The colour nobody bought is untouched.
    assert after_colors[other["id"]]["stock_left"] == other["stock_left"]
    assert after["stock_left"] == product["stock_left"] - quantity


def test_the_listing_leaves_out_what_cannot_be_bought(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A sold-out product sat in the grid behind its veil, taking a slot in
    every listing from the products that could actually be sold."""
    listed = client.get(f"{API}/products", params={"page_size": 60}).json()["items"]
    assert listed, "the shop is not empty"
    assert all(item["in_stock"] for item in listed)

    # The filter sheet can put them back for anyone who wants to see them.
    with_sold_out = client.get(
        f"{API}/products", params={"page_size": 60, "show_sold_out": True}
    ).json()["items"]
    assert len(with_sold_out) > len(listed)
    assert any(not item["in_stock"] for item in with_sold_out)


# --------------------------------------------------------------------------- 25-29


def test_order_list_and_cancel(client: TestClient, auth: dict[str, str]) -> None:
    active = client.get(f"{API}/orders", params={"active": True}, headers=auth).json()
    assert active["total"] >= 2
    assert all(o["can_track"] for o in active["items"])

    reasons = client.get(f"{API}/orders/reasons/cancel").json()
    assert len(reasons) == 5

    cancellable = next(o for o in active["items"] if o["can_cancel"])
    cancelled = client.post(
        f"{API}/orders/{cancellable['id']}/cancel",
        json={"reason_id": reasons[0]["id"]},
        headers=auth,
    ).json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["status_label"] == "BEKOR QILINDI"

    again = client.post(
        f"{API}/orders/{cancellable['id']}/cancel",
        json={"reason_id": reasons[0]["id"]},
        headers=auth,
    )
    assert again.status_code == 409


def test_return_request(client: TestClient, auth: dict[str, str]) -> None:
    finished = client.get(f"{API}/orders", params={"active": False}, headers=auth).json()
    delivered = next(o for o in finished["items"] if o["status"] == "delivered")
    reasons = client.get(f"{API}/orders/reasons/return").json()

    created = client.post(
        f"{API}/orders/{delivered['id']}/return",
        json={"reason_id": reasons[0]["id"], "comment": "O'lcham kichik keldi"},
        headers=auth,
    )
    assert created.status_code == 201
    assert created.json()["status"] == "submitted"
    assert client.get(f"{API}/returns", headers=auth).json()


# --------------------------------------------------------------------------- 30-40


def test_profile_overview(client: TestClient, auth: dict[str, str]) -> None:
    body = client.get(f"{API}/me/overview", headers=auth).json()
    assert body["user"]["full_name"] == "Aziz Toshmatov"
    assert body["user"]["has_pin"] is True
    assert body["addresses_count"] == 2
    assert body["cards_count"] == 2
    assert body["unread_notifications"] >= 1


def test_favorites(client: TestClient, auth: dict[str, str]) -> None:
    favorites = client.get(f"{API}/favorites", headers=auth).json()
    assert favorites["total"] == 4
    assert all(p["is_favorite"] for p in favorites["items"])

    product_id = favorites["items"][0]["id"]
    client.delete(f"{API}/favorites/{product_id}", headers=auth)
    assert client.get(f"{API}/favorites", headers=auth).json()["total"] == 3

    client.put(f"{API}/favorites/{product_id}", headers=auth)
    assert client.get(f"{API}/favorites", headers=auth).json()["total"] == 4


def test_addresses_keep_a_single_default(client: TestClient, auth: dict[str, str]) -> None:
    created = client.post(
        f"{API}/addresses",
        json={"title": "Dala hovli", "line": "Toshkent viloyati, Zangiota", "is_default": True},
        headers=auth,
    )
    assert created.status_code == 201
    rows = client.get(f"{API}/addresses", headers=auth).json()
    assert sum(1 for a in rows if a["is_default"]) == 1
    client.delete(f"{API}/addresses/{created.json()['id']}", headers=auth)


def test_cards_never_expose_a_pan(client: TestClient, auth: dict[str, str]) -> None:
    cards = client.get(f"{API}/payment-cards", headers=auth).json()
    assert {c["last4"] for c in cards} == {"4417", "3390"}
    assert all("processor_token" not in c for c in cards)

    expired = next(c for c in cards if c["status"] == "expired")
    rejected = client.post(f"{API}/payment-cards/{expired['id']}/default", headers=auth)
    assert rejected.status_code == 409


def test_notifications_are_grouped(client: TestClient, auth: dict[str, str]) -> None:
    groups = client.get(f"{API}/notifications", headers=auth).json()
    assert [g["label"] for g in groups][0] == "Bugun"

    before = client.get(f"{API}/notifications/unread-count", headers=auth).json()["count"]
    assert before > 0
    client.post(f"{API}/notifications/read", headers=auth)
    assert client.get(f"{API}/notifications/unread-count", headers=auth).json()["count"] == 0


def test_settings_and_prefs(client: TestClient, auth: dict[str, str]) -> None:
    updated = client.put(
        f"{API}/me/settings", json={"language": "ru", "night_mode": True}, headers=auth
    ).json()
    assert updated["language"] == "ru" and updated["night_mode"] is True
    client.put(f"{API}/me/settings", json={"language": "uz", "night_mode": False}, headers=auth)

    prefs = client.put(
        f"{API}/me/notification-prefs", json={"promotions": False}, headers=auth
    ).json()
    assert prefs["promotions"] is False and prefs["order_status"] is True


def test_pin_change(client: TestClient, auth: dict[str, str]) -> None:
    wrong = client.post(
        f"{API}/auth/pin", json={"current_pin": "0000", "new_pin": "5678"}, headers=auth
    )
    assert wrong.status_code == 400

    ok = client.post(
        f"{API}/auth/pin", json={"current_pin": "1234", "new_pin": "5678"}, headers=auth
    )
    assert ok.status_code == 200
    verified = client.post(f"{API}/auth/pin/verify", json={"pin": "5678"}, headers=auth)
    assert verified.status_code == 200
    client.post(f"{API}/auth/pin", json={"current_pin": "5678", "new_pin": "1234"}, headers=auth)


# --------------------------------------------------------------------------- 45-47


def test_content_screens(client: TestClient) -> None:
    assert len(client.get(f"{API}/help/faq").json()) == 5
    assert client.get(f"{API}/help/support").json()["phone"] == "1150"
    docs = client.get(f"{API}/legal").json()
    assert len(docs) == 4
    assert client.get(f"{API}/legal/{docs[0]['slug']}").json()["body"]
    assert [x["code"] for x in client.get(f"{API}/languages").json()] == ["uz", "ru", "en"]


def test_logout_revokes_refresh_tokens(client: TestClient) -> None:
    phone = "+998933332211"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code}).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    assert client.post(f"{API}/auth/logout", headers=headers).status_code == 200
    assert client.post(
        f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    ).status_code == 401


# --------------------------------------------------------------------------- languages


def test_categories_follow_accept_language(client: TestClient) -> None:
    def first_name(lang: str | None) -> str:
        headers = {"Accept-Language": lang} if lang else {}
        return client.get(f"{API}/categories", headers=headers).json()[0]["name"]

    assert first_name(None) == "Elektronika"          # no header: the default
    assert first_name("uz") == "Elektronika"
    assert first_name("ru") == "Электроника"
    assert first_name("en") == "Electronics"


def test_unknown_language_falls_back_to_uzbek(client: TestClient) -> None:
    body = client.get(f"{API}/categories", headers={"Accept-Language": "de"}).json()
    assert body[0]["name"] == "Elektronika"


def test_quality_values_are_honoured(client: TestClient) -> None:
    headers = {"Accept-Language": "de;q=1.0, ru;q=0.9, en;q=0.8"}
    body = client.get(f"{API}/categories", headers=headers).json()
    assert body[0]["name"] == "Электроника"


def test_untranslated_rows_keep_their_uzbek(client: TestClient) -> None:
    """A missing translation degrades to Uzbek rather than to a blank."""
    uz = client.get(f"{API}/products/1", headers={"Accept-Language": "uz"}).json()
    ru = client.get(f"{API}/products/1", headers={"Accept-Language": "ru"}).json()

    # Brands have no translations and must survive the lookup untouched.
    assert ru["brand"]["name"] == uz["brand"]["name"]
    # Everything that is translated came back filled in, not blank.
    assert ru["subtitle"] and ru["description"] and ru["title"]
    assert ru["subtitle"] != uz["subtitle"]


def test_error_details_are_translated(client: TestClient) -> None:
    missing = f"{API}/products/999999"
    assert client.get(missing, headers={"Accept-Language": "ru"}).json()["detail"] == (
        "Товар не найден"
    )
    assert client.get(missing, headers={"Accept-Language": "en"}).json()["detail"] == (
        "Product not found"
    )


def test_response_advertises_its_language(client: TestClient) -> None:
    response = client.get(f"{API}/categories", headers={"Accept-Language": "ru"})
    assert response.headers["Content-Language"] == "ru"
    # Without this a cache could hand a Russian body to an English client.
    assert response.headers["Vary"] == "Accept-Language"


# --------------------------------------------------------------------------- roles


def test_a_staff_endpoint_refuses_an_anonymous_caller(client: TestClient) -> None:
    assert client.get(f"{API}/staff/me").status_code == 401


def test_a_customer_cannot_reach_a_staff_endpoint(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A signed-in customer is still not staff — 403, not 401.

    The two must stay apart: the app retries a 401 by refreshing its token,
    and a customer refreshing forever would never learn why.
    """
    assert client.get(f"{API}/staff/me", headers=auth).status_code == 403


def test_an_admin_reaches_a_staff_endpoint(
    client: TestClient, admin: dict[str, str]
) -> None:
    response = client.get(f"{API}/staff/me", headers=admin)
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_every_staff_role_is_staff(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    roles = (UserRole.OPERATOR, UserRole.WAREHOUSE, UserRole.COURIER, UserRole.SELLER)
    for index, role in enumerate(roles):
        headers = staff(role, f"+99890000201{index}")
        response = client.get(f"{API}/staff/me", headers=headers)
        assert response.status_code == 200, role
        assert response.json()["role"] == role.value


def test_require_role_admits_one_role_and_not_the_others(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """``AdminUser`` is stricter than ``StaffUser``, which is the point of
    naming roles at all: an operator works here, but not on this.

    Mounted on a throwaway app rather than a real endpoint — the backoffice
    has no admin-only route to guard yet, and the guard is what is under test.
    """
    probe = FastAPI()

    @probe.get("/admin-only")
    def admin_only(user: AdminUser) -> dict[str, str]:
        return {"role": user.role.value}

    operator = staff(UserRole.OPERATOR, "+998900002020")
    with TestClient(probe) as c:
        assert c.get("/admin-only", headers=admin).json() == {"role": "admin"}
        assert c.get("/admin-only", headers=operator).status_code == 403
        assert c.get("/admin-only").status_code == 401


def test_a_new_account_is_a_customer(client: TestClient) -> None:
    phone = "+998900003030"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})

    with Session(engine) as session:
        user = session.exec(select(User).where(User.phone == phone)).one()
    assert user.role is UserRole.CUSTOMER


def test_the_role_stays_out_of_the_apps_profile(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The apps are shipped and read this shape — the role must not leak into
    it, however the account is flagged on our side."""
    body = client.get(f"{API}/me", headers=admin).json()
    assert "role" not in body
    assert body["phone"] and "has_pin" in body


# --------------------------------------------------------------------------- audit


def test_the_audit_log_records_both_sides_of_a_change() -> None:
    with Session(engine) as session:
        actor = session.exec(select(User).where(User.role == UserRole.ADMIN)).one()
        row = audit.record(
            session,
            actor=actor,
            action="product.price",
            entity="product",
            entity_id=1,
            field="price",
            old=1_090_000,
            new=990_000,
            note="hafta oxiri chegirmasi",
        )
        session.commit()
        session.refresh(row)

        assert row.actor_id == actor.id
        assert row.actor_role is UserRole.ADMIN
        assert (row.old_value, row.new_value) == ("1090000", "990000")
        assert row.created_at is not None


def test_the_audit_log_keeps_an_absent_value_absent() -> None:
    """"There was no value" and "the value was the word None" are different
    claims about the past, and only one of them is true."""
    with Session(engine) as session:
        row = audit.record(
            session,
            action="order.cancel_reason",
            entity="order",
            entity_id=1,
            field="cancel_reason",
            old=None,
            new="Mijoz bekor qildi",
        )
        session.commit()
        session.refresh(row)

    assert row.old_value is None
    assert row.new_value == "Mijoz bekor qildi"
    # No actor at all: a webhook or a scheduled job, not a person.
    assert row.actor_id is None and row.actor_role is None


# --------------------------------------------------------------------------- 401 / 403


def test_a_401_speaks_the_apps_language(client: TestClient) -> None:
    expected = {
        "uz": "Avtorizatsiya talab qilinadi",
        "ru": "Требуется авторизация",
        "en": "You need to sign in",
    }
    for lang, detail in expected.items():
        response = client.get(f"{API}/cart", headers={"Accept-Language": lang})
        assert response.status_code == 401
        assert response.json()["detail"] == detail, lang


def test_a_403_speaks_the_apps_language(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.get(
        f"{API}/staff/me", headers={**auth, "Accept-Language": "en"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "You don't have permission for this"


# --------------------------------------------------------------------------- operator


def _place_an_order(client: TestClient, auth: dict[str, str]) -> dict:
    """An order of this customer's own, in ``placed``, to push around."""
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_asc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert created.status_code == 201, created.text
    return created.json()


def _audit_rows(action: str, entity_id: int) -> list[AuditLog]:
    with Session(engine) as session:
        return session.exec(
            select(AuditLog).where(
                AuditLog.action == action, AuditLog.entity_id == entity_id
            )
        ).all()


# ------------------------------------------------------------------ order status


def test_an_order_walks_its_flow_and_will_not_walk_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    url = f"{API}/staff/orders/{order['id']}/status"

    # Skipping a step is not a step.
    assert client.post(url, json={"status": "delivered"}, headers=operator).status_code == 409

    for target in ("packing", "shipped", "delivered"):
        moved = client.post(url, json={"status": target}, headers=operator)
        assert moved.status_code == 200, (target, moved.text)
        assert moved.json()["status"] == target

    # The one the brief names: a delivered order does not go back to packing.
    back = client.post(url, json={"status": "packing"}, headers=operator)
    assert back.status_code == 409
    assert "delivered" in back.json()["detail"]

    # Delivered has exactly one way on: a return.
    returned = client.post(url, json={"status": "returned"}, headers=operator)
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    # And that really is the end of it.
    assert client.post(url, json={"status": "delivered"}, headers=operator).status_code == 409


def test_the_queue_says_what_an_order_may_become_next(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """The backoffice draws its buttons from this rather than keeping its own
    copy of the rules."""
    order = _place_an_order(client, auth)
    queue = client.get(
        f"{API}/staff/orders", params={"status": "placed", "page_size": 100}, headers=operator
    ).json()
    row = next(r for r in queue["items"] if r["id"] == order["id"])
    assert row["next_statuses"] == ["packing", "cancelled"]
    assert row["customer_phone"] and row["code"] == order["code"]


def test_moving_an_order_writes_the_timeline_the_app_draws(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing", "note": "3-qatordan yig'ildi"},
        headers=operator,
    )

    # Read it back the way the customer's app does.
    events = client.get(f"{API}/orders/{order['id']}", headers=auth).json()["events"]
    by_status = {e["status"]: e for e in events}
    assert by_status["placed"]["done"] is True
    assert by_status["packing"]["done"] is True
    assert by_status["packing"]["happened_at"] is not None
    assert by_status["packing"]["note"] == "3-qatordan yig'ildi"
    assert by_status["shipped"]["done"] is False
    assert by_status["delivered"]["done"] is False


def test_a_cancelled_order_is_not_drawn_as_a_delivered_one(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """Cancelled is not a step on the way to delivery, and the timeline used
    to say it was: the status fell outside the flow, so every step of it came
    back done and the app drew a cancelled order as arrived."""
    order = _place_an_order(client, auth)
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "Mijoz telefonda bekor qildi"},
        headers=operator,
    )

    events = client.get(f"{API}/orders/{order['id']}", headers=auth).json()["events"]
    by_status = {e["status"]: e for e in events}
    assert by_status["placed"]["done"] is True
    assert by_status["delivered"]["done"] is False
    # And the timeline ends where the order actually ended, in words.
    assert by_status["cancelled"]["done"] is True
    assert by_status["cancelled"]["title"] == "Bekor qilindi"


def test_moving_an_order_tells_the_customer_and_the_audit_log(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "packing", "note": "smena-2"},
        headers=operator,
    )

    groups = client.get(f"{API}/notifications", headers=auth).json()
    titles = [n["title"] for g in groups for n in g["items"]]
    assert "Omborda yig'ildi" in titles

    rows = _audit_rows("order.status", order["id"])
    assert len(rows) == 1
    assert (rows[0].old_value, rows[0].new_value) == ("placed", "packing")
    assert rows[0].actor_role is UserRole.OPERATOR
    assert rows[0].note == "smena-2"


def test_only_staff_may_move_an_order(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    url = f"{API}/staff/orders/{order['id']}/status"
    body = {"status": "packing"}

    assert client.post(url, json=body).status_code == 401
    assert client.post(url, json=body, headers=auth).status_code == 403
    assert client.post(url, json=body, headers=operator).status_code == 200


# ------------------------------------------------------------------ returns


def _submit_a_return(client: TestClient, auth: dict[str, str]) -> dict:
    finished = client.get(f"{API}/orders", params={"active": False}, headers=auth).json()
    delivered = next(o for o in finished["items"] if o["status"] == "delivered")
    created = client.post(
        f"{API}/orders/{delivered['id']}/return",
        json={"reason": "O'lcham kichik keldi", "comment": "Qadoq butun"},
        headers=auth,
    )
    assert created.status_code == 201
    return created.json()


def test_a_return_is_approved_and_then_paid_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request = _submit_a_return(client, auth)
    base = f"{API}/staff/returns/{request['id']}"

    # Where the goods went is not a question with a default answer.
    assert client.post(f"{base}/refund", json={}, headers=operator).status_code == 422

    # The money cannot move before the decision does.
    early = client.post(f"{base}/refund", json={"restock": False}, headers=operator)
    assert early.status_code == 409

    approved = client.post(f"{base}/approve", json={"note": "TKT-4417"}, headers=operator)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["next_statuses"] == ["refunded"]

    # Approving twice is not approving harder.
    assert client.post(f"{base}/approve", json={}, headers=operator).status_code == 409
    # Nor is refusing something already accepted.
    assert client.post(
        f"{base}/reject", json={"reason": "Kech"}, headers=operator
    ).status_code == 409

    refunded = client.post(
        f"{base}/refund", json={"note": "Humo", "restock": True}, headers=operator
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"
    assert refunded.json()["next_statuses"] == []

    # Three status moves, all logged against the request.
    moves = _audit_rows("return.status", request["id"])
    assert [(r.old_value, r.new_value) for r in moves] == [
        ("submitted", "approved"),
        ("approved", "refunded"),
    ]

    # How much was paid back is its own row, against the order: it is the
    # figure anyone would later dispute, and a status change does not carry it.
    order_id = approved.json()["order_id"]
    money = _audit_rows("return.refund", order_id)
    assert len(money) == 1
    assert money[0].field == "refund" and int(money[0].new_value) > 0
    assert money[0].actor_role is UserRole.OPERATOR


def test_a_refusal_needs_a_reason_and_the_customer_gets_it(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request = _submit_a_return(client, auth)
    base = f"{API}/staff/returns/{request['id']}"

    assert client.post(f"{base}/reject", json={}, headers=operator).status_code == 400
    blank = client.post(f"{base}/reject", json={"reason": "   "}, headers=operator)
    assert blank.status_code == 400

    rejected = client.post(
        f"{base}/reject",
        json={"reason": "Kiyilgan holda qaytarilgan"},
        headers=operator,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["resolution"] == "Kiyilgan holda qaytarilgan"

    # The answer that never used to come.
    groups = client.get(f"{API}/notifications", headers=auth).json()
    texts = [n["text"] for g in groups for n in g["items"]]
    assert any("Kiyilgan holda qaytarilgan" in t for t in texts)

    rows = _audit_rows("return.status", request["id"])
    assert len(rows) == 1
    assert (rows[0].old_value, rows[0].new_value) == ("submitted", "rejected")


def test_the_customers_own_view_of_a_return_keeps_its_shape(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """The apps read this list and are shipped, so a decision may change what
    it says but not which fields it has."""
    request = _submit_a_return(client, auth)
    before = next(
        r for r in client.get(f"{API}/returns", headers=auth).json() if r["id"] == request["id"]
    )
    client.post(f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator)
    after = next(
        r for r in client.get(f"{API}/returns", headers=auth).json() if r["id"] == request["id"]
    )

    assert set(before) == set(after)
    assert before["status"] == "submitted" and after["status"] == "approved"


def test_only_staff_may_decide_a_return(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request = _submit_a_return(client, auth)
    base = f"{API}/staff/returns/{request['id']}"

    assert client.get(f"{API}/staff/returns").status_code == 401
    assert client.get(f"{API}/staff/returns", headers=auth).status_code == 403
    assert client.post(f"{base}/approve", json={}, headers=auth).status_code == 403
    assert client.get(f"{API}/staff/returns", headers=operator).status_code == 200


# ------------------------------------------------------------------ review moderation


def _review_awaiting_moderation(client: TestClient) -> tuple[int, int, int]:
    """A moderating review on a product nobody has reviewed yet.

    Written straight to the table because the customer endpoint publishes on
    the spot in a dev build, which is the state this queue never sees.
    """
    with Session(engine) as session:
        reviewed = set(session.exec(select(Review.product_id)).all())
        product_id = next(
            p for p in session.exec(select(Product.id).order_by(col(Product.id))).all()
            if p not in reviewed
        )
        author = session.exec(
            select(User).where(User.phone == "+998900007007")
        ).first()
        if author is None:
            author = User(phone="+998900007007", full_name="Nodira Yusupova")
            session.add(author)
            session.commit()
            session.refresh(author)
        review = Review(
            user_id=author.id,
            product_id=product_id,
            rating=5,
            text="Kutganimdan yaxshi chiqdi.",
            status=ReviewStatus.MODERATING,
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        return review.id, product_id, author.id


def test_publishing_a_review_puts_it_on_the_product_page(
    client: TestClient, operator: dict[str, str]
) -> None:
    review_id, product_id, _ = _review_awaiting_moderation(client)

    queue = client.get(f"{API}/staff/reviews", headers=operator).json()
    row = next(r for r in queue if r["id"] == review_id)
    assert row["next_statuses"] == ["published", "rejected"]
    assert row["author_name"] == "Nodira Yusupova"

    # Moderating means invisible: the product page shows no reviews of its own.
    assert client.get(f"{API}/products/{product_id}/reviews").json()["items"] == []

    published = client.post(
        f"{API}/staff/reviews/{review_id}/publish", json={}, headers=operator
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"

    product = client.get(f"{API}/products/{product_id}").json()
    assert product["rating"] == 5.0
    assert product["reviews_count"] == 1
    shown = client.get(f"{API}/products/{product_id}/reviews").json()["items"]
    assert [r["id"] for r in shown] == [review_id]


def test_a_review_cannot_be_published_twice_over(
    client: TestClient, operator: dict[str, str]
) -> None:
    review_id, product_id, _ = _review_awaiting_moderation(client)
    url = f"{API}/staff/reviews/{review_id}/publish"

    assert client.post(url, json={}, headers=operator).status_code == 200
    assert client.post(url, json={}, headers=operator).status_code == 409

    # Taking a published review down is allowed, and stops it counting.
    taken_down = client.post(
        f"{API}/staff/reviews/{review_id}/reject",
        json={"reason": "Boshqa mahsulot haqida"},
        headers=operator,
    )
    assert taken_down.status_code == 200
    assert client.get(f"{API}/products/{product_id}").json()["reviews_count"] == 0


def test_rejecting_a_review_needs_a_reason(
    client: TestClient, operator: dict[str, str]
) -> None:
    review_id, _, author_id = _review_awaiting_moderation(client)
    url = f"{API}/staff/reviews/{review_id}/reject"

    assert client.post(url, json={}, headers=operator).status_code == 400

    rejected = client.post(url, json={"reason": "Haqoratli so'zlar"}, headers=operator)
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    rows = _audit_rows("review.status", review_id)
    assert (rows[0].old_value, rows[0].new_value) == ("moderating", "rejected")
    with Session(engine) as session:
        notes = session.exec(
            select(Notification).where(Notification.user_id == author_id)
        ).all()
    assert any("Haqoratli so'zlar" in n.text for n in notes)


def test_only_staff_may_moderate_a_review(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    review_id, _, _ = _review_awaiting_moderation(client)
    url = f"{API}/staff/reviews/{review_id}/publish"

    assert client.post(url, json={}).status_code == 401
    assert client.post(url, json={}, headers=auth).status_code == 403
    assert client.get(f"{API}/staff/reviews", headers=auth).status_code == 403
    assert client.post(url, json={}, headers=operator).status_code == 200


# ------------------------------------------------------------------ delivery windows


def test_windows_can_be_opened_a_fortnight_at_a_time(
    client: TestClient, operator: dict[str, str]
) -> None:
    """The seed fills a week and nothing refills it, which is how the shop ran
    out of slots. One call has to be able to open a whole stretch."""
    far = date.today() + timedelta(days=40)
    days = [(far + timedelta(days=n)).isoformat() for n in range(3)]
    body = {
        "days": days,
        "windows": [
            {"start_time": "09:00", "end_time": "13:00", "note": "Ertalabki yetkazish"},
            {"start_time": "14:00", "end_time": "18:00", "price": 9000, "capacity": 5},
        ],
    }

    created = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert created.status_code == 201
    assert len(created.json()) == 6

    # Running it again tops up rather than doubling up.
    again = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert again.status_code == 201
    assert again.json() == []

    listed = client.get(
        f"{API}/staff/delivery/slots",
        params={"from_day": days[0], "to_day": days[-1]},
        headers=operator,
    ).json()
    assert len(listed) == 6
    assert {sl["capacity_left"] for sl in listed} == {20, 5}

    # And the customer's own picker now has them.
    offered = client.get(
        f"{API}/delivery/slots", params={"days": 14}, headers=operator
    ).json()
    assert offered, "the customer endpoint still answers"


def test_a_window_that_ends_before_it_starts_is_refused(
    client: TestClient, operator: dict[str, str]
) -> None:
    body = {
        "days": [date.today().isoformat()],
        "windows": [{"start_time": "18:00", "end_time": "14:00"}],
    }
    refused = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert refused.status_code == 422


def test_capacity_can_be_raised_again_and_the_change_is_logged(
    client: TestClient, operator: dict[str, str]
) -> None:
    """Capacity only ever went down — one seat per order placed, and nothing
    to put a seat back or open more."""
    far = (date.today() + timedelta(days=50)).isoformat()
    slot = client.post(
        f"{API}/staff/delivery/slots",
        json={
            "days": [far],
            "windows": [{"start_time": "10:00", "end_time": "12:00", "capacity": 0}],
        },
        headers=operator,
    ).json()[0]
    assert slot["capacity_left"] == 0

    raised = client.patch(
        f"{API}/staff/delivery/slots/{slot['id']}",
        json={"capacity_left": 12, "price": 15000},
        headers=operator,
    )
    assert raised.status_code == 200
    assert raised.json()["capacity_left"] == 12
    assert raised.json()["price"] == 15000
    # An absent field is not "set to nothing".
    assert raised.json()["note"] == slot["note"]

    capacity = _audit_rows("slot.capacity_left", slot["id"])
    assert (capacity[0].old_value, capacity[0].new_value) == ("0", "12")
    price = _audit_rows("slot.price", slot["id"])
    assert (price[0].old_value, price[0].new_value) == ("0", "15000")


def test_only_staff_may_touch_the_delivery_windows(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    body = {
        "days": [(date.today() + timedelta(days=60)).isoformat()],
        "windows": [{"start_time": "09:00", "end_time": "11:00"}],
    }
    assert client.post(f"{API}/staff/delivery/slots", json=body).status_code == 401
    assert client.post(f"{API}/staff/delivery/slots", json=body, headers=auth).status_code == 403
    assert client.get(f"{API}/staff/delivery/slots", headers=auth).status_code == 403
    allowed = client.post(f"{API}/staff/delivery/slots", json=body, headers=operator)
    assert allowed.status_code == 201


def test_a_missing_thing_is_a_404_not_a_conflict(
    client: TestClient, operator: dict[str, str]
) -> None:
    assert client.get(f"{API}/staff/returns/999999", headers=operator).status_code == 404
    assert client.get(f"{API}/staff/orders/999999", headers=operator).status_code == 404
    assert client.patch(
        f"{API}/staff/delivery/slots/999999", json={"capacity_left": 1}, headers=operator
    ).status_code == 404
    assert client.post(
        f"{API}/staff/reviews/999999/publish", json={}, headers=operator
    ).status_code == 404


def test_a_refused_move_says_so_in_the_apps_language(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order = _place_an_order(client, auth)
    refused = client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "delivered"},
        headers={**operator, "Accept-Language": "en"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == "placed cannot become delivered"


# --------------------------------------------------------- what comes back


def _counts(product_id: int, variant_ids: tuple[int, ...] = (), slot_id: int | None = None) -> dict:
    """Every count an order moves, read straight from the tables."""
    with Session(engine) as session:
        product = session.get(Product, product_id)
        slot = session.get(DeliverySlot, slot_id) if slot_id else None
        return {
            "stock_left": product.stock_left,
            "in_stock": product.in_stock,
            "sold_count": product.sold_count,
            "variants": {
                v: session.get(ProductVariant, v).stock_left for v in variant_ids
            },
            "capacity_left": slot.capacity_left if slot else None,
        }


PRODUCT_WITH_VARIANTS = 1
SHELF = 50          # what the helper below stocks the shelf with
VARIANT_SHELF = 20  # and each of the two variants it picks


def _order_with_a_variant_and_a_slot(
    client: TestClient, auth: dict[str, str], quantity: int = 2
) -> tuple[dict, dict, tuple[int, ...], int]:
    """An order that moves all four counts, and what they were beforehand.

    The shelf is set to a known figure first. These tests each spend some of
    it and only some of them put it back, which is the behaviour under test —
    so without a baseline they would run the product out and start failing in
    whatever order they happen to run in.
    """
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/{PRODUCT_WITH_VARIANTS}").json()
    colour = next(v for v in product["variants"] if v["kind"] == "color")
    size = next(
        v
        for v in product["variants"]
        if v["kind"] == "size" and v["parent_id"] == colour["id"]
    )
    days = client.get(f"{API}/delivery/slots", params={"days": 5}, headers=auth).json()
    slot = next(sl for day in days for sl in day["slots"] if sl["available"])
    variant_ids = (colour["id"], size["id"])

    # Stocked through the ledger, because that is the only way a count moves
    # now: writing the figure onto the row would leave the running total
    # disagreeing with the sum of its movements, which is the one thing the
    # ledger must never do. Only the leaves are set — a colour is the sum of
    # its sizes and follows on its own.
    with Session(engine) as session:
        offer = of.winning_offer(session, product["id"]) or of.offers_for(
            session, product["id"], active_only=False
        )[0]
        offer.active = True
        session.add(offer)
        for leaf in of.leaf_variants(session, product["id"]):
            current = of.variant_stock(session, offer.id, leaf.id) or 0
            st.move(
                session,
                offer=offer,
                kind=StockMovementKind.COUNT_ADJUSTMENT,
                quantity=VARIANT_SHELF - current,
                variant_id=leaf.id,
                reason="sinov javoni",
            )
        session.commit()
        of.refresh(session, product["id"])
        session.commit()

    before = _counts(product["id"], variant_ids, slot["id"])
    client.post(
        f"{API}/cart/items",
        json={
            "product_id": product["id"],
            "color_variant_id": colour["id"],
            "variant_id": size["id"],
            "quantity": quantity,
        },
        headers=auth,
    )
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "slot_id": slot["id"]},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    return created.json(), before, variant_ids, slot["id"]


def test_placing_an_order_moves_all_four_counts(
    client: TestClient, auth: dict[str, str]
) -> None:
    """The baseline the restoration is measured against — and proof the order
    line now remembers which variants it took, which is what makes any of it
    possible to undo."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    after = _counts(order["items"][0]["product_id"], variant_ids, slot_id)

    assert after["stock_left"] == before["stock_left"] - 2
    assert after["sold_count"] == before["sold_count"] + 2
    assert after["capacity_left"] == before["capacity_left"] - 1
    for v in variant_ids:
        assert after["variants"][v] == before["variants"][v] - 2

    with Session(engine) as session:
        line = session.exec(
            select(OrderItem).where(OrderItem.order_id == order["id"])
        ).one()
        assert (line.color_variant_id, line.variant_id) == variant_ids
        assert session.get(Order, order["id"]).slot_id == slot_id


def test_cancelling_puts_all_four_counts_back(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Nothing about a cancelled order happened, so nothing about it should
    still be counted: the goods never left, they were never sold, and the
    window is free for somebody else."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    reasons = client.get(f"{API}/orders/reasons/cancel").json()

    cancelled = client.post(
        f"{API}/orders/{order['id']}/cancel",
        json={"reason_id": reasons[0]["id"]},
        headers=auth,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    after = _counts(order["items"][0]["product_id"], variant_ids, slot_id)
    assert after["stock_left"] == before["stock_left"]
    assert after["sold_count"] == before["sold_count"]
    assert after["capacity_left"] == before["capacity_left"]
    assert after["variants"] == before["variants"]


def test_the_operator_cancels_exactly_as_the_customer_does(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """Two cancel paths, one restoration between them. The operator's put
    nothing back at all."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)

    cancelled = client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "Mijoz telefonda voz kechdi"},
        headers=operator,
    )
    assert cancelled.status_code == 200

    after = _counts(order["items"][0]["product_id"], variant_ids, slot_id)
    assert after["stock_left"] == before["stock_left"]
    assert after["sold_count"] == before["sold_count"]
    assert after["capacity_left"] == before["capacity_left"]
    assert after["variants"] == before["variants"]


def test_a_sold_out_product_is_on_sale_again_once_it_is_cancelled(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A shelf emptied by an order that never happened is not empty."""
    client.delete(f"{API}/cart", headers=auth)
    product = _variantless_product(client)
    left = client.get(f"{API}/products/{product['id']}").json()["stock_left"]

    client.post(f"{API}/cart/items", json=_pick(product["id"], left), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()

    emptied = client.get(f"{API}/products/{product['id']}").json()
    assert emptied["stock_left"] == 0
    assert emptied["in_stock"] is False

    client.post(f"{API}/orders/{order['id']}/cancel", json={}, headers=auth)

    back = client.get(f"{API}/products/{product['id']}").json()
    assert back["stock_left"] == left
    assert back["in_stock"] is True


def test_cancelling_says_who_moved_which_count(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    product_id = order["items"][0]["product_id"]
    client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "TKT-9001"},
        headers=operator,
    )

    with Session(engine) as session:
        rows = session.exec(
            select(AuditLog).where(
                AuditLog.action == "order.cancel", AuditLog.note == "TKT-9001"
            )
        ).all()
    moved = {(r.entity, r.field) for r in rows}
    assert ("product", "stock_left") in moved
    assert ("product", "sold_count") in moved
    assert ("product_variant", "stock_left") in moved
    assert ("delivery_slot", "capacity_left") in moved
    assert all(r.actor_role is UserRole.OPERATOR for r in rows)

    shelf = next(
        r for r in rows if r.entity == "product" and r.field == "stock_left"
    )
    assert shelf.entity_id == product_id
    assert int(shelf.new_value) - int(shelf.old_value) == 2


# --------------------------------------------------------- refund and restock


def _refundable_return(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> tuple[dict, dict, tuple[int, ...], int]:
    """An approved return on a delivered order, ready to be paid back."""
    order, before, variant_ids, slot_id = _order_with_a_variant_and_a_slot(client, auth)
    url = f"{API}/staff/orders/{order['id']}/status"
    for target in ("packing", "shipped", "delivered"):
        assert client.post(url, json={"status": target}, headers=operator).status_code == 200

    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Rangi rasmdagidek emas"},
        headers=auth,
    ).json()
    approved = client.post(
        f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator
    )
    assert approved.status_code == 200
    return request, before, variant_ids, slot_id


def test_a_refund_that_restocks_puts_the_goods_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    request, before, variant_ids, slot_id = _refundable_return(client, auth, operator)
    product_id = client.get(
        f"{API}/staff/returns/{request['id']}", headers=operator
    ).json()["order_id"]

    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True, "note": "Ko'zdan kechirildi, butun"},
        headers=operator,
    )
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"

    after = _counts(PRODUCT_WITH_VARIANTS, variant_ids, slot_id)
    assert after["stock_left"] == before["stock_left"]
    assert after["variants"] == before["variants"]
    # It was sold, and delivered, and that happened. A refund returns money,
    # not the fact of the sale — and the window was used, not freed.
    assert after["sold_count"] == before["sold_count"] + 2
    assert after["capacity_left"] == before["capacity_left"] - 1
    assert product_id


def test_a_refund_without_restocking_leaves_the_shelf_alone(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """Goods that came back damaged belong on nobody's count."""
    request, before, variant_ids, slot_id = _refundable_return(client, auth, operator)
    sold_out = _counts(PRODUCT_WITH_VARIANTS, variant_ids, slot_id)

    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": False, "reason": "Yaroqsiz holatda qaytdi"},
        headers=operator,
    )
    assert refunded.status_code == 200

    after = _counts(PRODUCT_WITH_VARIANTS, variant_ids, slot_id)
    assert after["stock_left"] == sold_out["stock_left"] == before["stock_left"] - 2
    assert after["variants"] == sold_out["variants"]


def test_both_answers_about_the_goods_are_logged(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """A write-off nobody recorded is indistinguishable from stock going
    missing, so "we kept it off the shelf" is a logged decision too."""
    kept, _, _, _ = _refundable_return(client, auth, operator)
    client.post(
        f"{API}/staff/returns/{kept['id']}/refund",
        json={"restock": False, "reason": "Yaroqsiz"},
        headers=operator,
    )
    shelved, _, _, _ = _refundable_return(client, auth, operator)
    client.post(
        f"{API}/staff/returns/{shelved['id']}/refund",
        json={"restock": True},
        headers=operator,
    )

    decisions = {
        r.entity_id: r.new_value
        for r in _audit_rows("return.restock", kept["id"])
        + _audit_rows("return.restock", shelved["id"])
        if r.entity == "return_request"
    }
    assert decisions == {kept["id"]: "false", shelved["id"]: "true"}

    # And the counts that actually moved are logged against the goods.
    assert not [
        r for r in _audit_rows("return.restock", kept["id"]) if r.entity == "product"
    ]
    with Session(engine) as session:
        shelf = session.exec(
            select(AuditLog).where(
                AuditLog.action == "return.restock",
                AuditLog.entity == "product",
                AuditLog.field == "stock_left",
            )
        ).all()
    assert shelf and all(
        int(r.new_value) > int(r.old_value) for r in shelf
    )


def test_the_customer_can_read_how_much_came_back(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """The figure was only ever in the audit log, which the customer cannot
    read — so the request could not answer the one question they have."""
    request, _, _, _ = _refundable_return(client, auth, operator)

    before = next(
        r for r in client.get(f"{API}/returns", headers=auth).json()
        if r["id"] == request["id"]
    )
    assert before["refund_amount"] == 0

    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True},
        headers=operator,
    ).json()

    after = next(
        r for r in client.get(f"{API}/returns", headers=auth).json()
        if r["id"] == request["id"]
    )
    assert after["refund_amount"] == refunded["refund_amount"] > 0
    # The whole order, because the request did not name a line of it.
    with Session(engine) as session:
        order = session.get(Order, refunded["order_id"])
    assert after["refund_amount"] == order.total
    # Added, not changed: every field the apps already read is still there.
    assert set(before) == set(after)
    assert {"id", "order_code", "reason", "comment", "status", "created_at"} <= set(after)


def test_only_the_named_line_comes_back_on_a_partial_return(
    client: TestClient, auth: dict[str, str], operator: dict[str, str]
) -> None:
    """A request that names one item is about that item, and neither the money
    nor the shelf should move for the rest of the order."""
    client.delete(f"{API}/cart", headers=auth)
    cheap, dear = client.get(
        f"{API}/products", params={"sort": "price_asc"}
    ).json()["items"][:2]
    for product in (cheap, dear):
        client.post(
            f"{API}/cart/items", json=_pick(product["id"]), headers=auth
        )
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    assert len(order["items"]) == 2

    url = f"{API}/staff/orders/{order['id']}/status"
    for target in ("packing", "shipped", "delivered"):
        client.post(url, json={"status": target}, headers=operator)

    line = next(i for i in order["items"] if i["product_id"] == cheap["id"])
    other = next(i for i in order["items"] if i["product_id"] == dear["id"])
    before = _counts(other["product_id"])

    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"order_item_id": line["id"], "reason": "Kerak emas"},
        headers=auth,
    ).json()
    client.post(
        f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator
    )
    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True},
        headers=operator,
    ).json()

    assert refunded["refund_amount"] == line["line_total"] < order["total"]
    assert _counts(other["product_id"])["stock_left"] == before["stock_left"]


# --------------------------------------------------------- offers and sellers


def _seller(name: str, *, commission: int = 5) -> int:
    with Session(engine) as session:
        row = session.exec(select(Seller).where(Seller.name == name)).first()
        if row is None:
            row = Seller(name=name, phone="+998781234567", commission_percent=commission)
            session.add(row)
            session.commit()
            session.refresh(row)
        return row.id


def _offer(
    product_id: int,
    *,
    seller: str,
    price: int,
    stock: int,
    old_price: int | None = None,
    active: bool = True,
) -> int:
    """Put one seller's offer on a product, and let the cache follow.

    The shelf is moved through the ledger rather than written onto the row: a
    running total that disagrees with the sum of its movements is the one
    thing the warehouse must never contain, and the suite checks that
    globally.
    """
    seller_id = _seller(seller)
    with Session(engine) as session:
        row = session.exec(
            select(Offer).where(
                Offer.product_id == product_id, Offer.seller_id == seller_id
            )
        ).first()
        if row is None:
            row = Offer(seller_id=seller_id, product_id=product_id, price=price)
        row.price, row.old_price, row.active = price, old_price, active
        session.add(row)
        session.commit()
        session.refresh(row)
        _adjust_to(session, row, stock)
        session.commit()
        of.refresh(session, product_id)
        session.commit()
        return row.id


def _adjust_to(session: Session, offer: Offer, target: int) -> None:
    """Bring an offer's whole shelf to `target` by recording the difference.

    All of it on the first leaf and nothing on the rest, so the offer's total
    is the figure asked for rather than the figure times the number of sizes.
    Which size is arbitrary and does not matter to the callers; what matters
    is that the total is right and the ledger explains it.
    """
    leaves = of.leaf_variants(session, offer.product_id)
    if leaves:
        for index, leaf in enumerate(leaves):
            current = of.variant_stock(session, offer.id, leaf.id) or 0
            st.move(
                session,
                offer=offer,
                kind=StockMovementKind.COUNT_ADJUSTMENT,
                quantity=(target if index == 0 else 0) - current,
                variant_id=leaf.id,
                reason="sinov javoni",
            )
    else:
        st.move(
            session,
            offer=offer,
            kind=StockMovementKind.COUNT_ADJUSTMENT,
            quantity=target - offer.stock_left,
            reason="sinov javoni",
        )


def _undercuts(house_price: int) -> tuple[int, int]:
    """Two prices below the house's, well apart, and never below a so'm.

    Fixed offsets do not work across this catalogue: it runs from a few
    thousand so'm to a few million, and "the house price less six hundred
    thousand" is a negative number on half of it.
    """
    cheap = max(1_000, house_price // 3)
    mid = max(cheap * 2, house_price // 2)
    return cheap, mid


def _untouched_product(client: TestClient) -> dict:
    """A product no other test has put a second seller on.

    One offer means one price, which is the state the whole catalogue is in
    after the migration — and taking a fresh one per test keeps each of them
    reasoning about a shelf nothing else has been spending.

    The seeded catalogue is thirty-one cards and this suite spends them, so
    when they run out a new one is made through the front door: written,
    published, offered by the house and stocked. That is a slower path than
    picking one, which is why it is the fallback rather than the rule.
    """
    listing = client.get(f"{API}/products", params={"page_size": 60}).json()
    with Session(engine) as session:
        single = {
            product_id
            for product_id in session.exec(select(Offer.product_id)).all()
            if len(of.offers_for(session, product_id, active_only=False)) == 1
        }
    found = next(
        (p for p in listing["items"] if p["in_stock"] and p["id"] in single), None
    )
    return found if found is not None else _mint_a_product(client)


def _mint_a_product(client: TestClient) -> dict:
    """A fresh card in the shop, offered by the house and stocked.

    Everything through the endpoints this stage added, except the shelf, which
    goes through the ledger because that is the only way a count moves.
    """
    admin = _sign_in_as(client, ADMIN_PHONE)
    slug = client.get(f"{API}/categories").json()[0]["slug"]
    with Session(engine) as session:
        minted = len(session.exec(select(Product)).all()) + 1
        house = session.exec(select(Seller).where(Seller.name == "Mini Bozor")).one()
        house_id = house.id

    card = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": f"MB-MINT-{minted}",
            "title": f"Sinov tovari {minted}",
            "category_slug": slug,
            "price": 400_000,
        },
        headers=admin,
    )
    assert card.status_code == 201, card.text
    product_id = card.json()["id"]
    client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "published"},
        headers=admin,
    )
    offer = client.post(
        f"{API}/staff/offers",
        json={"product_id": product_id, "price": 400_000, "seller_id": house_id},
        headers=admin,
    )
    assert offer.status_code == 201, offer.text

    with Session(engine) as session:
        _adjust_to(session, session.get(Offer, offer.json()["id"]), 25)
        session.commit()
        of.refresh(session, product_id)
        session.commit()
    return client.get(f"{API}/products/{product_id}").json()


def _sign_in_as(client: TestClient, phone: str) -> dict[str, str]:
    """Auth headers for a phone, for the helpers that cannot take a fixture."""
    requested = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    tokens = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": requested["dev_code"]}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_the_cheapest_offer_wins_the_card(client: TestClient) -> None:
    product = _untouched_product(client)
    cheap, mid = _undercuts(product["price"])

    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=4)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=9)

    card = client.get(f"{API}/products/{product['id']}").json()
    assert card["price"] == cheap
    assert card["stock_left"] == 4
    assert card["seller"] == "Toshkent Elektronika"
    # Every field the apps read is still the field it was; only the value moved.
    assert set(card) >= {"price", "old_price", "discount_percent", "stock_left", "in_stock"}


def test_an_offer_with_nothing_left_does_not_compete(client: TestClient) -> None:
    """A price nobody can pay is not a price. It used to be the whole shop's
    only price, so the question could not come up."""
    product = _untouched_product(client)
    cheap, mid = _undercuts(product["price"])

    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=0)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=6)

    card = client.get(f"{API}/products/{product['id']}").json()
    assert card["price"] == mid
    assert card["seller"] == "Chilonzor Savdo"
    assert card["in_stock"] is True

    # And with none of them holding anything, the card keeps a price to print
    # and says plainly that it cannot be bought.
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=0)
    with Session(engine) as session:
        for row in of.offers_for(session, product["id"]):
            _adjust_to(session, row, 0)
        session.commit()
        of.refresh(session, product["id"])
        session.commit()

    empty = client.get(f"{API}/products/{product['id']}").json()
    assert empty["in_stock"] is False
    assert empty["stock_left"] == 0
    assert empty["price"] == cheap, "the cheapest offer still names the price"


def test_selling_a_winner_out_hands_the_card_to_the_next_seller(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Bought through the front door, not set in the table: the point is that
    an order draws down the seller's shelf and the card follows."""
    product = _untouched_product(client)
    low, mid = _undercuts(product["price"])
    cheap = _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=2)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=8)

    client.delete(f"{API}/cart", headers=auth)
    response = client.post(f"{API}/cart/items", json=_pick(product["id"], 2), headers=auth)
    assert response.status_code == 201, response.text
    added = response.json()
    # The basket is capped by the chosen seller's shelf, not the catalogue's.
    assert added["items"][0]["unit_price"] == low
    assert added["items"][0]["stock_left"] == 2

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert order.status_code == 201

    with Session(engine) as session:
        assert session.get(Offer, cheap).stock_left == 0

    moved_on = client.get(f"{API}/products/{product['id']}").json()
    assert moved_on["price"] == mid
    assert moved_on["seller"] == "Chilonzor Savdo"
    assert moved_on["stock_left"] == 8


def test_the_order_line_says_who_sold_it(
    client: TestClient, auth: dict[str, str]
) -> None:
    """Without this there is no answering "who is owed this money", which is
    the difference between a shop and a marketplace."""
    product = _untouched_product(client)
    cheap, _ = _undercuts(product["price"])
    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=5)
    seller_id = _seller("Toshkent Elektronika")

    client.delete(f"{API}/cart", headers=auth)
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()

    with Session(engine) as session:
        line = session.exec(
            select(OrderItem).where(OrderItem.order_id == order["id"])
        ).one()
        assert line.seller_id == seller_id
        assert line.offer_id is not None
        seller = session.get(Seller, line.seller_id)
    assert seller.commission_percent == 5, "five per cent of every item sold"


def test_cancelling_gives_the_stock_back_to_the_seller_it_came_from(
    client: TestClient, auth: dict[str, str]
) -> None:
    product = _untouched_product(client)
    low, _ = _undercuts(product["price"])
    cheap = _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=5)
    dear_id = _offer(product["id"], seller="Chilonzor Savdo", price=product["price"], stock=7)

    client.delete(f"{API}/cart", headers=auth)
    added = client.post(f"{API}/cart/items", json=_pick(product["id"], 3), headers=auth)
    assert added.status_code == 201, added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    with Session(engine) as session:
        assert session.get(Offer, cheap).stock_left == 2
        assert session.get(Offer, dear_id).stock_left == 7

    client.post(f"{API}/orders/{order['id']}/cancel", json={}, headers=auth)

    with Session(engine) as session:
        assert session.get(Offer, cheap).stock_left == 5, "back on the shelf it left"
        assert session.get(Offer, dear_id).stock_left == 7, "and not on anybody else's"
    assert client.get(f"{API}/products/{product['id']}").json()["stock_left"] == 5


def test_the_cache_follows_the_offer_that_changed(client: TestClient) -> None:
    """The product's price is a copy, and a copy is only as good as what keeps
    it in step. One function writes it, and everything that can change the
    answer calls that function."""
    product = _untouched_product(client)
    # Under the house's price, whatever the house's price happens to be: this
    # catalogue runs from a few thousand so'm to a few million.
    was = product["price"]
    low, mid = _undercuts(was)
    _offer(product["id"], seller="Toshkent Elektronika", price=mid, stock=3, old_price=was)

    card = client.get(f"{API}/products/{product['id']}").json()
    assert (card["price"], card["old_price"]) == (mid, was)
    assert card["discount_percent"] == round((was - mid) / was * 100)

    # A seller cutting their price.
    _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=3, old_price=was)
    cut = client.get(f"{API}/products/{product['id']}").json()
    assert cut["price"] == low
    assert cut["discount_percent"] == round((was - low) / was * 100)

    # And withdrawing it altogether, which hands the card back.
    _offer(product["id"], seller="Toshkent Elektronika", price=low, stock=3, active=False)
    withdrawn = client.get(f"{API}/products/{product['id']}").json()
    assert withdrawn["price"] != low
    assert withdrawn["seller"] == "Mini Bozor"


def test_price_sorting_sorts_by_the_winning_price(client: TestClient) -> None:
    """The listing sorts in SQL over a paged query, which is the whole reason
    the winning price is cached on the product at all."""
    product = _untouched_product(client)
    # One so'm: nothing in the catalogue can undercut it, so the assertion
    # does not depend on what the rest of the shop happens to cost.
    _offer(product["id"], seller="Toshkent Elektronika", price=1, stock=3)

    cheapest = client.get(
        f"{API}/products", params={"sort": "price_asc", "page_size": 5}
    ).json()["items"]
    assert cheapest[0]["id"] == product["id"]
    assert cheapest[0]["price"] == 1
    assert [i["price"] for i in cheapest] == sorted(i["price"] for i in cheapest)

    # And the filter reads the same figure.
    under = client.get(f"{API}/products", params={"max_price": 1}).json()
    assert [i["id"] for i in under["items"]] == [product["id"]]
    assert under["total"] == 1

    dearest = client.get(
        f"{API}/products", params={"sort": "price_desc", "page_size": 5}
    ).json()["items"]
    assert product["id"] not in [i["id"] for i in dearest]


def test_the_offers_list_shows_every_seller_cheapest_first(client: TestClient) -> None:
    product = _untouched_product(client)
    cheap, mid = _undercuts(product["price"])
    _offer(product["id"], seller="Toshkent Elektronika", price=cheap, stock=0)
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=4)

    listed = client.get(f"{API}/products/{product['id']}/offers").json()
    assert [o["price"] for o in listed] == sorted(o["price"] for o in listed)
    assert [o["seller"]["name"] for o in listed[:2]] == [
        "Toshkent Elektronika",
        "Chilonzor Savdo",
    ]
    # The cheapest is shown, and shown to be sold out — which is why the card
    # is quoting the second one.
    assert listed[0]["in_stock"] is False and listed[0]["is_winner"] is False
    assert listed[1]["is_winner"] is True
    assert sum(1 for o in listed if o["is_winner"]) == 1

    # A withdrawn offer is not on sale, so it is not on the list.
    _offer(product["id"], seller="Chilonzor Savdo", price=mid, stock=4, active=False)
    fewer = client.get(f"{API}/products/{product['id']}/offers").json()
    assert "Chilonzor Savdo" not in [o["seller"]["name"] for o in fewer]

    assert client.get(f"{API}/products/999999/offers").status_code == 404


def test_every_product_still_has_at_least_one_offer(client: TestClient) -> None:
    """The invariant the migration left behind: the catalogue read as a
    single-seller shop all along, so nothing should have been left without a
    price to show."""
    with Session(engine) as session:
        products = session.exec(select(Product.id)).all()
        offered = {o.product_id for o in session.exec(select(Offer)).all()}
    assert set(products) <= offered

    listing = client.get(f"{API}/products", params={"page_size": 60}).json()
    assert all(p["price"] > 0 for p in listing["items"])


# --------------------------------------------------------- selling and stocking


def _linked_seller(
    staff: Callable[[UserRole, str], dict[str, str]],
    name: str,
    phone: str,
    *,
    commission: int = 5,
) -> tuple[int, dict[str, str]]:
    """A seller, and the account that signs in as them.

    Two rows, not one: staff come through the same OTP flow as customers and
    the role is the only difference, so a seller is a `sellers` row pointed at
    a `users` row holding UserRole.SELLER.
    """
    headers = staff(UserRole.SELLER, phone)
    with Session(engine) as session:
        user = session.exec(select(User).where(User.phone == phone)).one()
        row = session.exec(select(Seller).where(Seller.name == name)).first()
        if row is None:
            row = Seller(name=name, phone=phone, commission_percent=commission)
        row.user_id = user.id
        row.commission_percent = commission
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id, headers


def _offer_body(product_id: int, price: int, **extra) -> dict:
    """Post an offer with the product's variants filled in.

    Naming every leaf is required, and most of these tests are about something
    else, so the list is assembled here rather than written out eight times.
    """
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product_id)]
    body = {"product_id": product_id, "price": price, "variant_ids": leaves, **extra}
    return body


def _stock_body(product_id: int, per_leaf: int) -> dict:
    """A warehouse intake for a product whether or not it has variants.

    Only leaves are given: a product with colours and sizes is stocked cell by
    cell, and one with neither is stocked once on the offer itself.
    """
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product_id)]
    if not leaves:
        return {"stock_left": per_leaf, "reason": "sinov uchun sanoq"}
    return {
        "reason": "sinov uchun sanoq",
        "variants": [{"variant_id": v, "stock_left": per_leaf} for v in leaves],
    }


def _untouched_with_variants(client: TestClient) -> dict:
    """A product that has colours and sizes, and only one offer so far."""
    listing = client.get(f"{API}/products", params={"page_size": 60}).json()
    with Session(engine) as session:
        single = {
            product_id
            for product_id in session.exec(select(Offer.product_id)).all()
            if len(of.offers_for(session, product_id, active_only=False)) == 1
        }
        return next(
            p
            for p in listing["items"]
            if p["in_stock"]
            and p["id"] in single
            and of.leaf_variants(session, p["id"])
        )


def test_a_seller_sets_their_own_price_and_the_card_follows(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    seller_id, mine = _linked_seller(staff, "Yunusobod Savdo", "+998900010001")
    cheap, _ = _undercuts(product["price"])

    created = client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap),
        headers=mine,
    )
    assert created.status_code == 201, created.text
    offer = created.json()
    assert offer["seller"]["id"] == seller_id
    # Nothing on the shelf until the warehouse books something in, so the card
    # is not handed over on the strength of a price alone.
    assert offer["stock_left"] == 0
    assert offer["is_winner"] is False
    assert client.get(f"{API}/products/{product['id']}").json()["price"] != cheap

    with Session(engine) as session:
        _adjust_to(session, session.get(Offer, offer["id"]), 5)
        session.commit()
        of.refresh(session, product["id"])
        session.commit()

    won = client.get(f"{API}/products/{product['id']}").json()
    assert (won["price"], won["seller"], won["stock_left"]) == (cheap, "Yunusobod Savdo", 5)

    # And cutting it again moves the card again — one cache, one writer.
    dropped = client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"price": cheap - 1}, headers=mine
    )
    assert dropped.status_code == 200
    assert client.get(f"{API}/products/{product['id']}").json()["price"] == cheap - 1


def test_a_seller_cannot_touch_somebody_elses_offer(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Sergeli Savdo", "+998900010002")
    _, theirs = _linked_seller(staff, "Olmazor Savdo", "+998900010003")
    cheap, mid = _undercuts(product["price"])

    ours = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=mine
    ).json()

    # A real offer, and a refusal — not a pretence that it is missing.
    refused = client.patch(
        f"{API}/staff/offers/{ours['id']}", json={"price": cheap}, headers=theirs
    )
    assert refused.status_code == 403
    with Session(engine) as session:
        assert session.get(Offer, ours["id"]).price == mid

    # Nor may a seller open an offer in somebody else's name.
    assert client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap, seller_id=1),
        headers=theirs,
    ).status_code == 403

    # Their own is fine, and the two coexist.
    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=theirs
    ).status_code == 201


def test_stock_is_the_warehouses_and_not_the_sellers(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """The line that matters under this model: the goods are in our warehouse,
    so a seller who could write a stock figure could promise goods nobody has
    received."""
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Chirchiq Savdo", "+998900010004")
    warehouse = staff(UserRole.WAREHOUSE, "+998900010005")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    ).json()
    url = f"{API}/staff/offers/{offer['id']}/stock"

    intake = _stock_body(product["id"], 9)
    assert client.put(url, json=intake).status_code == 401
    assert client.put(url, json=intake, headers=mine).status_code == 403

    stocked = client.put(url, json=intake, headers=warehouse)
    assert stocked.status_code == 200
    assert stocked.json()["stock_left"] > 0

    # The price side is closed to the warehouse in the same way.
    assert client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"price": 1}, headers=warehouse
    ).status_code == 403
    # And a seller still cannot smuggle stock in through the price endpoint.
    assert "stock_left" not in s.OfferUpdateIn.model_fields


def test_an_offer_on_a_product_with_variants_must_name_them_all(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """An offer naming no variants used to win the card and leave every colour
    of the product without a count — a colour with no row on the winning offer
    reads as "nobody counts this apart"."""
    product = _untouched_with_variants(client)
    _, mine = _linked_seller(staff, "Bektemir Savdo", "+998900010006")
    cheap, _ = _undercuts(product["price"])
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    assert len(leaves) > 1

    bare = client.post(
        f"{API}/staff/offers", json={"product_id": product["id"], "price": cheap}, headers=mine
    )
    assert bare.status_code == 422

    partial = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": leaves[:1]},
        headers=mine,
    )
    assert partial.status_code == 422
    assert "detail" in partial.json()

    stray = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": [*leaves, 999999]},
        headers=mine,
    )
    assert stray.status_code == 400

    full = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": leaves},
        headers=mine,
    )
    assert full.status_code == 201
    offer = full.json()
    # Rows for every variant, parents included: the parents are what a
    # colour's count is rolled up onto.
    with Session(engine) as session:
        every = session.exec(
            select(ProductVariant).where(ProductVariant.product_id == product["id"])
        ).all()
    assert {v["variant_id"] for v in offer["variants"]} == {v.id for v in every}
    assert all(v["stock_left"] == 0 for v in offer["variants"])


def test_the_warehouse_rolls_a_shelf_up_from_its_leaves(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """A colour holding four when its sizes hold one, one and one is a shelf
    that lies about itself, so neither total is ever written directly."""
    product = _untouched_with_variants(client)
    _, mine = _linked_seller(staff, "Zangiota Savdo", "+998900010007")
    warehouse = staff(UserRole.WAREHOUSE, "+998900010008")
    cheap, _ = _undercuts(product["price"])

    with Session(engine) as session:
        leaves = of.leaf_variants(session, product["id"])
        leaf_ids = [v.id for v in leaves]
        parents = {v.id: v.parent_id for v in leaves}

    offer = client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap, variant_ids=leaf_ids),
        headers=mine,
    ).json()

    stocked = client.put(
        f"{API}/staff/offers/{offer['id']}/stock",
        json={
            "reason": "birinchi sanoq",
            "variants": [{"variant_id": v, "stock_left": 2} for v in leaf_ids],
        },
        headers=warehouse,
    )
    assert stocked.status_code == 200
    body = stocked.json()

    counts = {v["variant_id"]: v["stock_left"] for v in body["variants"]}
    assert body["stock_left"] == 2 * len(leaf_ids), "the offer is the sum of its colours"
    for colour_id in {p for p in parents.values() if p is not None}:
        children = [v for v, parent in parents.items() if parent == colour_id]
        assert counts[colour_id] == 2 * len(children), "a colour is the sum of its sizes"

    # The cache follows, one level down as well.
    page = client.get(f"{API}/products/{product['id']}").json()
    assert page["price"] == cheap and page["stock_left"] == body["stock_left"]
    shown = {v["id"]: v["stock_left"] for v in page["variants"]}
    assert all(shown[v] is not None for v in leaf_ids), "no colour left uncounted"
    assert shown[leaf_ids[0]] == 2

    # A later delivery of one variant is not a statement about the others.
    again = client.put(
        f"{API}/staff/offers/{offer['id']}/stock",
        json={
            "reason": "yana to'rttasi topildi",
            "variants": [{"variant_id": leaf_ids[0], "stock_left": 6}],
        },
        headers=warehouse,
    ).json()
    after = {v["variant_id"]: v["stock_left"] for v in again["variants"]}
    assert after[leaf_ids[0]] == 6
    assert after[leaf_ids[1]] == 2
    assert again["stock_left"] == body["stock_left"] + 4


def test_a_seller_sees_only_their_own_offers(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    admin: dict[str, str],
) -> None:
    product = _untouched_product(client)
    mine_id, mine = _linked_seller(staff, "Qibray Savdo", "+998900010009")
    _, theirs = _linked_seller(staff, "Nurafshon Savdo", "+998900010010")
    cheap, mid = _undercuts(product["price"])

    client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    )
    client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=theirs
    )

    ours = client.get(f"{API}/staff/offers", headers=mine).json()
    assert {o["seller"]["id"] for o in ours} == {mine_id}
    # Not a filter they chose — asking for somebody else's changes nothing.
    asked = client.get(f"{API}/staff/offers", params={"seller_id": 1}, headers=mine).json()
    assert {o["seller"]["id"] for o in asked} == {mine_id}

    everybody = client.get(
        f"{API}/staff/offers", params={"product_id": product["id"]}, headers=admin
    ).json()
    assert len(everybody) >= 3, "the house's offer and both sellers'"

    # An admin has no seller of their own, so they have to say who they mean.
    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], 5), headers=admin
    ).status_code == 400
    named = client.post(
        f"{API}/staff/offers",
        json=_offer_body(_untouched_product(client)["id"], 5, seller_id=mine_id),
        headers=admin,
    )
    assert named.status_code == 201
    assert named.json()["seller"]["id"] == mine_id


def test_a_seller_may_offer_a_product_only_once(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Angren Savdo", "+998900010011")
    cheap, mid = _undercuts(product["price"])

    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    ).status_code == 201
    assert client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=mine
    ).status_code == 409

    missing = client.post(
        f"{API}/staff/offers", json=_offer_body(999999, cheap), headers=mine
    )
    assert missing.status_code == 404
    gone = client.patch(f"{API}/staff/offers/999999", json={"price": 1}, headers=mine)
    assert gone.status_code == 404


def test_every_price_and_count_names_who_moved_it(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """A price is the number a seller will argue about."""
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Guliston Savdo", "+998900010012")
    warehouse = staff(UserRole.WAREHOUSE, "+998900010013")
    cheap, mid = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], mid), headers=mine
    ).json()
    client.patch(f"{API}/staff/offers/{offer['id']}", json={"price": cheap}, headers=mine)
    client.patch(f"{API}/staff/offers/{offer['id']}", json={"active": False}, headers=mine)
    client.put(
        f"{API}/staff/offers/{offer['id']}/stock",
        json=_stock_body(product["id"], 7),
        headers=warehouse,
    )

    rows = _audit_rows("offer.price", offer["id"]) + _audit_rows("offer.create", offer["id"])
    priced = [r for r in rows if r.action == "offer.price"]
    assert (priced[0].old_value, priced[0].new_value) == (str(mid), str(cheap))
    assert priced[0].actor_role is UserRole.SELLER

    withdrawn = _audit_rows("offer.active", offer["id"])
    assert (withdrawn[0].old_value, withdrawn[0].new_value) == ("true", "false")

    counted = _audit_rows("offer.stock_left", offer["id"])
    assert counted[0].old_value == "0" and int(counted[0].new_value) > 0
    assert counted[0].actor_role is UserRole.WAREHOUSE


def test_the_struck_through_price_can_be_put_up_and_taken_down(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product = _untouched_product(client)
    _, mine = _linked_seller(staff, "Denov Savdo", "+998900010014")
    cheap, mid = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers",
        json=_offer_body(product["id"], cheap, old_price=mid),
        headers=mine,
    ).json()
    assert offer["old_price"] == mid

    # Omitted leaves it alone; nought takes it away. Two different statements.
    kept = client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"price": cheap}, headers=mine
    ).json()
    assert kept["old_price"] == mid
    cleared = client.patch(
        f"{API}/staff/offers/{offer['id']}", json={"old_price": 0}, headers=mine
    ).json()
    assert cleared["old_price"] is None


# --------------------------------------------------------- the commission


def test_the_commission_is_snapshotted_on_the_order_line(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A rate is a term of a contract and contracts get renegotiated. A payout
    computed later against today's rate would quietly restate what a seller was
    owed for something they sold last year."""
    product = _untouched_product(client)
    seller_id, mine = _linked_seller(staff, "Buxoro Savdo", "+998900010015", commission=12)
    warehouse = staff(UserRole.WAREHOUSE, "+998900010016")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=mine
    ).json()
    client.put(
        f"{API}/staff/offers/{offer['id']}/stock",
        json=_stock_body(product["id"], 4),
        headers=warehouse,
    )

    client.delete(f"{API}/cart", headers=auth)
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()

    with Session(engine) as session:
        line = session.exec(
            select(OrderItem).where(OrderItem.order_id == order["id"])
        ).one()
        assert (line.seller_id, line.commission_percent) == (seller_id, 12)

        # The contract is renegotiated.
        seller = session.get(Seller, seller_id)
        seller.commission_percent = 20
        session.add(seller)
        session.commit()

        again = session.get(OrderItem, line.id)
        assert again.commission_percent == 12, "what was sold was sold at twelve"
        assert session.get(Seller, seller_id).commission_percent == 20

    # And the next sale is at the new rate.
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    later = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    with Session(engine) as session:
        fresh = session.exec(
            select(OrderItem).where(OrderItem.order_id == later["id"])
        ).one()
    assert fresh.commission_percent == 20


def test_the_house_orders_carry_the_rate_they_were_sold_at(client: TestClient) -> None:
    """The backfill the migration did: one seller, one rate, never changed
    since — so the figure was recoverable, and only while that stayed true."""
    with Session(engine) as session:
        lines = session.exec(
            select(OrderItem).where(col(OrderItem.seller_id).is_not(None))
        ).all()
    assert lines
    assert all(line.commission_percent > 0 for line in lines)


# --------------------------------------------------------- the browser's session


def test_the_refresh_token_arrives_as_a_cookie_the_page_cannot_read(
    client: TestClient,
) -> None:
    """A refresh token readable from JavaScript is one XSS away from being
    somebody else's session for the next sixty days."""
    phone = "+998900020001"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    verified = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": code}
    )
    assert verified.status_code == 200

    jar = verified.headers.get("set-cookie", "")
    assert "mb_refresh=" in jar
    assert "HttpOnly" in jar
    assert "SameSite=lax" in jar
    assert "Path=/api/v1/auth" in jar, "nothing else should carry this credential"

    # The response shape the apps read is untouched.
    body = verified.json()
    assert set(body) == {
        "access_token", "refresh_token", "token_type", "expires_in", "is_new_user"
    }


def test_a_browser_refreshes_with_no_body_at_all(client: TestClient) -> None:
    phone = "+998900020002"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    client.post(f"{API}/auth/otp/verify", json={"phone": phone, "code": code})

    # The cookie is in the client's jar; no body is sent.
    refreshed = client.post(f"{API}/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    # And it rotated, so the cookie has to have been replaced along with it.
    again = client.post(f"{API}/auth/refresh")
    assert again.status_code == 200


def test_the_apps_keep_refreshing_through_the_body(client: TestClient) -> None:
    """The shipped builds send the token in the body and must go on working
    exactly as they did."""
    phone = "+998900020003"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": code}
    ).json()
    client.cookies.clear()

    refreshed = client.post(
        f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != pair["refresh_token"]

    # Single use, as before.
    replayed = client.post(
        f"{API}/auth/refresh", json={"refresh_token": pair["refresh_token"]}
    )
    assert replayed.status_code == 401


def test_refreshing_with_neither_is_a_401(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post(f"{API}/auth/refresh").status_code == 401
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": "nonsense"}).status_code == 401


def test_signing_out_takes_the_cookie_with_it(client: TestClient) -> None:
    phone = "+998900020004"
    code = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()["dev_code"]
    pair = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": code}
    ).json()
    headers = {"Authorization": f"Bearer {pair['access_token']}"}

    out = client.post(f"{API}/auth/logout", headers=headers)
    assert out.status_code == 200
    assert 'mb_refresh=""' in out.headers.get("set-cookie", "")
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_the_allowed_origins_are_named_and_never_a_wildcard() -> None:
    """A browser refuses a wildcard together with credentials, so a deployment
    that set one would not be permissive — it would be broken."""
    from app.core.config import Settings

    assert "*" not in settings.cors_origin_list

    # All three staff applications, on both hostnames. Listing only the
    # backoffice is what had actually shipped, and the seller's cabinet and the
    # courier PWA could not reach this API at all: the browser refused the
    # request before it was sent, so the server never saw one to complain
    # about. A test that named the single origin which worked is why that
    # survived, so this names every one of them.
    for port in (5173, 5174, 5175):
        for host in ("localhost", "127.0.0.1"):
            assert f"http://{host}:{port}" in settings.cors_origin_list

    # And a wildcard in the environment is dropped rather than passed through.
    assert Settings(cors_origins="*").cors_origin_list == []
    assert Settings(cors_origins="*,https://ofis.minibozor.uz").cors_origin_list == [
        "https://ofis.minibozor.uz"
    ]


def test_a_preflight_answers_each_staff_application_by_name(
    client: TestClient,
) -> None:
    """One request per application, not one for the first of them.

    The three are separate builds on separate ports and in production on
    separate hostnames, and being allowed is a per-origin fact. Asserting it
    for the backoffice alone said nothing about the other two, which were in
    fact blocked.
    """
    for origin in (
        "http://localhost:5173",   # backoffice
        "http://localhost:5174",   # seller's cabinet
        "http://localhost:5175",   # courier PWA
    ):
        preflight = client.options(
            f"{API}/staff/returns",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert preflight.status_code == 200, origin
        assert preflight.headers["access-control-allow-origin"] == origin
        assert preflight.headers["access-control-allow-credentials"] == "true"

    # Somebody else's page gets nothing.
    stranger = client.options(
        f"{API}/staff/returns",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert stranger.headers.get("access-control-allow-origin") != "https://evil.example"


# --------------------------------------------------------- the shelf as a ledger


def _stock_is_consistent() -> list[str]:
    """Everything the warehouse must never contain, as a list of complaints.

    Two invariants, and both of them hold everywhere or the shelf is lying:

    * **The ledger.** An offer's running total is the sum of its movements. A
      figure is no longer a number anybody writes, so a disagreement here
      means something assigned to one instead of recording why it changed.
    * **The roll-up.** An offer's total is the sum of its colours, and a
      colour is the sum of its sizes. This one is not repairable after the
      fact: a sale that named no colour comes off the total and off no colour,
      and afterwards there is no working out which colour the shirt was. So it
      is checked beside the ledger rather than trusted.
    """
    complaints: list[str] = []
    with Session(engine) as session:
        for offer in session.exec(select(Offer)).all():
            ledger = st.on_hand(session, offer.id)
            if offer.stock_left != ledger:
                complaints.append(
                    f"offer {offer.id}: total {offer.stock_left} but ledger {ledger}"
                )

            variants = session.exec(
                select(ProductVariant).where(ProductVariant.product_id == offer.product_id)
            ).all()
            colours = [v for v in variants if v.kind is VariantKind.COLOR]
            sizes = [v for v in variants if v.kind is VariantKind.SIZE]
            counts = {
                row.variant_id: row.stock_left
                for row in session.exec(
                    select(OfferVariant).where(OfferVariant.offer_id == offer.id)
                ).all()
            }
            if not counts:
                continue

            for colour in colours:
                children = [z for z in sizes if z.parent_id == colour.id]
                if not children or colour.id not in counts:
                    continue
                total = sum(counts.get(z.id, 0) for z in children)
                if counts[colour.id] != total:
                    complaints.append(
                        f"offer {offer.id} colour {colour.id}: "
                        f"{counts[colour.id]} but its sizes hold {total}"
                    )

            if colours and all(c.id in counts for c in colours):
                across = sum(counts[c.id] for c in colours)
                if offer.stock_left != across:
                    complaints.append(
                        f"offer {offer.id}: total {offer.stock_left} "
                        f"but its colours hold {across}"
                    )
    return complaints


def _stocked_offer(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    name: str,
    phone: str,
    *,
    units: int = 6,
) -> tuple[dict, dict, dict[str, str], dict[str, str]]:
    """A seller's own offer on a fresh product, stocked through a supply.

    Which is the only way goods reach a shelf now: declared by the seller,
    counted in by the warehouse.
    """
    product = _untouched_product(client)
    _, seller = _linked_seller(staff, name, phone)
    warehouse = staff(UserRole.WAREHOUSE, f"{phone[:-1]}9")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=seller
    ).json()

    # All of it in one size, so the offer's total is the figure asked for
    # rather than the figure times the number of sizes. Which size is
    # arbitrary; that the total is right is not.
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    lines: list[dict] = [{"offer_id": offer["id"], "quantity": units}]
    if leaves:
        lines = [{"offer_id": offer["id"], "variant_id": leaves[0], "quantity": units}]
    declared = client.post(
        f"{API}/staff/supplies", json={"lines": lines, "note": "sinov partiyasi"}, headers=seller
    )
    assert declared.status_code == 201, declared.text
    supply = declared.json()

    received = client.post(
        f"{API}/staff/supplies/{supply['id']}/receive",
        json={
            "lines": [
                {"line_id": line["id"], "received_quantity": units}
                for line in supply["lines"]
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text
    return product, offer, seller, warehouse


def test_goods_reach_the_shelf_only_by_being_counted_in(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """A declaration is a promise. The shelf moves when somebody counts."""
    product = _untouched_product(client)
    _, seller = _linked_seller(staff, "Chinoz Savdo", "+998900020101")
    warehouse = staff(UserRole.WAREHOUSE, "+998900020102")
    cheap, _ = _undercuts(product["price"])

    offer = client.post(
        f"{API}/staff/offers", json=_offer_body(product["id"], cheap), headers=seller
    ).json()
    assert offer["stock_left"] == 0

    supply = client.post(
        f"{API}/staff/supplies",
        json={"lines": [{"offer_id": offer["id"], "quantity": 10}], "note": "birinchi palet"},
        headers=seller,
    ).json()
    assert supply["code"].startswith("SUP-"), "the code is ours, not the seller's label"
    assert supply["status"] == "declared"
    # Declared is not delivered: nothing on the shelf yet.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 0

    line_id = supply["lines"][0]["id"]
    received = client.post(
        f"{API}/staff/supplies/{supply['id']}/receive",
        json={"lines": [{"line_id": line_id, "received_quantity": 8}], "note": "2 tasi kelmadi"},
        headers=warehouse,
    )
    assert received.status_code == 200
    body = received.json()
    assert body["status"] == "received"
    # The promise and the fact are kept side by side, and so is the gap.
    assert body["lines"][0]["declared_quantity"] == 10
    assert body["lines"][0]["received_quantity"] == 8
    assert body["lines"][0]["difference"] == -2

    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 8
        movement = session.exec(
            select(StockMovement).where(StockMovement.supply_id == supply["id"])
        ).one()
    assert movement.kind is StockMovementKind.INTAKE
    assert movement.quantity == 8
    assert movement.reason == "2 tasi kelmadi"
    assert movement.actor_id is not None, "somebody counted it"
    assert not _stock_is_consistent()


def test_the_shelf_is_always_the_sum_of_its_movements(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The invariant, put through the whole cycle: received, sold, cancelled,
    written off, corrected. A count that disagrees with its own ledger is a
    count somebody assigned."""
    product, offer, seller, warehouse = _stocked_offer(
        client, staff, "Zarafshon Savdo", "+998900020111", units=9
    )
    assert not _stock_is_consistent()

    client.delete(f"{API}/cart", headers=auth)
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    ).json()
    assert not _stock_is_consistent()

    client.post(f"{API}/orders/{order['id']}/cancel", json={}, headers=auth)
    assert not _stock_is_consistent()

    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    body = {"quantity": 2, "reason": "suv ketgan"}
    if leaves:
        body["variant_id"] = leaves[0]
    written = client.post(
        f"{API}/staff/offers/{offer['id']}/write-off", json=body, headers=warehouse
    )
    assert written.status_code == 200
    assert not _stock_is_consistent()

    corrected = client.put(
        f"{API}/staff/offers/{offer['id']}/stock",
        json=_stock_body(product["id"], 4),
        headers=warehouse,
    )
    assert corrected.status_code == 200
    assert not _stock_is_consistent()

    # And the whole story is readable, oldest reason first.
    ledger = client.get(
        f"{API}/staff/stock/movements", params={"offer_id": offer["id"]}, headers=warehouse
    ).json()
    kinds = {row["kind"] for row in ledger["items"]}
    assert {"intake", "sale", "cancel_return", "write_off", "count_adjustment"} <= kinds
    assert all(row["reason"] for row in ledger["items"]), "every movement says why"


def test_a_correction_records_the_difference_and_not_the_figure(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """Two people counting the same shelf used to mean the second save erased
    the first. A difference adds; a figure overwrites."""
    product, offer, _, warehouse = _stocked_offer(
        client, staff, "Xiva Savdo", "+998900020121", units=5
    )
    url = f"{API}/staff/offers/{offer['id']}/stock"

    assert client.put(url, json=_stock_body(product["id"], 7), headers=warehouse).status_code == 200

    with Session(engine) as session:
        rows = session.exec(
            select(StockMovement).where(
                StockMovement.offer_id == offer["id"],
                StockMovement.kind == StockMovementKind.COUNT_ADJUSTMENT,
            )
        ).all()
    # The leaf that held five moves by two, not to seven. The empty ones jump
    # the whole way, which is also a difference and also recorded as one.
    assert rows and 2 in {row.quantity for row in rows}, "the difference, not the seven"
    assert all(row.quantity != 7 or row.variant_id is not None for row in rows)
    assert all(row.reason for row in rows)

    # And a correction with no reason is refused.
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    bare = (
        {"variants": [{"variant_id": leaves[0], "stock_left": 3}]}
        if leaves
        else {"stock_left": 3}
    )
    assert client.put(url, json=bare, headers=warehouse).status_code == 422


# --------------------------------------------------------- holding


def test_what_is_in_one_basket_is_not_offered_to_the_next_shopper(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """The last one of something used to sit in two baskets at once, and one of
    those two shoppers was going to be disappointed at the till."""
    product, offer, _, _ = _stocked_offer(
        client, staff, "Nukus Savdo", "+998900020131", units=2
    )
    mine = sign_in("+998900020135")
    theirs = sign_in("+998900020136")

    client.delete(f"{API}/cart", headers=mine)
    client.delete(f"{API}/cart", headers=theirs)

    pick = _pick(product["id"], 2)
    response = client.post(f"{API}/cart/items", json=pick, headers=mine)
    assert response.status_code == 201, response.text
    assert response.json()["items"][0]["quantity"] == 2

    # The card stops offering what is already promised.
    card = client.get(f"{API}/products/{product['id']}").json()
    assert card["stock_left"] == 0
    assert card["in_stock"] is False

    # And the next shopper is refused rather than sold the same two.
    refused = client.post(f"{API}/cart/items", json=pick, headers=theirs)
    assert refused.status_code == 409

    # Nothing left the shelf: it is held, not gone.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 2
        assert st.reserved(session, offer["id"]) == 2
    assert not _stock_is_consistent()


def test_a_hold_that_has_run_out_lets_go(
    client: TestClient,
    staff: Callable[[UserRole, str], dict[str, str]],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """An abandoned basket kept the last one of something for ever: nobody
    could buy it and nobody was going to."""
    product, offer, _, _ = _stocked_offer(
        client, staff, "Termiz Savdo", "+998900020141", units=1
    )
    mine = sign_in("+998900020145")
    theirs = sign_in("+998900020146")
    client.delete(f"{API}/cart", headers=mine)
    client.delete(f"{API}/cart", headers=theirs)

    pick = _pick(product["id"], 1)
    client.post(f"{API}/cart/items", json=pick, headers=mine)
    assert client.post(f"{API}/cart/items", json=pick, headers=theirs).status_code == 409

    # Walk away. Nothing sweeps up — the deadline is part of the question.
    with Session(engine) as session:
        line = session.exec(
            select(CartItem).where(CartItem.offer_id == offer["id"])
        ).first()
        assert line is not None
        line.reserved_until = utcnow() - timedelta(minutes=1)
        session.add(line)
        session.commit()
        assert st.reserved(session, offer["id"]) == 0
        of.refresh(session, product["id"])
        session.commit()

    assert client.get(f"{API}/products/{product['id']}").json()["in_stock"] is True
    assert client.post(f"{API}/cart/items", json=pick, headers=theirs).status_code == 201


def test_an_unpaid_order_holds_the_goods_until_the_courier_is_paid(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
    operator: dict[str, str],
) -> None:
    """Cash at the door is not a sale yet. Selling on promise-of-cash is how an
    order refused at the doorstep consumed stock nobody ever gave back."""
    product, offer, _, _ = _stocked_offer(
        client, staff, "Jizzax Savdo", "+998900020151", units=5
    )
    client.delete(f"{API}/cart", headers=auth)
    added = client.post(f"{API}/cart/items", json=_pick(product["id"], 2), headers=auth)
    assert added.status_code == 201, added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders",
        json={"address_id": address["id"], "payment_method": "cash"},
        headers=auth,
    )
    assert order.status_code == 201
    assert order.json()["paid"] is False
    order_id = order.json()["id"]

    # Still on the shelf, and held for this order.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 5
        assert st.reserved(session, offer["id"]) == 2
    assert client.get(f"{API}/products/{product['id']}").json()["stock_left"] == 3
    assert not _stock_is_consistent()

    for target in ("packing", "shipped", "delivered"):
        moved = client.post(
            f"{API}/staff/orders/{order_id}/status", json={"status": target}, headers=operator
        )
        assert moved.status_code == 200, moved.text

    # Paid at the door: now the goods leave, and the ledger says why.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 3
        assert st.reserved(session, offer["id"]) == 0
        sale = session.exec(
            select(StockMovement).where(
                StockMovement.order_id == order_id,
                StockMovement.kind == StockMovementKind.SALE,
            )
        ).one()
    assert sale.quantity == -2
    assert not _stock_is_consistent()


# --------------------------------------------------------- stocktakes and removals


def test_a_stocktake_writes_its_difference_as_a_movement(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    product, offer, _, warehouse = _stocked_offer(
        client, staff, "Navoiy Savdo", "+998900020161", units=4
    )

    opened = client.post(
        f"{API}/staff/stock-counts",
        json={"offer_id": offer["id"], "note": "chorak sanog'i"},
        headers=warehouse,
    )
    assert opened.status_code == 201
    count = opened.json()
    assert count["code"].startswith("CNT-")
    assert sum(line["expected"] for line in count["lines"]) == 4, "the books, frozen"

    # One fewer on the shelf than the books say.
    closed = client.post(
        f"{API}/staff/stock-counts/{count['id']}/close",
        json={
            "lines": [
                {
                    "variant_id": line["variant_id"],
                    "counted": max(0, line["expected"] - 1),
                }
                for line in count["lines"]
            ],
            "note": "bittasi yo'q",
        },
        headers=warehouse,
    )
    assert closed.status_code == 200
    body = closed.json()
    assert body["status"] == "closed"
    assert sum(line["difference"] or 0 for line in body["lines"]) == -1

    with Session(engine) as session:
        rows = session.exec(
            select(StockMovement).where(StockMovement.count_id == count["id"])
        ).all()
    assert rows and sum(row.quantity for row in rows) == -1
    assert all(row.kind is StockMovementKind.COUNT_ADJUSTMENT for row in rows)
    assert all(row.reason == "bittasi yo'q" for row in rows)
    assert not _stock_is_consistent()

    # Closing twice is not counting twice.
    assert client.post(
        f"{API}/staff/stock-counts/{count['id']}/close",
        json={"lines": [{"variant_id": None, "counted": 3}]},
        headers=warehouse,
    ).status_code == 409
    # Nor may two stocktakes run on one shelf at once.
    assert client.post(
        f"{API}/staff/stock-counts", json={"offer_id": offer["id"]}, headers=warehouse
    ).status_code == 201


def test_a_removal_holds_the_goods_then_takes_them_away(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    """Selling something that is already on a pallet by the door is the
    failure `ready` exists to prevent."""
    product, offer, seller, warehouse = _stocked_offer(
        client, staff, "Andijon Savdo", "+998900020171", units=6
    )
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    line = {"offer_id": offer["id"], "quantity": 4}
    if leaves:
        line["variant_id"] = leaves[0]

    requested = client.post(
        f"{API}/staff/removals",
        json={"reason": "unsold", "lines": [line], "note": "sotilmadi"},
        headers=seller,
    )
    assert requested.status_code == 201
    removal = requested.json()
    assert removal["code"].startswith("RMV-")
    assert removal["status"] == "requested"

    # Requested is not picked: nothing is held yet.
    with Session(engine) as session:
        assert st.reserved(session, offer["id"]) == 0

    # A seller may not walk off with it themselves.
    assert client.post(
        f"{API}/staff/removals/{removal['id']}/collect", headers=seller
    ).status_code == 403

    ready = client.post(
        f"{API}/staff/removals/{removal['id']}/prepare",
        json={"lines": [{"line_id": removal["lines"][0]["id"], "prepared_quantity": 4}]},
        headers=warehouse,
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    # Picked and standing by the door: still ours to account for, nobody's to buy.
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 6
        assert st.reserved(session, offer["id"]) == 4
        assert st.sellable(session, session.get(Offer, offer["id"])) == 2
    assert not _stock_is_consistent()

    collected = client.post(
        f"{API}/staff/removals/{removal['id']}/collect", headers=warehouse
    )
    assert collected.status_code == 200
    assert collected.json()["status"] == "collected"

    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).stock_left == 2
        assert st.reserved(session, offer["id"]) == 0
        movement = session.exec(
            select(StockMovement).where(StockMovement.removal_id == removal["id"])
        ).one()
    assert movement.kind is StockMovementKind.SELLER_RETURN
    assert movement.quantity == -4
    assert not _stock_is_consistent()

    # And it cannot be collected twice.
    assert client.post(
        f"{API}/staff/removals/{removal['id']}/collect", headers=warehouse
    ).status_code == 409


def test_a_seller_sees_their_own_batches_and_nobody_elses(
    client: TestClient, staff: Callable[[UserRole, str], dict[str, str]]
) -> None:
    _, mine_offer, mine, warehouse = _stocked_offer(
        client, staff, "Farg'ona Savdo", "+998900020181", units=3
    )
    _, _, theirs, _ = _stocked_offer(
        client, staff, "Namangan Savdo", "+998900020191", units=3
    )

    ours = client.get(f"{API}/staff/supplies", headers=mine).json()
    assert ours and {row["seller"]["name"] for row in ours} == {"Farg'ona Savdo"}
    others = client.get(f"{API}/staff/supplies", headers=theirs).json()
    assert {row["seller"]["name"] for row in others} == {"Namangan Savdo"}

    # The warehouse sees everybody's, which is the point of a warehouse.
    everything = client.get(f"{API}/staff/supplies", headers=warehouse).json()
    assert {"Farg'ona Savdo", "Namangan Savdo"} <= {r["seller"]["name"] for r in everything}

    # And one seller cannot read the other's by id.
    theirs_id = next(r["id"] for r in others)
    assert client.get(f"{API}/staff/supplies/{theirs_id}", headers=mine).status_code == 403

    # Nor declare a batch against somebody else's offer.
    assert client.post(
        f"{API}/staff/supplies",
        json={"lines": [{"offer_id": mine_offer["id"], "quantity": 1}]},
        headers=theirs,
    ).status_code == 403, "whose offer it is comes before what it names"

    # The ledger is scoped the same way.
    mine_ledger = client.get(f"{API}/staff/stock/movements", headers=mine).json()
    with Session(engine) as session:
        mine_offers = {
            o.id
            for o in session.exec(
                select(Offer).where(Offer.id == mine_offer["id"])
            ).all()
        }
    assert mine_offers <= {row["offer_id"] for row in mine_ledger["items"]}
    assert all(row["offer_id"] != theirs_id for row in mine_ledger["items"])


def test_only_the_warehouse_moves_a_count(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The seller sets the price, the warehouse sets the count. That line is
    the whole reason these live in different files."""
    product, offer, seller, warehouse = _stocked_offer(
        client, staff, "Qarshi Savdo", "+998900020201", units=3
    )
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]
    line: dict = {"offer_id": offer["id"], "quantity": 1}
    if leaves:
        line["variant_id"] = leaves[0]
    supply = client.post(f"{API}/staff/supplies", json={"lines": [line]}, headers=seller).json()
    receipt = {"lines": [{"line_id": supply["lines"][0]["id"], "received_quantity": 1}]}

    for headers, expected in ((None, 401), (auth, 403), (seller, 403)):
        response = client.post(
            f"{API}/staff/supplies/{supply['id']}/receive",
            json=receipt,
            **({"headers": headers} if headers else {}),
        )
        assert response.status_code == expected

    write_off = {"quantity": 1, "reason": "sinov"}
    if leaves:
        write_off["variant_id"] = leaves[0]
    assert client.post(
        f"{API}/staff/offers/{offer['id']}/write-off", json=write_off, headers=seller
    ).status_code == 403
    assert client.post(
        f"{API}/staff/stock-counts", json={"offer_id": offer["id"]}, headers=seller
    ).status_code == 403

    # The warehouse can, and the shelf tells the whole story afterwards.
    assert client.post(
        f"{API}/staff/supplies/{supply['id']}/receive", json=receipt, headers=warehouse
    ).status_code == 200
    shelf = client.get(f"{API}/staff/offers/{offer['id']}/shelf", headers=warehouse).json()
    total = next(row for row in shelf if row["variant_id"] is None)
    assert total["on_hand"] == total["sellable"] + total["reserved"]


def test_a_counted_product_will_not_go_into_a_basket_unnamed(
    client: TestClient, auth: dict[str, str]
) -> None:
    """A sale that names no colour comes off the offer's total and off no
    colour at all, and afterwards there is no working out which colour the
    shirt was. The choice is required rather than guessed."""
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products/1").json()
    sizes = [v for v in product["variants"] if v["kind"] == "size"]
    assert sizes, "seeded with a colour × size grid"

    bare = client.post(
        f"{API}/cart/items", json={"product_id": product["id"]}, headers=auth
    )
    assert bare.status_code == 422
    assert bare.json()["detail"] == "O'lchamni tanlang"

    # A colour on its own is not a leaf either, where the colours have sizes.
    colour = next(v for v in product["variants"] if v["kind"] == "color")
    half = client.post(
        f"{API}/cart/items",
        json={"product_id": product["id"], "color_variant_id": colour["id"]},
        headers=auth,
    )
    assert half.status_code == 422

    # And with the size, it goes in.
    named = client.post(
        f"{API}/cart/items", json=_pick(product["id"]), headers=auth
    )
    assert named.status_code == 201, named.text
    line = named.json()["items"][0]
    assert line["variant_id"] is not None
    assert line["color_variant_id"] is not None

    # A product nobody counts by variant still goes in on its own.
    plain = _variantless_product(client)
    assert client.post(
        f"{API}/cart/items", json={"product_id": plain["id"]}, headers=auth
    ).status_code == 201

    assert not _stock_is_consistent()


def test_a_colour_with_nothing_left_is_out_of_stock_not_a_question(
    client: TestClient,
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The one case both apps send no size: a colour whose every size has
    gone. Asking them to choose one would be asking for something that is not
    there, so the answer stays the one they are written to expect."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900020211")
    client.delete(f"{API}/cart", headers=auth)

    # The winning offer's own shelf, because that is the one a shopper buys
    # from — emptying somebody else's cell would leave the colour perfectly
    # buyable and the question perfectly sensible.
    product_id = 1
    with Session(engine) as session:
        assert of.winning_offer(session, product_id) is not None
        colour = next(
            leaf.parent_id
            for leaf in of.leaf_variants(session, product_id)
            if leaf.parent_id is not None
        )
        # Every seller's, not only the winner's: emptying one shelf hands the
        # card to the next, and the colour would still be for sale.
        cells = [
            (offer.id, leaf.id, of.variant_stock(session, offer.id, leaf.id) or 0)
            for offer in of.offers_for(session, product_id, active_only=False)
            for leaf in of.leaf_variants(session, product_id)
            if leaf.parent_id == colour
        ]

    for shelf_id, variant_id, held in cells:
        if held:
            written = client.post(
                f"{API}/staff/offers/{shelf_id}/write-off",
                json={"variant_id": variant_id, "quantity": held, "reason": "suv ketgan"},
                headers=warehouse,
            )
            assert written.status_code == 200, written.text

    # Every size of that colour is gone, so there is no size to choose. Both
    # apps ask exactly this, and the answer they expect is the true one.
    refused = client.post(
        f"{API}/cart/items",
        json={"product_id": product_id, "color_variant_id": colour},
        headers=auth,
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "Mahsulot mavjud emas"
    # The other half of the pair — a colour that *does* still have sizes gets
    # asked rather than refused — is
    # `test_a_counted_product_will_not_go_into_a_basket_unnamed`.
    assert not _stock_is_consistent()


def test_the_warehouse_can_see_the_shelves_it_counts(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Reading which offers exist is not pricing them — a warehouse that
    cannot list a shelf cannot go and count it."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900020221")

    listed = client.get(f"{API}/staff/offers", headers=warehouse)
    assert listed.status_code == 200
    assert listed.json(), "every shelf, not one seller's"
    assert len({row["seller"]["id"] for row in listed.json()}) >= 1

    # Still nobody else's business.
    assert client.get(f"{API}/staff/offers", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/offers", headers=operator).status_code == 403
    # And reading is not writing.
    offer_id = listed.json()[0]["id"]
    assert client.patch(
        f"{API}/staff/offers/{offer_id}", json={"price": 1}, headers=warehouse
    ).status_code == 403


# --------------------------------------------------------- the catalogue's owner


def _new_card(
    client: TestClient,
    headers: dict[str, str],
    *,
    sku: str,
    title: str,
    price: int = 500_000,
    path: str = "/staff/catalog/products",
) -> dict:
    listing = client.get(f"{API}/categories").json()
    created = client.post(
        f"{API}{path}",
        json={
            "sku": sku,
            "title": title,
            "subtitle": "sinov",
            "category_slug": listing[0]["slug"],
            "price": price,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_an_admin_takes_on_a_seller_and_nobody_else_can(
    client: TestClient,
    admin: dict[str, str],
    operator: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Until now the only way to make a second seller was the database, which
    left the multi-seller model exercised by nothing but a fixture."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030001")
    body = {"name": "Chorsu Bozori", "phone": "+998781112233", "commission_percent": 8}

    assert client.post(f"{API}/staff/sellers", json=body).status_code == 401
    assert client.post(f"{API}/staff/sellers", json=body, headers=auth).status_code == 403
    assert client.post(f"{API}/staff/sellers", json=body, headers=operator).status_code == 403
    assert client.post(f"{API}/staff/sellers", json=body, headers=warehouse).status_code == 403

    created = client.post(f"{API}/staff/sellers", json=body, headers=admin)
    assert created.status_code == 201, created.text
    seller = created.json()
    assert (seller["name"], seller["commission_percent"], seller["active"]) == (
        "Chorsu Bozori",
        8,
        True,
    )
    assert seller["user_phone"] is None, "nobody signs in as them yet"

    # And one name, one seller.
    assert client.post(f"{API}/staff/sellers", json=body, headers=admin).status_code == 409


def test_linking_an_account_is_what_makes_somebody_a_seller(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """There is no state where an account is attached to a seller and cannot
    act as one, so the role comes with the link rather than through a second
    door that does not exist."""
    phone = "+998900030011"
    theirs = sign_in(phone)          # an ordinary customer, for now
    assert client.get(f"{API}/staff/offers", headers=theirs).status_code == 403

    seller = client.post(
        f"{API}/staff/sellers",
        json={"name": "Yakkasaroy Savdo", "user_phone": phone},
        headers=admin,
    ).json()
    assert seller["user_phone"] == phone

    with Session(engine) as session:
        account = session.exec(select(User).where(User.phone == phone)).one()
    assert account.role is UserRole.SELLER

    # They can now see their own shelf — and it is theirs, not everybody's.
    theirs = sign_in(phone)
    mine = client.get(f"{API}/staff/offers", headers=theirs)
    assert mine.status_code == 200
    assert mine.json() == [], "a new seller has no offers"

    # A privilege change is logged with a name against it.
    rows = _audit_rows("user.role", account.id)
    assert rows and rows[0].new_value == "seller"

    # And one account cannot be two sellers.
    assert client.post(
        f"{API}/staff/sellers",
        json={"name": "Boshqa Savdo", "user_phone": phone},
        headers=admin,
    ).status_code == 409


def test_a_second_seller_undercuts_the_first_on_the_same_card(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The whole model, end to end and through the front door: the admin takes
    on a seller, the seller offers on a card the platform already owns, the
    warehouse books the goods in, and the cheaper price wins the card."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030021")
    phone = "+998900030022"
    sign_in(phone)
    seller_row = client.post(
        f"{API}/staff/sellers",
        json={"name": "Olmaliq Savdo", "user_phone": phone, "commission_percent": 11},
        headers=admin,
    ).json()
    seller = sign_in(phone)

    product = _untouched_product(client)
    was = client.get(f"{API}/products/{product['id']}").json()
    cheap, _ = _undercuts(was["price"])
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product["id"])]

    offer = client.post(
        f"{API}/staff/offers",
        json={"product_id": product["id"], "price": cheap, "variant_ids": leaves},
        headers=seller,
    )
    assert offer.status_code == 201, offer.text
    # Not in the shop until the warehouse has it: a price with nothing behind
    # it does not win a card.
    assert client.get(f"{API}/products/{product['id']}").json()["price"] == was["price"]

    line: dict = {"offer_id": offer.json()["id"], "quantity": 4}
    if leaves:
        line["variant_id"] = leaves[0]
    supply = client.post(
        f"{API}/staff/supplies", json={"lines": [line]}, headers=seller
    ).json()
    received = client.post(
        f"{API}/staff/supplies/{supply['id']}/receive",
        json={"lines": [{"line_id": supply["lines"][0]["id"], "received_quantity": 4}]},
        headers=warehouse,
    )
    assert received.status_code == 200, received.text

    won = client.get(f"{API}/products/{product['id']}").json()
    assert (won["price"], won["seller"], won["stock_left"]) == (cheap, "Olmaliq Savdo", 4)

    # And the card lists both sellers, cheapest first.
    quotes = client.get(f"{API}/products/{product['id']}/offers").json()
    assert [q["seller"]["name"] for q in quotes][0] == "Olmaliq Savdo"
    assert len(quotes) >= 2
    assert sum(1 for q in quotes if q["is_winner"]) == 1

    # The admin sees who they took on, and what they carry.
    seen = next(
        row
        for row in client.get(f"{API}/staff/sellers", headers=admin).json()
        if row["id"] == seller_row["id"]
    )
    assert (seen["offer_count"], seen["commission_percent"]) == (1, 11)
    assert not _stock_is_consistent()


def test_a_card_nobody_has_approved_is_not_in_the_shop(
    client: TestClient, admin: dict[str, str], auth: dict[str, str]
) -> None:
    """Every customer-facing path that returns a product, held to the same
    rule. A shopper who can find a draft has been shown something that does
    not exist yet."""
    card = _new_card(client, admin, sku="MB-DRAFT-1", title="Sinov chiroq, qoralama")
    assert card["status"] == "draft"
    product_id = card["id"]

    def visible() -> dict[str, bool]:
        listing = client.get(f"{API}/products", params={"page_size": 60}).json()
        sold_out_too = client.get(
            f"{API}/products", params={"page_size": 60, "show_sold_out": True}
        ).json()
        similar = client.get(f"{API}/products/1/similar").json()
        home = client.get(f"{API}/home").json()
        suggest = client.get(f"{API}/search/suggest", params={"q": "Sinov chiroq"}).json()
        client.put(f"{API}/favorites/{product_id}", headers=auth)
        favourites = client.get(f"{API}/favorites", headers=auth).json()
        return {
            "listing": any(p["id"] == product_id for p in listing["items"]),
            "even_sold_out": any(p["id"] == product_id for p in sold_out_too["items"]),
            "similar": any(p["id"] == product_id for p in similar),
            "home": any(
                p["id"] == product_id
                for section in home["sections"]
                for p in section["products"]
            ),
            "suggest": any(row["product_id"] == product_id for row in suggest),
            "favourites": any(p["id"] == product_id for p in favourites["items"]),
            "page": client.get(f"{API}/products/{product_id}").status_code == 200,
            "offers": client.get(f"{API}/products/{product_id}/offers").status_code == 200,
        }

    assert not any(visible().values()), visible()

    # Published, and the same walk finds it — the page and the offer list at
    # least; the rails and the typeahead want stock, which it has none of.
    published = client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "published"},
        headers=admin,
    )
    assert published.status_code == 200, published.text
    now = visible()
    assert now["page"] and now["offers"]
    assert now["even_sold_out"], "in the shop, and the filter can show it"
    assert now["favourites"], "a favourite that can be opened again"

    # Withdrawn, and it is gone from all of them again.
    client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "archived"},
        headers=admin,
    )
    assert not any(visible().values())


def test_a_sellers_proposal_never_lands_in_the_shop(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """The catalogue belongs to the platform. A seller may suggest a card; a
    copy per seller would duplicate the catalogue and leave the warehouse
    holding the same goods in two places under two names."""
    phone = "+998900030031"
    sign_in(phone)
    client.post(
        f"{API}/staff/sellers",
        json={"name": "Uchtepa Savdo", "user_phone": phone},
        headers=admin,
    )
    seller = sign_in(phone)

    proposed = _new_card(
        client,
        seller,
        sku="MB-PROP-1",
        title="Sotuvchi taklifi, stol chirog'i",
        path="/staff/catalog/proposals",
    )
    assert proposed["status"] == "moderating", "not in the shop, whoever sent it"
    assert proposed["proposed_by"]["name"] == "Uchtepa Savdo"
    assert client.get(f"{API}/products/{proposed['id']}").status_code == 404

    # A seller cannot write straight into the catalogue, nor approve their own.
    assert client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "MB-PROP-2",
            "title": "O'zim yozdim",
            "category_slug": client.get(f"{API}/categories").json()[0]["slug"],
            "price": 100_000,
        },
        headers=seller,
    ).status_code == 403
    assert client.post(
        f"{API}/staff/catalog/products/{proposed['id']}/status",
        json={"status": "published"},
        headers=seller,
    ).status_code == 403

    # The queue, oldest first, and a refusal the seller can read.
    queue = client.get(
        f"{API}/staff/catalog/products", params={"status": "moderating"}, headers=admin
    ).json()
    assert any(row["id"] == proposed["id"] for row in queue["items"])
    assert client.post(
        f"{API}/staff/catalog/products/{proposed['id']}/status",
        json={"status": "rejected"},
        headers=admin,
    ).status_code == 400, "a refusal without a reason is not a refusal"

    refused = client.post(
        f"{API}/staff/catalog/products/{proposed['id']}/status",
        json={"status": "rejected", "reason": "Rasm yo'q, tavsif to'liq emas"},
        headers=admin,
    ).json()
    assert refused["status"] == "rejected"
    assert refused["moderation_note"] == "Rasm yo'q, tavsif to'liq emas"
    assert refused["next_statuses"] == ["moderating", "archived"]
    assert client.get(f"{API}/products/{proposed['id']}").status_code == 404

    rows = _audit_rows("product.status", proposed["id"])
    assert (rows[0].old_value, rows[0].new_value) == ("moderating", "rejected")
    assert rows[0].actor_role is UserRole.ADMIN
    assert "Rasm yo'q" in rows[0].note

    # Fixed and sent back, then approved — and only then is it in the shop.
    client.post(
        f"{API}/staff/catalog/products/{proposed['id']}/status",
        json={"status": "moderating"},
        headers=admin,
    )
    client.post(
        f"{API}/staff/catalog/products/{proposed['id']}/status",
        json={"status": "published"},
        headers=admin,
    )
    page = client.get(f"{API}/products/{proposed['id']}")
    assert page.status_code == 200
    assert page.json()["title"] == "Sotuvchi taklifi, stol chirog'i"

    # Published does not go back to a queue: it is withdrawn, which is a
    # different act.
    assert client.post(
        f"{API}/staff/catalog/products/{proposed['id']}/status",
        json={"status": "moderating"},
        headers=admin,
    ).status_code == 409


def test_the_catalogue_can_be_written_without_a_developer(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Everything a card is made of, through the front door: a category, a
    brand, the card, its photographs, its colours and sizes, its spec table."""
    assert client.post(
        f"{API}/staff/catalog/categories",
        json={"slug": "sinov-turkum", "name": "Sinov turkumi", "icon": "box", "sort": 99},
        headers=admin,
    ).status_code == 201
    assert client.post(
        f"{API}/staff/catalog/brands",
        json={"slug": "sinov-brend", "name": "Sinov Brend"},
        headers=admin,
    ).status_code == 201

    created = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "MB-FULL-1",
            "title": "Sinov krossovka",
            "subtitle": "to'liq kartochka",
            "description": "Admin panelidan yozilgan",
            "category_slug": "sinov-turkum",
            "brand_slug": "sinov-brend",
            "price": 700_000,
            "old_price": 900_000,
            "badge": "Yangi",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    card = created.json()
    product_id = card["id"]
    assert (card["stock_left"], card["offer_count"]) == (0, 0), "stock is the ledger's"

    # One SKU, one card.
    assert client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "MB-FULL-1",
            "title": "Takror",
            "category_slug": "sinov-turkum",
            "price": 1,
        },
        headers=admin,
    ).status_code == 409

    images = client.post(
        f"{API}/staff/catalog/products/{product_id}/images",
        json={"url": "products/gazelle.png", "sort": 0},
        headers=admin,
    )
    assert images.status_code == 201 and len(images.json()) == 1

    colour = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "color", "label": "Qora", "value": "#0E0F12"},
        headers=admin,
    )
    assert colour.status_code == 201
    colour_id = colour.json()[0]["id"]
    # A size has to say which colour it is a size of.
    assert client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "size", "label": "42", "value": "42"},
        headers=admin,
    ).status_code == 400
    sized = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "size", "label": "42", "value": "42", "parent_id": colour_id},
        headers=admin,
    )
    assert sized.status_code == 201
    assert {v["kind"] for v in sized.json()} == {"color", "size"}

    specs = client.put(
        f"{API}/staff/catalog/products/{product_id}/specs",
        json={"specs": [{"key": "Material", "value": "Zamsh"}, {"key": "Vazn", "value": "320 g"}]},
        headers=admin,
    )
    assert [row["key"] for row in specs.json()] == ["Material", "Vazn"]

    # Published, and the customer sees the card the admin built.
    client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "published"},
        headers=admin,
    )
    page = client.get(f"{API}/products/{product_id}").json()
    assert page["brand"]["name"] == "Sinov Brend"
    assert page["category"]["slug"] == "sinov-turkum"
    assert [spec["key"] for spec in page["specs"]] == ["Material", "Vazn"]
    assert page["images"] and page["badge"] == "Yangi"
    assert {v["label"] for v in page["variants"]} == {"Qora", "42"}

    # A category with a card in it is load-bearing.
    assert client.delete(
        f"{API}/staff/catalog/categories/sinov-turkum", headers=admin
    ).status_code == 409
    assert client.delete(
        f"{API}/staff/catalog/brands/sinov-brend", headers=admin
    ).status_code == 409


def _card_with_a_colour(
    client: TestClient, admin: dict[str, str], sku: str, *, with_a_size: bool
) -> tuple[int, int]:
    """A published card carrying a colour, and optionally a size of it.

    Written through the admin endpoints, so the test depends on nothing the
    seed happened to include.
    """
    slug = client.get(f"{API}/categories").json()[0]["slug"]
    card = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": sku,
            "title": f"Sinov kiyim {sku}",
            "category_slug": slug,
            "price": 300_000,
        },
        headers=admin,
    )
    assert card.status_code == 201, card.text
    product_id = card.json()["id"]

    colour = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "color", "label": "Qora", "value": "#0E0F12"},
        headers=admin,
    )
    assert colour.status_code == 201, colour.text
    colour_id = colour.json()[0]["id"]

    leaf_id = colour_id
    if with_a_size:
        sized = client.post(
            f"{API}/staff/catalog/products/{product_id}/variants",
            json={"kind": "size", "label": "L", "value": "L", "parent_id": colour_id},
            headers=admin,
        )
        assert sized.status_code == 201, sized.text
        leaf_id = next(v["id"] for v in sized.json() if v["kind"] == "size")

    client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "published"},
        headers=admin,
    )
    return product_id, leaf_id


def _stock_a_leaf(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
    product_id: int,
    leaf_id: int,
    units: int,
) -> int:
    """The house takes the card on and the warehouse books goods in."""
    with Session(engine) as session:
        house_id = session.exec(select(Seller).where(Seller.name == "Mini Bozor")).one().id
    offer = client.post(
        f"{API}/staff/offers",
        json={
            "product_id": product_id,
            "price": 300_000,
            "seller_id": house_id,
            "variant_ids": [leaf_id],
        },
        headers=admin,
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]

    supply = client.post(
        f"{API}/staff/supplies",
        json={
            "lines": [{"offer_id": offer_id, "variant_id": leaf_id, "quantity": units}],
            "seller_id": house_id,
        },
        headers=admin,
    )
    assert supply.status_code == 201, supply.text
    received = client.post(
        f"{API}/staff/supplies/{supply.json()['id']}/receive",
        json={
            "lines": [
                {"line_id": supply.json()["lines"][0]["id"], "received_quantity": units}
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text
    return offer_id


def test_a_variant_with_a_history_cannot_be_deleted(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The ledger would stop explaining its own totals, and an old order would
    point at a row that is not there."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030041")
    product_id, leaf_id = _card_with_a_colour(
        client, admin, "MB-VAR-1", with_a_size=True
    )

    # Before anything has happened to it, a variant is just a row.
    spare = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "color", "label": "Oq", "value": "#FFFFFF"},
        headers=admin,
    ).json()
    spare_id = next(v["id"] for v in spare if v["label"] == "Oq")
    assert client.delete(
        f"{API}/staff/catalog/products/{product_id}/variants/{spare_id}",
        headers=admin,
    ).status_code == 200

    _stock_a_leaf(client, admin, warehouse, product_id, leaf_id, 3)

    refused = client.delete(
        f"{API}/staff/catalog/products/{product_id}/variants/{leaf_id}",
        headers=admin,
    )
    assert refused.status_code == 409
    assert "harakat" in refused.json()["detail"]
    assert not _stock_is_consistent()


def test_a_size_cannot_be_added_under_stock_that_is_already_counted(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A shelf counted on colours would have every figure sitting a level
    above where the ledger looks for it, with no way to say how the colour's
    stock divides between the new sizes."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030042")
    product_id, colour_id = _card_with_a_colour(
        client, admin, "MB-VAR-2", with_a_size=False
    )

    # No stock yet, so the grid may still change shape.
    allowed = client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "size", "label": "S", "value": "S", "parent_id": colour_id},
        headers=admin,
    )
    assert allowed.status_code == 201

    other_id, other_colour = _card_with_a_colour(
        client, admin, "MB-VAR-3", with_a_size=False
    )
    _stock_a_leaf(client, admin, warehouse, other_id, other_colour, 4)

    blocked = client.post(
        f"{API}/staff/catalog/products/{other_id}/variants",
        json={"kind": "size", "label": "M", "value": "M", "parent_id": other_colour},
        headers=admin,
    )
    assert blocked.status_code == 409
    assert "sanoq" in blocked.json()["detail"]
    assert not _stock_is_consistent()


def test_standing_a_seller_down_takes_their_offers_with_them(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Left active, the cheapest card in the shop could belong to somebody we
    have stopped dealing with."""
    product, offer, seller_headers, _ = _stocked_offer(
        client, staff, "Sirdaryo Savdo", "+998900030051", units=5
    )
    assert client.get(f"{API}/products/{product['id']}").json()["seller"] == "Sirdaryo Savdo"

    with Session(engine) as session:
        seller_id = session.exec(
            select(Seller).where(Seller.name == "Sirdaryo Savdo")
        ).one().id

    stood_down = client.patch(
        f"{API}/staff/sellers/{seller_id}", json={"active": False}, headers=admin
    )
    assert stood_down.status_code == 200
    assert stood_down.json()["active"] is False

    # The card is back with whoever else sells it.
    assert client.get(f"{API}/products/{product['id']}").json()["seller"] != "Sirdaryo Savdo"
    with Session(engine) as session:
        assert session.get(Offer, offer["id"]).active is False
    rows = _audit_rows("seller.active", seller_id)
    assert (rows[0].old_value, rows[0].new_value) == ("true", "false")
    assert seller_headers


# --------------------------------------------------------- the shop window


def test_the_banner_order_is_the_order_the_app_shows(
    client: TestClient, admin: dict[str, str], operator: dict[str, str]
) -> None:
    """A seasonal banner used to need a deployment. The order is set as a
    whole, because a screen where rows are dragged knows the final order and
    nothing else."""
    assert client.get(f"{API}/staff/showcase/banners", headers=operator).status_code == 403

    added = client.post(
        f"{API}/staff/showcase/banners",
        json={
            "title": "Qishki chegirma",
            "kicker": "MINI BOZOR / SINOV",
            "image_url": "banners/deal.png",
            "target_type": "category",
            "target_value": "elektronika",
        },
        headers=admin,
    )
    assert added.status_code == 201, added.text
    mine = added.json()
    assert mine["active"] is True

    # New banners go at the bottom, where a person expects to find them.
    listed = client.get(f"{API}/staff/showcase/banners", headers=admin).json()
    assert listed[-1]["id"] == mine["id"]
    assert [row["sort"] for row in listed] == sorted(row["sort"] for row in listed)

    # The app already shows it, at the end.
    on_screen = client.get(f"{API}/home").json()["banners"]
    assert on_screen[-1]["title"] == "Qishki chegirma"

    # Drag it to the front, and the app follows.
    order = [mine["id"], *[row["id"] for row in listed if row["id"] != mine["id"]]]
    reordered = client.post(
        f"{API}/staff/showcase/banners/order", json={"ids": order}, headers=admin
    )
    assert reordered.status_code == 200
    assert [row["id"] for row in reordered.json()] == order
    assert client.get(f"{API}/home").json()["banners"][0]["title"] == "Qishki chegirma"

    # A partial order would leave the rest holding numbers that mean something
    # else, so it is refused rather than half applied.
    assert client.post(
        f"{API}/staff/showcase/banners/order", json={"ids": [mine["id"]]}, headers=admin
    ).status_code == 400
    assert client.post(
        f"{API}/staff/showcase/banners/order",
        json={"ids": [mine["id"], mine["id"]]},
        headers=admin,
    ).status_code == 400

    # Switched off, and it is out of the window without being lost.
    client.patch(
        f"{API}/staff/showcase/banners/{mine['id']}",
        json={"active": False},
        headers=admin,
    )
    titles = [b["title"] for b in client.get(f"{API}/home").json()["banners"]]
    assert "Qishki chegirma" not in titles
    assert any(
        row["id"] == mine["id"]
        for row in client.get(f"{API}/staff/showcase/banners", headers=admin).json()
    )

    assert client.delete(
        f"{API}/staff/showcase/banners/{mine['id']}", headers=admin
    ).status_code == 200


def test_a_home_rail_can_be_added_moved_and_taken_down(
    client: TestClient, admin: dict[str, str]
) -> None:
    before = [section["key"] for section in client.get(f"{API}/home").json()["sections"]]
    assert before, "the seeded window is not empty"

    created = client.post(
        f"{API}/staff/showcase/sections",
        json={
            "key": "sinov-rail",
            "title": "Sinov tokchasi",
            "subtitle": "faqat test uchun",
            "layout": "rail",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    # A rail pointing at a category that is not there would show nothing.
    assert client.post(
        f"{API}/staff/showcase/sections",
        json={"key": "yoq-rail", "title": "Yo'q", "category_slug": "bunday-turkum-yoq"},
        headers=admin,
    ).status_code == 404
    assert client.post(
        f"{API}/staff/showcase/sections",
        json={"key": "sinov-rail", "title": "Takror"},
        headers=admin,
    ).status_code == 409

    shown = [section["key"] for section in client.get(f"{API}/home").json()["sections"]]
    assert shown[-1] == "sinov-rail"

    rows = client.get(f"{API}/staff/showcase/sections", headers=admin).json()
    order = [
        next(r["id"] for r in rows if r["key"] == "sinov-rail"),
        *[r["id"] for r in rows if r["key"] != "sinov-rail"],
    ]
    client.post(f"{API}/staff/showcase/sections/order", json={"ids": order}, headers=admin)
    assert client.get(f"{API}/home").json()["sections"][0]["key"] == "sinov-rail"

    # Out of season rather than deleted: the alternative is writing it again
    # from memory next year.
    client.patch(
        f"{API}/staff/showcase/sections/sinov-rail",
        json={"active": False, "title": "Sinov tokchasi (yopiq)"},
        headers=admin,
    )
    keys = [section["key"] for section in client.get(f"{API}/home").json()["sections"]]
    assert "sinov-rail" not in keys
    assert set(before) <= set(keys), "nothing else moved"

    assert client.delete(
        f"{API}/staff/showcase/sections/sinov-rail", headers=admin
    ).status_code == 200
    assert client.delete(
        f"{API}/staff/showcase/sections/sinov-rail", headers=admin
    ).status_code == 404


def test_a_promo_code_can_be_written_and_switched_off(
    client: TestClient, admin: dict[str, str], auth: dict[str, str]
) -> None:
    created = client.post(
        f"{API}/staff/showcase/promos",
        json={"code": "sinov20", "percent_off": 20, "min_total": 100_000},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    # Stored upper case, because that is how the cart looks one up — a
    # lower-case row would be a code nobody could redeem.
    assert created.json()["code"] == "SINOV20"

    # A discount that discounts nothing is not a promo code.
    assert client.post(
        f"{API}/staff/showcase/promos", json={"code": "bosh"}, headers=admin
    ).status_code == 400
    assert client.post(
        f"{API}/staff/showcase/promos", json={"code": "SINOV20", "amount_off": 1}, headers=admin
    ).status_code == 409

    # The customer's cart takes it.
    client.delete(f"{API}/cart", headers=auth)
    product = _untouched_product(client)
    client.post(f"{API}/cart/items", json=_pick(product["id"], 1), headers=auth)
    applied = client.post(f"{API}/cart/promo", json={"code": "SINOV20"}, headers=auth)
    assert applied.status_code == 200, applied.text
    assert applied.json()["totals"]["promo_code"] == "SINOV20"
    assert applied.json()["totals"]["discount"] > 0

    # Switched off, and the same code stops working.
    client.patch(
        f"{API}/staff/showcase/promos/SINOV20", json={"active": False}, headers=admin
    )
    assert client.post(
        f"{API}/cart/promo", json={"code": "SINOV20"}, headers=auth
    ).status_code == 400

    # A discount is money, so writing one is logged.
    with Session(engine) as session:
        promo_id = session.exec(
            select(PromoCode).where(PromoCode.code == "SINOV20")
        ).one().id
    assert _audit_rows("promo.create", promo_id)
    off = _audit_rows("promo.active", promo_id)
    assert (off[0].old_value, off[0].new_value) == ("true", "false")


# --------------------------------------------------------- who works here


def _find_user(client: TestClient, admin: dict[str, str], phone: str) -> dict:
    """The account behind a phone number, the way a panel finds it."""
    found = client.get(f"{API}/staff/users", params={"q": phone}, headers=admin)
    assert found.status_code == 200, found.text
    rows = [row for row in found.json()["items"] if row["phone"] == phone]
    assert rows, f"{phone} not found by search"
    return rows[0]


def test_an_admin_appoints_an_operator_and_nobody_else_can(
    client: TestClient,
    admin: dict[str, str],
    operator: dict[str, str],
    auth: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """Until now a role came from a shell script, so a panel could list the
    operators and had no way to appoint one."""
    phone = "+998900040001"
    theirs = sign_in(phone)                      # an ordinary customer, for now
    account = _find_user(client, admin, phone)
    assert account["role"] == "customer"

    # Searching by the digits alone is enough — an admin has the number in
    # front of them, not a directory.
    assert _find_user(client, admin, phone)["id"] == account["id"]
    by_tail = client.get(f"{API}/staff/users", params={"q": "900040001"}, headers=admin)
    assert account["id"] in [row["id"] for row in by_tail.json()["items"]]

    body = {"role": "operator", "note": "yangi smena"}
    door = f"{API}/staff/users/{account['id']}/role"
    assert client.patch(door, json=body).status_code == 401
    assert client.patch(door, json=body, headers=auth).status_code == 403
    assert client.patch(door, json=body, headers=theirs).status_code == 403
    # Not even the role that runs the shop day to day: this is how somebody
    # would promote themselves.
    assert client.patch(door, json=body, headers=operator).status_code == 403

    done = client.patch(door, json=body, headers=admin)
    assert done.status_code == 200, done.text
    assert done.json()["role"] == "operator"

    # And the role is the whole of the difference — the same token now opens
    # the operator's door.
    assert client.get(f"{API}/staff/returns", headers=theirs).status_code == 200

    # A privilege change is the kind of thing asked about months later.
    rows = _audit_rows("user.role", account["id"])
    assert rows[-1].action == "user.role"
    assert (rows[-1].old_value, rows[-1].new_value) == ("customer", "operator")
    assert rows[-1].actor_role is UserRole.ADMIN
    assert rows[-1].note == "yangi smena"

    # Saving a form that changed nothing is not an error, and does not add a
    # row to a log that is meant to be a list of changes.
    again = client.patch(door, json={"role": "operator"}, headers=admin)
    assert again.status_code == 200
    assert len(_audit_rows("user.role", account["id"])) == len(rows)

    # Standing them down again is the same door.
    back = client.patch(door, json={"role": "customer"}, headers=admin)
    assert back.status_code == 200
    assert back.json()["role"] == "customer"
    assert client.get(f"{API}/staff/returns", headers=theirs).status_code == 403


def test_the_last_admin_cannot_be_stood_down(
    client: TestClient,
    admin: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """The one privilege change that cannot be undone through the door it was
    made in: demote the last admin and there is nobody left who can hand the
    role back."""
    me = client.get(f"{API}/staff/me", headers=admin).json()
    door = f"{API}/staff/users/{me['id']}/role"

    refused = client.patch(door, json={"role": "operator"}, headers=admin)
    assert refused.status_code == 409, refused.text
    assert "admin" in refused.json()["detail"].lower()
    assert client.get(f"{API}/staff/me", headers=admin).json()["role"] == "admin"

    # With a second admin in place the same request is ordinary.
    phone = "+998900040002"
    theirs = sign_in(phone)
    second = _find_user(client, admin, phone)
    assert client.patch(
        f"{API}/staff/users/{second['id']}/role", json={"role": "admin"}, headers=admin
    ).status_code == 200

    stood_down = client.patch(door, json={"role": "operator"}, headers=theirs)
    assert stood_down.status_code == 200, stood_down.text
    assert stood_down.json()["role"] == "operator"

    # Put back by the admin who is left, which is the point of the rule.
    assert client.patch(
        door, json={"role": "admin"}, headers=theirs
    ).status_code == 200

    # And now the second one is the one who cannot go — whichever of them is
    # last is the one the rule protects.
    client.patch(
        f"{API}/staff/users/{second['id']}/role", json={"role": "customer"},
        headers=admin,
    )
    assert client.patch(
        door, json={"role": "operator"}, headers=admin
    ).status_code == 409


def test_a_role_a_seller_link_hands_out_obeys_the_same_rule(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Linking an account to a seller sets its role, so it is a second door on
    to the same rule and has to be guarded at the same place."""
    me = client.get(f"{API}/staff/me", headers=admin).json()
    seller = client.post(
        f"{API}/staff/sellers",
        json={"name": "Yakka Admin Savdo", "phone": "+998781119988"},
        headers=admin,
    ).json()

    # The last admin filling in a form about somebody else's shop would
    # otherwise demote themselves out of the panel.
    refused = client.patch(
        f"{API}/staff/sellers/{seller['id']}",
        json={"user_phone": me["phone"]},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text
    assert client.get(f"{API}/staff/me", headers=admin).json()["role"] == "admin"


# --------------------------------------------------------- a card in three languages


def _ru(headers: dict[str, str] | None = None) -> dict[str, str]:
    return {**(headers or {}), "Accept-Language": "ru"}


def _en(headers: dict[str, str] | None = None) -> dict[str, str]:
    return {**(headers or {}), "Accept-Language": "en"}


def _trilingual_card(client: TestClient, admin: dict[str, str]) -> dict:
    """A card written the way the panel writes one: all three languages, in the
    same request that creates the row."""
    category = client.post(
        f"{API}/staff/catalog/categories",
        json={
            "slug": "sinov-choynak",
            "name": "Choynaklar",
            "subtitle": "Choy uchun",
            "translations": {
                "ru": {"name": "Чайники", "subtitle": "Для чая"},
                "en": {"name": "Teapots", "subtitle": "For tea"},
            },
        },
        headers=admin,
    )
    assert category.status_code == 201, category.text

    brand = client.post(
        f"{API}/staff/catalog/brands",
        json={
            "slug": "sinov-hunarmand",
            "name": "Hunarmand",
            "translations": {"ru": {"name": "Ремесленник"}, "en": {"name": "Artisan"}},
        },
        headers=admin,
    )
    assert brand.status_code == 201, brand.text

    created = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-I18N-1",
            "title": "Choynak",
            "subtitle": "Sopol choynak",
            "description": "Qo'lda yasalgan sopol choynak.",
            "badge": "Yangi",
            "warranty": "Kafolat 1 yil",
            "category_slug": "sinov-choynak",
            "brand_slug": "sinov-hunarmand",
            "price": 120_000,
            "translations": {
                "ru": {
                    "title": "Чайник",
                    "subtitle": "Керамический чайник",
                    "description": "Керамический чайник ручной работы.",
                    "badge": "Новинка",
                    "warranty": "Гарантия 1 год",
                },
                "en": {
                    "title": "Teapot",
                    "subtitle": "Ceramic teapot",
                    "description": "A hand-thrown ceramic teapot.",
                    "badge": "New",
                    "warranty": "1-year warranty",
                },
            },
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    product = created.json()

    variant = client.post(
        f"{API}/staff/catalog/products/{product['id']}/variants",
        json={
            "kind": "color",
            "label": "Ko'k",
            "value": "#2E5AAC",
            "translations": {"ru": {"label": "Синий"}, "en": {"label": "Blue"}},
        },
        headers=admin,
    )
    assert variant.status_code == 201, variant.text

    specs = client.put(
        f"{API}/staff/catalog/products/{product['id']}/specs",
        json={
            "specs": [
                {
                    "key": "Material",
                    "value": "Sopol",
                    "translations": {
                        "ru": {"key": "Материал", "value": "Керамика"},
                        "en": {"key": "Material", "value": "Ceramic"},
                    },
                }
            ]
        },
        headers=admin,
    )
    assert specs.status_code == 200, specs.text

    published = client.post(
        f"{API}/staff/catalog/products/{product['id']}/status",
        json={"status": "published"},
        headers=admin,
    )
    assert published.status_code == 200, published.text
    return product


def test_a_card_written_in_three_languages_answers_in_all_three(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The table has always been read. Until now nothing could write to it, so
    every card added after the seed made the catalogue a little more Uzbek than
    the app claims it is."""
    product = _trilingual_card(client, admin)
    url = f"{API}/products/{product['id']}"

    uz = client.get(url).json()
    assert (uz["title"], uz["subtitle"]) == ("Choynak", "Sopol choynak")
    assert uz["description"].startswith("Qo'lda")
    assert (uz["badge"], uz["warranty"]) == ("Yangi", "Kafolat 1 yil")
    assert uz["category"]["name"] == "Choynaklar"
    assert uz["brand"]["name"] == "Hunarmand"
    assert uz["variants"][0]["label"] == "Ko'k"
    assert (uz["specs"][0]["key"], uz["specs"][0]["value"]) == ("Material", "Sopol")

    ru = client.get(url, headers=_ru()).json()
    assert (ru["title"], ru["subtitle"]) == ("Чайник", "Керамический чайник")
    assert ru["description"] == "Керамический чайник ручной работы."
    assert (ru["badge"], ru["warranty"]) == ("Новинка", "Гарантия 1 год")
    assert ru["category"]["name"] == "Чайники"
    assert ru["brand"]["name"] == "Ремесленник"
    assert ru["variants"][0]["label"] == "Синий"
    assert (ru["specs"][0]["key"], ru["specs"][0]["value"]) == ("Материал", "Керамика")

    en = client.get(url, headers=_en()).json()
    assert (en["title"], en["brand"]["name"]) == ("Teapot", "Artisan")
    assert en["specs"][0]["value"] == "Ceramic"

    # The value the row itself holds is untouched: the panel edits Uzbek, and
    # sees Uzbek.
    card = client.get(
        f"{API}/staff/catalog/products/{product['id']}", headers=_ru(admin)
    ).json()
    assert card["title"] == "Choynak"

    # A listing carries the translation too, not only the product page.
    # Nothing has been booked in against this card, so the grid is asked for
    # what it normally hides.
    listing = client.get(
        f"{API}/products",
        params={"category": "sinov-choynak", "show_sold_out": True},
        headers=_ru(),
    ).json()
    assert [row["title"] for row in listing["items"]] == ["Чайник"]


def test_a_card_with_no_translation_is_uzbek_in_every_language(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The fallback is what makes a partly translated catalogue usable: a card
    written by somebody in a hurry degrades to Uzbek, not to blanks."""
    listing = client.get(f"{API}/categories").json()
    created = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-I18N-2",
            "title": "Tarjimasiz kartochka",
            "subtitle": "Faqat o'zbekcha",
            "category_slug": listing[0]["slug"],
            "price": 90_000,
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    product = created.json()
    client.post(
        f"{API}/staff/catalog/products/{product['id']}/status",
        json={"status": "published"},
        headers=admin,
    )

    for headers in ({}, _ru(), _en()):
        body = client.get(f"{API}/products/{product['id']}", headers=headers).json()
        assert body["title"] == "Tarjimasiz kartochka"
        assert body["subtitle"] == "Faqat o'zbekcha"


def test_a_translation_can_be_read_back_and_taken_away(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The catalogue endpoints answer in one language and fall back silently,
    which is right for a shopper and no use to an editor trying to see what is
    still missing."""
    listing = client.get(f"{API}/categories").json()
    product = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-I18N-3",
            "title": "Piyola",
            "category_slug": listing[0]["slug"],
            "price": 30_000,
            "translations": {"ru": {"title": "Пиала"}},
        },
        headers=admin,
    ).json()
    client.post(
        f"{API}/staff/catalog/products/{product['id']}/status",
        json={"status": "published"},
        headers=admin,
    )
    door = f"{API}/staff/catalog/translations/product/{product['id']}"

    held = client.get(door, headers=admin)
    assert held.status_code == 200, held.text
    assert held.json()["uz"]["title"] == "Piyola"
    assert held.json()["translations"]["ru"]["title"] == "Пиала"
    assert "en" not in held.json()["translations"]

    # A field left out of the payload is left alone; the English arriving
    # later does not wipe the Russian that was already there.
    client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"en": {"title": "Tea bowl"}}},
        headers=admin,
    )
    assert client.get(door, headers=admin).json()["translations"] == {
        "ru": {"title": "Пиала"},
        "en": {"title": "Tea bowl"},
    }

    # Blank is not the same as absent: it takes the row away, and the card
    # falls back to its Uzbek again.
    client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"ru": {"title": ""}}},
        headers=admin,
    )
    assert "ru" not in client.get(door, headers=admin).json()["translations"]
    assert client.get(
        f"{API}/products/{product['id']}", headers=_ru()
    ).json()["title"] == "Piyola"

    # A field the shape does not have is a bug in the caller, not a silent
    # no-op that shows up months later as a card nobody translated.
    assert client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"ru": {"nomi": "Пиала"}}},
        headers=admin,
    ).status_code == 422
    assert client.patch(
        f"{API}/staff/catalog/products/{product['id']}",
        json={"translations": {"de": {"title": "Teeschale"}}},
        headers=admin,
    ).status_code == 422
    # Uzbek is the row itself, and is not written here.
    assert client.get(door).status_code == 401


def test_a_replaced_spec_table_does_not_inherit_the_old_rows_words(
    client: TestClient, admin: dict[str, str]
) -> None:
    """SQLite hands a deleted row's id straight back out, so a spec table
    replaced in place would arrive in Russian describing something else."""
    listing = client.get(f"{API}/categories").json()
    product = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-I18N-4",
            "title": "Likobcha",
            "category_slug": listing[0]["slug"],
            "price": 20_000,
        },
        headers=admin,
    ).json()
    client.post(
        f"{API}/staff/catalog/products/{product['id']}/status",
        json={"status": "published"},
        headers=admin,
    )
    specs_url = f"{API}/staff/catalog/products/{product['id']}/specs"

    client.put(
        specs_url,
        json={
            "specs": [
                {
                    "key": "Rang",
                    "value": "Oq",
                    "translations": {"ru": {"key": "Цвет", "value": "Белый"}},
                }
            ]
        },
        headers=admin,
    )
    client.put(
        specs_url,
        json={"specs": [{"key": "Og'irlik", "value": "300 g"}]},
        headers=admin,
    )

    ru = client.get(f"{API}/products/{product['id']}", headers=_ru()).json()
    assert [(s["key"], s["value"]) for s in ru["specs"]] == [("Og'irlik", "300 g")]


# --------------------------------------------------------- photographs


def _photograph(width: int, height: int, fmt: str = "JPEG") -> bytes:
    """A picture of the size a phone actually takes one."""
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (width, height))
    for x in range(0, width, 7):
        for y in range(0, height, 11):
            image.putpixel((x, y), ((x * 3) % 256, (y * 5) % 256, (x + y) % 256))
    buffer = BytesIO()
    image.save(buffer, fmt, quality=95)
    return buffer.getvalue()


def test_a_photograph_is_re_encoded_shrunk_and_renamed(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The catalogue's pictures are 169–641 px. What arrives from a phone is
    four megabytes and four thousand pixels across, under a name of its
    own."""
    from io import BytesIO

    from PIL import Image

    from app.images import MEDIA_DIR

    original = _photograph(4000, 3000)
    sent = client.post(
        f"{API}/staff/media",
        files={"file": ("IMG_20260907_113045.jpg", original, "image/jpeg")},
        headers=admin,
    )
    assert sent.status_code == 201, sent.text
    body = sent.json()

    # Shrunk on its long side, and the shape kept.
    assert (body["width"], body["height"]) == (1600, 1200)
    assert body["bytes"] < len(original)

    # Named by us. Nothing of what the uploader called it survives.
    assert body["media_url"].startswith("uploads/")
    assert body["media_url"].endswith(".webp")
    assert "IMG_20260907" not in body["media_url"]

    # Written where the existing StaticFiles mount already serves, and in the
    # format we chose rather than the one that was sent.
    on_disk = MEDIA_DIR / body["media_url"]
    assert on_disk.is_file()
    with Image.open(BytesIO(on_disk.read_bytes())) as written:
        assert written.format == "WEBP"
        assert written.size == (1600, 1200)
    assert client.get(f"/media/{body['media_url']}").status_code == 200

    # And the path is the shape the rest of the catalogue already stores, so
    # it goes straight back as a product image.
    listing = client.get(f"{API}/categories").json()
    product = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-MEDIA-1",
            "title": "Suratli kartochka",
            "category_slug": listing[0]["slug"],
            "price": 55_000,
        },
        headers=admin,
    ).json()
    attached = client.post(
        f"{API}/staff/catalog/products/{product['id']}/images",
        json={"url": body["media_url"]},
        headers=admin,
    )
    assert attached.status_code == 201, attached.text
    assert attached.json() == [body["media_url"]]

    # A picture already inside the box is re-encoded but never enlarged.
    small = client.post(
        f"{API}/staff/media",
        files={"file": ("swatch.png", _photograph(640, 640, "PNG"), "image/png")},
        headers=admin,
    ).json()
    assert (small["width"], small["height"]) == (640, 640)


def test_a_file_that_is_not_an_image_is_refused_however_it_is_named(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The name, the extension and the declared type are all the uploader's to
    write. The bytes are the only honest part of the request."""
    refused = client.post(
        f"{API}/staff/media",
        files={"file": ("photo.jpg", b"#!/bin/sh\necho not a picture\n", "image/jpeg")},
        headers=admin,
    )
    assert refused.status_code == 415, refused.text
    assert refused.json()["detail"]

    # Nor does a real image header make the rest of the file an image.
    truncated = _photograph(320, 240)[:40]
    assert client.post(
        f"{API}/staff/media",
        files={"file": ("half.jpg", truncated, "image/jpeg")},
        headers=admin,
    ).status_code == 415

    assert client.post(
        f"{API}/staff/media",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
        headers=admin,
    ).status_code == 400


def test_a_file_over_the_limit_is_refused_before_it_is_read(
    client: TestClient, admin: dict[str, str]
) -> None:
    from app.images import MAX_BYTES

    too_big = b"\xff\xd8\xff\xe0" + b"\x00" * (MAX_BYTES + 1024)
    refused = client.post(
        f"{API}/staff/media",
        files={"file": ("huge.jpg", too_big, "image/jpeg")},
        headers=admin,
    )
    assert refused.status_code == 413, refused.text
    assert "8" in refused.json()["detail"], "the limit is named, not just refused"


def test_only_the_people_who_write_cards_may_upload_a_picture(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A seller photographs the goods they propose, so uploading is theirs as
    well as the admin's — and nobody else's."""
    seller = staff(UserRole.SELLER, "+998900040011")
    picture = _photograph(200, 200)

    def send(headers: dict[str, str] | None) -> int:
        return client.post(
            f"{API}/staff/media",
            files={"file": ("a.jpg", picture, "image/jpeg")},
            headers=headers or {},
        ).status_code

    assert send(None) == 401
    assert send(auth) == 403
    assert send(operator) == 403
    assert send(seller) == 201
    assert send(admin) == 201


# --------------------------------------------------------- what the editor reads


def test_the_admin_lists_answer_in_the_words_the_rows_hold(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The customer endpoints translate as they go, which is right for the app
    and wrong for the field that writes the source: an editor working in
    Russian would be shown the translation and save it back as the Uzbek."""
    client.post(
        f"{API}/staff/catalog/categories",
        json={
            "slug": "sinov-admin-turkum",
            "name": "Sinov turkumi",
            "subtitle": "izohi",
            "translations": {"ru": {"name": "Тестовая категория"}},
        },
        headers=admin,
    )
    client.post(
        f"{API}/staff/catalog/brands",
        json={
            "slug": "sinov-admin-brend",
            "name": "Sinov Brend",
            "translations": {"ru": {"name": "Тестовый бренд"}},
        },
        headers=admin,
    )

    # The shopper's list, asked for in Russian, answers in Russian.
    shopper = client.get(f"{API}/brands", headers=_ru()).json()
    assert "Тестовый бренд" in [row["name"] for row in shopper]

    # The editor's list, asked for in Russian, answers with the row itself.
    brands = client.get(f"{API}/staff/catalog/brands", headers=_ru(admin))
    assert brands.status_code == 200, brands.text
    mine = next(row for row in brands.json() if row["slug"] == "sinov-admin-brend")
    assert mine["name"] == "Sinov Brend"

    categories = client.get(f"{API}/staff/catalog/categories", headers=_ru(admin))
    assert categories.status_code == 200, categories.text
    row = next(r for r in categories.json() if r["slug"] == "sinov-admin-turkum")
    assert (row["name"], row["subtitle"]) == ("Sinov turkumi", "izohi")

    # Flat, and the tree recoverable from parent_slug — a child of the seeded
    # root reports which root it hangs from.
    slugs = {r["slug"] for r in categories.json()}
    assert len(slugs) > len(client.get(f"{API}/categories").json()), "children too"
    assert any(r["parent_slug"] for r in categories.json())

    # Nobody else's list.
    assert client.get(f"{API}/staff/catalog/brands").status_code == 401


def test_the_admin_lists_carry_the_counts_that_explain_a_refusal(
    client: TestClient, admin: dict[str, str]
) -> None:
    """`GET /brands` sends `product_count: 0` for every row — the figure is
    only computed in `/products/filters`, scoped to one listing. Here it is the
    whole catalogue, and it is the answer to "why can't I delete this"."""
    client.post(
        f"{API}/staff/catalog/categories",
        json={"slug": "sinov-sanoq", "name": "Sanoq turkumi"},
        headers=admin,
    )
    client.post(
        f"{API}/staff/catalog/brands",
        json={"slug": "sinov-sanoq-brend", "name": "Sanoq Brend"},
        headers=admin,
    )

    def counts() -> tuple[int, int]:
        category = next(
            r
            for r in client.get(f"{API}/staff/catalog/categories", headers=admin).json()
            if r["slug"] == "sinov-sanoq"
        )
        brand = next(
            r
            for r in client.get(f"{API}/staff/catalog/brands", headers=admin).json()
            if r["slug"] == "sinov-sanoq-brend"
        )
        return category["product_count"], brand["product_count"]

    assert counts() == (0, 0)
    assert client.delete(
        f"{API}/staff/catalog/brands/sinov-sanoq-brend", headers=admin
    ).status_code == 200

    # Written again, this time with a card against it.
    client.post(
        f"{API}/staff/catalog/brands",
        json={"slug": "sinov-sanoq-brend", "name": "Sanoq Brend"},
        headers=admin,
    )
    client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-SANOQ-1",
            "title": "Sanoq kartochkasi",
            "category_slug": "sinov-sanoq",
            "brand_slug": "sinov-sanoq-brend",
            "price": 40_000,
        },
        headers=admin,
    )
    assert counts() == (1, 1)

    # And the count is exactly why the delete is refused.
    assert client.delete(
        f"{API}/staff/catalog/categories/sinov-sanoq", headers=admin
    ).status_code == 409
    assert client.delete(
        f"{API}/staff/catalog/brands/sinov-sanoq-brend", headers=admin
    ).status_code == 409


def test_the_queue_can_be_counted_without_fetching_it(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The sidebar says "3 waiting" on every screen. Fetching the queue to
    render an integer would be a page of cards downloaded each time."""
    before = client.get(f"{API}/staff/catalog/summary", headers=admin)
    assert before.status_code == 200, before.text
    waiting = before.json()["counts"]["moderating"]

    listing = client.get(f"{API}/categories").json()
    made = client.post(
        f"{API}/staff/catalog/proposals",
        json={
            "sku": "SINOV-QUEUE-1",
            "title": "Navbat kartochkasi",
            "category_slug": listing[0]["slug"],
            "price": 30_000,
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text

    after = client.get(f"{API}/staff/catalog/summary", headers=admin).json()
    assert after["counts"]["moderating"] == waiting + 1
    # Every state is named, so a zero is a zero rather than a missing key.
    assert set(after["counts"]) == {
        "draft", "moderating", "published", "rejected", "archived",
    }

    client.post(
        f"{API}/staff/catalog/products/{made.json()['id']}/status",
        json={"status": "published"},
        headers=admin,
    )
    assert (
        client.get(f"{API}/staff/catalog/summary", headers=admin).json()["counts"][
            "moderating"
        ]
        == waiting
    )
    assert client.get(f"{API}/staff/catalog/summary").status_code == 401


def test_a_draft_card_can_be_read_back_in_full_to_be_edited(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A draft is invisible through `/products/{id}` — that path is narrowed to
    what is in the shop, which is the point of it. So until now nothing could
    read back the description, the photographs, the colours or the specs of a
    card that had not been published, and an edit form had nothing to open."""
    listing = client.get(f"{API}/categories").json()
    made = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-EDIT-1",
            "title": "Tahrir kartochkasi",
            "subtitle": "qoralama",
            "description": "Uzun tavsif matni.",
            "badge": "Yangi",
            "warranty": "Kafolat 1 yil",
            "category_slug": listing[0]["slug"],
            "price": 60_000,
            "translations": {"ru": {"title": "Карточка", "description": "Описание."}},
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    product_id = made.json()["id"]

    # The draft is not in the shop, and reading it there says so.
    assert client.get(f"{API}/products/{product_id}").status_code == 404

    card = client.get(f"{API}/staff/catalog/products/{product_id}", headers=admin)
    assert card.status_code == 200, card.text
    body = card.json()
    assert body["description"] == "Uzun tavsif matni."
    assert (body["badge"], body["warranty"]) == ("Yangi", "Kafolat 1 yil")
    assert body["is_original"] is True
    # Every language at once, so the editor can mark the empty cells.
    assert body["translations"]["ru"]["title"] == "Карточка"
    assert "en" not in body["translations"]

    # The list shape stays lean — a description per row is prose fetched to
    # draw a table.
    page = client.get(
        f"{API}/staff/catalog/products", params={"q": "SINOV-EDIT-1"}, headers=admin
    ).json()
    assert "description" not in page["items"][0]

    specs = client.put(
        f"{API}/staff/catalog/products/{product_id}/specs",
        json={
            "specs": [
                {
                    "key": "Material",
                    "value": "Sopol",
                    "translations": {"ru": {"key": "Материал"}},
                }
            ]
        },
        headers=admin,
    )
    assert specs.status_code == 200, specs.text
    read_back = client.get(
        f"{API}/staff/catalog/products/{product_id}/specs", headers=admin
    )
    assert read_back.status_code == 200, read_back.text
    assert [(r["key"], r["value"]) for r in read_back.json()] == [("Material", "Sopol")]

    # With the Russian on the row. The table is only ever replaced whole, so a
    # form that could not read this back would delete it by saving an
    # unrelated row.
    assert read_back.json()[0]["translations"]["ru"]["key"] == "Материал"

    # Saving the table again, carrying the translation with it, keeps it.
    client.put(
        f"{API}/staff/catalog/products/{product_id}/specs",
        json={
            "specs": [
                {
                    "key": "Material",
                    "value": "Sopol",
                    "translations": {"ru": {"key": "Материал"}},
                },
                {"key": "Vazn", "value": "300 g"},
            ]
        },
        headers=admin,
    )
    again = client.get(
        f"{API}/staff/catalog/products/{product_id}/specs", headers=admin
    ).json()
    assert [r["key"] for r in again] == ["Material", "Vazn"]
    assert again[0]["translations"]["ru"]["key"] == "Материал"
    # And the new row inherits nothing from whatever held its id before.
    assert again[1]["translations"] == {}


def test_photographs_can_be_reordered_because_the_ids_are_readable(
    client: TestClient, admin: dict[str, str]
) -> None:
    """`DELETE .../images/{image_id}` has always existed and nothing ever told
    the panel what `image_id` was — the write endpoints answer with bare URLs,
    which redraws a gallery and cannot edit one."""
    listing = client.get(f"{API}/categories").json()
    product_id = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "SINOV-RASM-1",
            "title": "Rasmli kartochka",
            "category_slug": listing[0]["slug"],
            "price": 70_000,
        },
        headers=admin,
    ).json()["id"]

    for index, name in enumerate(("bir.png", "ikki.png", "uch.png")):
        client.post(
            f"{API}/staff/catalog/products/{product_id}/images",
            json={"url": f"products/{name}", "sort": index},
            headers=admin,
        )

    images = client.get(
        f"{API}/staff/catalog/products/{product_id}/images", headers=admin
    )
    assert images.status_code == 200, images.text
    rows = images.json()
    assert [r["url"] for r in rows] == ["products/bir.png", "products/ikki.png", "products/uch.png"]
    assert all(isinstance(r["id"], int) for r in rows)

    door = f"{API}/staff/catalog/products/{product_id}/images/order"
    flipped = [rows[2]["id"], rows[0]["id"], rows[1]["id"]]
    moved = client.put(door, json={"ids": flipped}, headers=admin)
    assert moved.status_code == 200, moved.text
    assert [r["url"] for r in moved.json()] == [
        "products/uch.png", "products/bir.png", "products/ikki.png"
    ]

    # The whole list or nothing: a partial order would leave the rest holding
    # numbers that mean something else.
    assert client.put(
        door, json={"ids": [rows[0]["id"]]}, headers=admin
    ).status_code == 400
    assert client.put(
        door, json={"ids": [rows[0]["id"], rows[0]["id"], rows[1]["id"]]}, headers=admin
    ).status_code == 400

    # The first photograph is the cover, so the order reaches the shop.
    client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "published"},
        headers=admin,
    )
    assert client.get(f"{API}/products/{product_id}").json()["images"][0] == "products/uch.png"

    # And an id read here is the id the delete takes.
    gone = client.delete(
        f"{API}/staff/catalog/products/{product_id}/images/{rows[0]['id']}",
        headers=admin,
    )
    assert gone.status_code == 200
    assert len(client.get(
        f"{API}/staff/catalog/products/{product_id}/images", headers=admin
    ).json()) == 2


def test_the_editor_is_told_what_it_may_not_do_before_it_tries(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Both guards come from the functions the write endpoints refuse with, so
    a greyed-out button and a 409 are the same rule rather than two copies of
    it that drift."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900030051")
    door = f"{API}/staff/catalog/products"

    # A colour with nothing against it yet: deletable, and the tree can still
    # change shape.
    product_id, colour_id = _card_with_a_colour(
        client, admin, "MB-GUARD-1", with_a_size=False
    )
    open_ = client.get(f"{door}/{product_id}/variants", headers=admin)
    assert open_.status_code == 200, open_.text
    assert open_.json()["can_add_size"] is True
    assert open_.json()["size_blocked_reason"] == ""
    colour = next(v for v in open_.json()["variants"] if v["id"] == colour_id)
    assert colour["can_delete"] is True and colour["blocked_reason"] == ""

    # Stock arrives on the colour. Now a first size would move where the shelf
    # is counted, and the editor is told so rather than finding out.
    _stock_a_leaf(client, admin, warehouse, product_id, colour_id, 4)
    stocked = client.get(f"{door}/{product_id}/variants", headers=admin).json()
    assert stocked["can_add_size"] is False
    assert "sanoq" in stocked["size_blocked_reason"]

    # And it is the same sentence the write endpoint refuses with.
    refused = client.post(
        f"{door}/{product_id}/variants",
        json={"kind": "size", "label": "M", "value": "M", "parent_id": colour_id},
        headers=admin,
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == stocked["size_blocked_reason"]

    # The movement against the colour also makes it undeletable, and says why.
    blocked = next(v for v in stocked["variants"] if v["id"] == colour_id)
    assert blocked["can_delete"] is False
    assert "harakat" in blocked["blocked_reason"]
    gone = client.delete(f"{door}/{product_id}/variants/{colour_id}", headers=admin)
    assert gone.status_code == 409
    assert gone.json()["detail"] == blocked["blocked_reason"]

    # A colour holding sizes is blocked for a different reason, and says that
    # one instead.
    parent_id, leaf_id = _card_with_a_colour(
        client, admin, "MB-GUARD-2", with_a_size=True
    )
    tree = client.get(f"{door}/{parent_id}/variants", headers=admin).json()
    colour_row = next(v for v in tree["variants"] if v["kind"] == "color")
    assert colour_row["can_delete"] is False
    assert "o'lcham" in colour_row["blocked_reason"]
    # Its size is a leaf with nothing against it, so that one may go.
    assert next(v for v in tree["variants"] if v["id"] == leaf_id)["can_delete"] is True
    assert not _stock_is_consistent()


# --------------------------------------------------------- paying the sellers


def _period(
    client: TestClient, admin: dict[str, str], *, starts: str, ends: str, label: str
) -> dict:
    made = client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": starts, "ends_on": ends, "label": label},
        headers=admin,
    )
    assert made.status_code == 201, made.text
    return made.json()


def _statement(
    client: TestClient, admin: dict[str, str], period_id: int, seller_id: int
) -> dict:
    """Generate the run and return this seller's account, with its lines."""
    made = client.post(
        f"{API}/staff/payouts/periods/{period_id}/generate", headers=admin
    )
    assert made.status_code == 200, made.text
    mine = next(row for row in made.json() if row["seller_id"] == seller_id)
    full = client.get(f"{API}/staff/payouts/statements/{mine['id']}", headers=admin)
    assert full.status_code == 200, full.text
    return full.json()


def _sell_and_deliver(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    warehouse: dict[str, str],
    *,
    seller_id: int,
    product_id: int,
    price: int,
    quantity: int = 1,
) -> dict:
    """One order for this seller's goods, carried all the way to the door.

    A sale only counts once it is delivered — a placed order may be called off
    and a cash order is not paid until the doorstep — so every one of these
    walks the whole flow.
    """
    with Session(engine) as session:
        leaves = [v.id for v in of.leaf_variants(session, product_id)]
    offer = client.post(
        f"{API}/staff/offers",
        json={
            "product_id": product_id,
            "price": price,
            "seller_id": seller_id,
            "variant_ids": leaves,
        },
        headers=admin,
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]

    supply = client.post(
        f"{API}/staff/supplies",
        json={
            "seller_id": seller_id,
            "lines": [
                {
                    "offer_id": offer_id,
                    **({"variant_id": leaves[0]} if leaves else {}),
                    "quantity": quantity + 2,
                }
            ],
        },
        headers=admin,
    )
    assert supply.status_code == 201, supply.text
    client.post(
        f"{API}/staff/supplies/{supply.json()['id']}/receive",
        json={
            "lines": [
                {
                    "line_id": supply.json()["lines"][0]["id"],
                    "received_quantity": quantity + 2,
                }
            ]
        },
        headers=warehouse,
    )

    client.delete(f"{API}/cart", headers=auth)
    # `_pick` names the leaf the way the apps do, and this card has exactly
    # one offer — the seller's — so that is the one the cart takes.
    added = client.post(
        f"{API}/cart/items", json=_pick(product_id, quantity), headers=auth
    )
    assert added.status_code == 201, added.text

    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    order = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert order.status_code == 201, order.text
    order = order.json()
    for target in ("packing", "shipped", "delivered"):
        moved = client.post(
            f"{API}/staff/orders/{order['id']}/status",
            json={"status": target},
            headers=operator,
        )
        assert moved.status_code == 200, moved.text
    return order


def _lines(statement: dict, kind: str) -> list[dict]:
    return [line for line in statement["lines"] if line["kind"] == kind]


def test_a_sellers_two_orders_add_up_to_one_account(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Nobody was being paid. Everything the arithmetic needed was captured on
    the order line and nothing added it up."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060001")
    seller_id, theirs = _linked_seller(staff, "Payout Bir", "+998900060002", commission=10)

    first_id, _ = _card_with_a_colour(client, admin, "MB-PAY-1", with_a_size=False)
    second_id, _ = _card_with_a_colour(client, admin, "MB-PAY-2", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=first_id, price=500_000,
    )
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=second_id, price=300_000, quantity=2,
    )

    # Its own window. Periods may not overlap — one sale falling into two
    # runs is the thing that guard exists for — and every test here shares
    # one database. A period's start date does not filter sales (see
    # `_sale_lines`: anything delivered by the closing day and not yet
    # settled belongs to it), so a far window still picks up today's sale.
    period = _period(
        client, admin, starts="2040-01-01", ends="2040-12-31", label="Sinov davri"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    # 500 000 + 2 × 300 000, and the commission is the rate on the line.
    assert statement["gross_sales"] == 1_100_000
    assert statement["commission"] == 110_000
    assert statement["seller_name"] == "Payout Bir"

    # The figure is the sum of its rows, the way the shelf is the sum of its
    # movements. A total that can drift from its own composition is the thing
    # this model exists to prevent.
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    assert (
        statement["payable"]
        == statement["gross_sales"]
        - statement["commission"]
        - statement["fulfilment"]
        - statement["refunds"]
        - statement["storage"]
        + statement["adjustments"]
    )

    # Every line names what it came from. "9 100 000" is a number to argue
    # with; this is an account to read.
    sales = _lines(statement, "sale")
    assert len(sales) == 2
    assert all(line["order_item_id"] for line in sales)
    assert all(line["title"].startswith("#") for line in sales)
    for line in _lines(statement, "commission"):
        assert "10%" in line["note"]
        assert line["order_item_id"]

    # The seller reads their own account, and only their own.
    theirs_view = client.get(f"{API}/staff/payouts/statements", headers=theirs)
    assert theirs_view.status_code == 200, theirs_view.text
    assert {row["seller_id"] for row in theirs_view.json()} == {seller_id}
    assert client.get(
        f"{API}/staff/payouts/statements/{statement['id']}", headers=theirs
    ).status_code == 200
    assert client.get(f"{API}/staff/payouts/periods", headers=theirs).status_code == 403
    assert not _stock_is_consistent()


def test_the_commission_is_the_rate_it_was_sold_at_not_todays(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A payout computed against today's rate would quietly restate what
    somebody was owed for something they sold last year."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060011")
    seller_id, _ = _linked_seller(staff, "Payout Ikki", "+998900060012", commission=8)
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-3", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=1_000_000,
    )

    past = _period(
        client, admin, starts="2019-01-01", ends="2019-12-31", label="Bo'sh"
    )
    # A period that closes before the sale happened sees nothing of it — not
    # the sale, and not a day of storage either.
    empty = _statement(client, admin, past["id"], seller_id)
    assert (empty["gross_sales"], empty["storage"], empty["payable"]) == (0, 0, 0)

    wide = _period(
        client, admin, starts="2041-01-01", ends="2041-12-31", label="Keng"
    )
    before = _statement(client, admin, wide["id"], seller_id)
    assert before["commission"] == 80_000

    # The contract is renegotiated upwards. What was already sold keeps the
    # rate it was sold at.
    changed = client.patch(
        f"{API}/staff/sellers/{seller_id}", json={"commission_percent": 25}, headers=admin
    )
    assert changed.status_code == 200, changed.text
    after = _statement(client, admin, wide["id"], seller_id)
    assert after["commission"] == 80_000, "the snapshot, not the seller row"
    assert "8%" in _lines(after, "commission")[0]["note"]
    assert not _stock_is_consistent()


def test_a_cheap_item_costs_more_to_handle_than_it_earns_in_commission(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The reason there are two fees at all.

    Five per cent of the catalogue's cheapest card is 1 950 so'm against a
    Tashkent delivery that costs many times that; five per cent of its dearest
    is 9 100 000 for carrying one small box the same distance. A single
    percentage is a loss at one end and an embarrassment at the other.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900060021")
    seller_id, _ = _linked_seller(staff, "Payout Uch", "+998900060022", commission=5)

    cheap_id, _ = _card_with_a_colour(client, admin, "MB-PAY-CHEAP", with_a_size=False)
    dear_id, _ = _card_with_a_colour(client, admin, "MB-PAY-DEAR", with_a_size=False)
    # Both light — a phone accessory and a watch weigh about the same, which
    # is exactly why the fee cannot follow the price.
    with Session(engine) as session:
        for product_id in (cheap_id, dear_id):
            row = session.get(Product, product_id)
            row.weight_grams = 300
            session.add(row)
        session.commit()

    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=cheap_id, price=39_000,
    )
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=dear_id, price=182_000_000,
    )

    period = _period(
        client, admin, starts="2042-01-01", ends="2042-12-31", label="Ikki haq"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    handling = {
        line["order_item_id"]: -line["amount"] for line in _lines(statement, "fulfilment")
    }
    commission = {
        line["order_item_id"]: -line["amount"] for line in _lines(statement, "commission")
    }
    sales = {line["order_item_id"]: line["amount"] for line in _lines(statement, "sale")}

    cheap = next(item for item, gross in sales.items() if gross == 39_000)
    dear = next(item for item, gross in sales.items() if gross == 182_000_000)

    # The whole point, in one assertion: on the cheap card the handling fee is
    # the larger of the two, and on the dear one it is a rounding error.
    assert handling[cheap] > commission[cheap], (handling[cheap], commission[cheap])
    assert commission[cheap] == 1_950
    assert handling[dear] < commission[dear] // 1000

    # Same weight, same handling fee — it does not follow the price.
    assert handling[cheap] == handling[dear]

    # And it is visible in the statement rather than buried in a net figure.
    assert statement["fulfilment"] == handling[cheap] + handling[dear]
    assert "yig'ish va yetkazish" in _lines(statement, "fulfilment")[0]["note"]
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    assert not _stock_is_consistent()


def test_a_refund_comes_off_the_account_and_gives_the_commission_back(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A refunded sale was never a sale, so keeping our cut of it would be
    charging for something that did not happen. The van still came, though, so
    the handling fee is not given back."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060031")
    seller_id, _ = _linked_seller(staff, "Payout To'rt", "+998900060032", commission=10)
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-4", with_a_size=False)
    order = _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=400_000,
    )

    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "O'lchami to'g'ri kelmadi"},
        headers=auth,
    ).json()
    client.post(f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator)
    refunded = client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True, "note": "Butun holida qaytdi"},
        headers=operator,
    )
    assert refunded.status_code == 200, refunded.text

    period = _period(
        client, admin, starts="2043-01-01", ends="2043-12-31", label="Qaytarish"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    # Sold, and unsold. The refund deduction is the goods less the commission
    # we handed back — exactly what the seller had received for it.
    assert statement["gross_sales"] == 400_000
    assert statement["commission"] == 40_000
    assert statement["refunds"] == 360_000

    back = _lines(statement, "refund")
    assert back and all(line["return_request_id"] == request["id"] for line in back)
    assert all(line["amount"] == -400_000 for line in back)
    given = _lines(statement, "refund_commission")
    assert [line["amount"] for line in given] == [40_000]
    assert "komissiya olinmaydi" in given[0]["note"]

    # The handling fee stays deducted: it was really spent.
    assert statement["fulfilment"] > 0
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    # Nothing left of the sale but the cost of having shipped it.
    assert statement["payable"] == -statement["fulfilment"] - statement["storage"]
    assert not _stock_is_consistent()


def test_a_refund_after_the_period_closed_lands_in_the_next_one(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A seller who reads what they are owed and is shown a different number
    next week has been told the first number was provisional — which makes
    every number provisional."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060041")
    seller_id, _ = _linked_seller(staff, "Payout Besh", "+998900060042", commission=10)
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-5", with_a_size=False)
    order = _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=700_000,
    )

    first = _period(
        client, admin, starts="2044-01-01", ends="2044-12-31", label="Birinchi"
    )
    before = _statement(client, admin, first["id"], seller_id)
    assert before["gross_sales"] == 700_000
    assert before["refunds"] == 0
    settled = before["payable"]

    closed = client.post(
        f"{API}/staff/payouts/periods/{first['id']}/close", headers=admin
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    # The refund arrives afterwards.
    request = client.post(
        f"{API}/orders/{order['id']}/return",
        json={"reason": "Kechikkan qaytarish"},
        headers=auth,
    ).json()
    client.post(f"{API}/staff/returns/{request['id']}/approve", json={}, headers=operator)
    client.post(
        f"{API}/staff/returns/{request['id']}/refund",
        json={"restock": True, "note": "Davr yopilgandan keyin"},
        headers=operator,
    )

    # The closed account is untouched — the same figure the seller read.
    frozen = client.get(
        f"{API}/staff/payouts/statements/{before['id']}", headers=admin
    ).json()
    assert frozen["payable"] == settled
    assert frozen["refunds"] == 0
    assert frozen["gross_sales"] == 700_000

    # A closed period will not be regenerated, and refuses to be reclosed.
    assert client.post(
        f"{API}/staff/payouts/periods/{first['id']}/generate", headers=admin
    ).status_code == 409
    assert client.post(
        f"{API}/staff/payouts/periods/{first['id']}/close", headers=admin
    ).status_code == 409

    # It lands in the next one instead, and the sale is not counted twice.
    second = _period(
        client, admin, starts="2045-01-01", ends="2045-12-31", label="Ikkinchi"
    )
    later = _statement(client, admin, second["id"], seller_id)
    assert later["refunds"] == 630_000, later
    assert later["gross_sales"] == 0, "the sale was settled in the closed period"
    assert later["payable"] == sum(line["amount"] for line in later["lines"])
    assert later["payable"] < 0, "a period of refunds alone is a debt, not a zero"
    assert not _stock_is_consistent()


def test_storage_is_charged_per_unit_day_and_surcharged_when_nothing_moves(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The only mechanism here that empties a shelf. Without a standing cost
    the warehouse is a free storage unit, and the way to use one is to send
    everything and let somebody else hold it."""
    from datetime import timedelta

    from app import settlement as settle
    from app.models import StockMovement

    warehouse = staff(UserRole.WAREHOUSE, "+998900060051")
    seller_id, _ = _linked_seller(staff, "Payout Olti", "+998900060052")
    product_id, leaf_id = _card_with_a_colour(
        client, admin, "MB-PAY-6", with_a_size=False
    )
    _stock_a_leaf(client, admin, warehouse, product_id, leaf_id, 4)

    with Session(engine) as session:
        offer = session.exec(
            select(Offer).where(
                Offer.product_id == product_id, Offer.seller_id != seller_id
            )
        ).first()
        # Hand the stocked offer to our seller so the storage lands on them.
        offer.seller_id = seller_id
        session.add(offer)
        # And date the intake far enough back that it counts as stale.
        movements = session.exec(
            select(StockMovement).where(StockMovement.offer_id == offer.id)
        ).all()
        old = utcnow() - timedelta(days=settle.STALE_AFTER_DAYS + 40)
        for movement in movements:
            movement.created_at = old
            session.add(movement)
        session.commit()
        offer_id = offer.id

    starts = (utcnow() - timedelta(days=9)).date()
    ends = (utcnow() - timedelta(days=1)).date()
    period = _period(
        client, admin, starts=str(starts), ends=str(ends), label="Saqlash"
    )
    statement = _statement(client, admin, period["id"], seller_id)

    rows = [line for line in _lines(statement, "storage") if line["offer_id"] == offer_id]
    assert rows, statement["lines"]
    row = rows[0]
    days = (ends - starts).days + 1
    # The rate is the weight band's, not a flat number: a washing machine and
    # a pair of earphones do not occupy the same warehouse.
    with Session(engine) as session:
        rate = settle.storage_rate(session, session.get(Product, product_id))
    expected = 4 * days * rate * settle.STALE_MULTIPLIER
    assert -row["amount"] == expected, (row, expected)

    # The sum in words, so a seller can check it rather than only dispute it.
    assert f"{4 * days} dona-kun" in row["note"]
    assert f"{settle.STALE_MULTIPLIER}×" in row["note"]
    assert "harakatsiz" in row["note"]
    assert statement["storage"] >= expected
    assert statement["payable"] == sum(line["amount"] for line in statement["lines"])
    assert not _stock_is_consistent()


def test_a_payout_is_marked_paid_once_with_a_date_and_a_reference(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Two transfers against one account is money gone that nobody notices
    until the seller who was not paid rings up."""
    warehouse = staff(UserRole.WAREHOUSE, "+998900060061")
    seller_id, theirs = _linked_seller(staff, "Payout Yetti", "+998900060062")
    product_id, _ = _card_with_a_colour(client, admin, "MB-PAY-7", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=900_000,
    )

    period = _period(
        client, admin, starts="2046-01-01", ends="2046-12-31", label="To'lov"
    )
    statement = _statement(client, admin, period["id"], seller_id)
    door = f"{API}/staff/payouts/statements/{statement['id']}"
    body = {"method": "bank o'tkazmasi", "reference": "TR-99001", "note": "Oylik"}

    # An open account cannot be paid: the figure is still being recomputed.
    assert client.post(f"{door}/pay", json=body, headers=admin).status_code == 409

    # A correction is the one line a person writes, so it must explain itself.
    assert client.post(
        f"{door}/adjust", json={"amount": -50_000, "note": ""}, headers=admin
    ).status_code == 422
    fixed = client.post(
        f"{door}/adjust",
        json={"amount": -50_000, "note": "Sinov uchun tuzatish"},
        headers=admin,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["adjustments"] == -50_000
    assert fixed.json()["payable"] == sum(
        line["amount"] for line in fixed.json()["lines"]
    )

    client.post(f"{API}/staff/payouts/periods/{period['id']}/close", headers=admin)
    # Closed: no more corrections here — one goes in the next period, where it
    # can be seen.
    assert client.post(
        f"{door}/adjust", json={"amount": -1, "note": "kech"}, headers=admin
    ).status_code == 409

    paid = client.post(f"{door}/pay", json=body, headers=admin)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["payment_reference"] == "TR-99001"
    assert paid.json()["paid_at"]

    # Once, and only once.
    assert client.post(f"{door}/pay", json=body, headers=admin).status_code == 409
    # And not by the seller being paid.
    assert client.post(f"{door}/pay", json=body, headers=theirs).status_code == 403
    assert client.post(f"{door}/pay", json=body, headers=operator).status_code == 403

    # Money leaving is logged with a name against it.
    rows = _audit_rows("settlement.pay", statement["id"])
    assert rows and rows[-1].actor_role is UserRole.ADMIN
    assert "TR-99001" in rows[-1].note
    assert _audit_rows("settlement.adjust", statement["id"])
    assert not _stock_is_consistent()


def test_two_periods_cannot_cover_the_same_day(
    client: TestClient, admin: dict[str, str]
) -> None:
    """One sale falling into two runs would either be paid twice or leave
    nobody able to say which run it belonged to."""
    _period(client, admin, starts="2031-01-01", ends="2031-01-31", label="Yanvar")
    clash = client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": "2031-01-15", "ends_on": "2031-02-15"},
        headers=admin,
    )
    assert clash.status_code == 409
    assert "davr" in clash.json()["detail"].lower()

    # Backwards is refused too.
    assert client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": "2031-03-31", "ends_on": "2031-03-01"},
        headers=admin,
    ).status_code == 400

    # The month after it is fine.
    after = _period(
        client, admin, starts="2031-02-01", ends="2031-02-28", label="Fevral"
    )
    assert after["status"] == "open"
    assert client.post(
        f"{API}/staff/payouts/periods",
        json={"starts_on": "2032-01-01", "ends_on": "2032-01-31"},
    ).status_code == 401


def test_the_handling_tariff_is_readable_by_the_people_charged_it(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A fee somebody is charged and cannot look up is a fee they can only
    dispute."""
    _, theirs = _linked_seller(staff, "Payout Sakkiz", "+998900060072")
    bands = client.get(f"{API}/staff/payouts/tariffs", headers=theirs)
    assert bands.status_code == 200, bands.text
    rows = bands.json()
    assert len(rows) >= 2
    # Read top to bottom as "up to 500 g", "up to 2 kg", so the band a parcel
    # falls into is the first that covers it.
    assert rows == sorted(rows, key=lambda r: r["max_grams"])
    assert all(r["fee"] > 0 and r["storage_per_day"] > 0 and r["label"] for r in rows)
    # Both rates climb with the band, because both follow how big the thing is.
    assert [r["fee"] for r in rows] == sorted(r["fee"] for r in rows)
    assert [r["storage_per_day"] for r in rows] == sorted(
        r["storage_per_day"] for r in rows
    )
    assert client.get(f"{API}/staff/payouts/tariffs", headers=admin).status_code == 200
    assert client.get(f"{API}/staff/payouts/tariffs", headers=auth).status_code == 403


# --------------------------------------------------------- the seller's own way in


def test_a_seller_can_see_which_shop_they_are_and_nobody_elses(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """`/staff/me` answers with the user — a phone number and a role — and says
    nothing about the shop behind it. So the cabinet greeted people by phone
    number, and somebody just taken on could not confirm they were linked to
    the right shop, which is the first thing they would check."""
    mine_id, mine = _linked_seller(staff, "Katalog Bir", "+998900080001", commission=12)
    other_id, other = _linked_seller(staff, "Katalog Ikki", "+998900080002", commission=7)

    shop = client.get(f"{API}/staff/sellers/me", headers=mine)
    assert shop.status_code == 200, shop.text
    body = shop.json()
    assert (body["id"], body["name"]) == (mine_id, "Katalog Bir")
    # A term of their own contract, and the figure every statement is computed
    # from — a seller who cannot read it cannot check a payout.
    assert body["commission_percent"] == 12
    assert body["active"] is True
    assert body["created_at"]

    # The other seller gets their own row, never this one.
    theirs = client.get(f"{API}/staff/sellers/me", headers=other).json()
    assert (theirs["id"], theirs["name"]) == (other_id, "Katalog Ikki")
    assert theirs["commission_percent"] == 7

    # And no door to anybody else's: the admin's list stays the admin's.
    assert client.get(f"{API}/staff/sellers/{other_id}", headers=mine).status_code == 403
    assert client.get(f"{API}/staff/sellers", headers=mine).status_code == 403
    assert client.get(f"{API}/staff/sellers/me", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/sellers/me").status_code == 401

    # An admin has no shop of their own and is told so rather than guessed at.
    refused = client.get(f"{API}/staff/sellers/me", headers=admin)
    assert refused.status_code == 400
    assert "do'kon" in refused.json()["detail"]

    # Linking is what stamps the date, so it is there for anybody linked
    # through the front door.
    phone = "+998900080003"
    sign_in_needed = client.post(
        f"{API}/staff/sellers",
        json={"name": "Katalog Uch", "phone": "+998781119977"},
        headers=admin,
    )
    assert sign_in_needed.status_code == 201, sign_in_needed.text
    third_id = sign_in_needed.json()["id"]
    fresh = staff(UserRole.CUSTOMER, phone)
    linked = client.patch(
        f"{API}/staff/sellers/{third_id}", json={"user_phone": phone}, headers=admin
    )
    assert linked.status_code == 200, linked.text
    third = client.get(f"{API}/staff/sellers/me", headers=fresh).json()
    assert third["name"] == "Katalog Uch"
    assert third["linked_at"], "the moment the account was pointed at the shop"
    assert third["offer_count"] == 0


def test_the_sellers_catalogue_shows_only_what_is_in_the_shop(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A draft, a proposal in moderation, a refused card and a withdrawn one
    are somebody else's unfinished work. Pricing one would be pricing
    something that is not in the shop and may never be."""
    _, mine = _linked_seller(staff, "Katalog To'rt", "+998900080011")
    listing = client.get(f"{API}/categories").json()

    made: dict[str, int] = {}
    for sku, title in (("SINOV-BROWSE-DRAFT", "Qoralama tovar"),
                       ("SINOV-BROWSE-LIVE", "Sotuvdagi tovar")):
        card = client.post(
            f"{API}/staff/catalog/products",
            json={
                "sku": sku,
                "title": title,
                "category_slug": listing[0]["slug"],
                "price": 250_000,
            },
            headers=admin,
        )
        assert card.status_code == 201, card.text
        made[sku] = card.json()["id"]

    client.post(
        f"{API}/staff/catalog/products/{made['SINOV-BROWSE-LIVE']}/status",
        json={"status": "published"},
        headers=admin,
    )

    page = client.get(
        f"{API}/staff/catalog/browse", params={"q": "SINOV-BROWSE"}, headers=mine
    )
    assert page.status_code == 200, page.text
    ids = {row["id"] for row in page.json()["items"]}
    assert made["SINOV-BROWSE-LIVE"] in ids
    assert made["SINOV-BROWSE-DRAFT"] not in ids, "a draft is not for sale"

    # Reading the draft directly is a 404 too, not a 403: it is not a card
    # this seller is being refused, it is not in the shop.
    assert client.get(
        f"{API}/staff/catalog/browse/{made['SINOV-BROWSE-DRAFT']}", headers=mine
    ).status_code == 404

    # Withdrawn again, and it leaves.
    client.post(
        f"{API}/staff/catalog/products/{made['SINOV-BROWSE-LIVE']}/status",
        json={"status": "archived", "reason": "sinov"},
        headers=admin,
    )
    after = client.get(
        f"{API}/staff/catalog/browse", params={"q": "SINOV-BROWSE"}, headers=mine
    ).json()
    assert after["items"] == []

    # It is a card list, not the admin's editing shape: what a seller needs to
    # recognise a product, and no moderation note.
    live = client.get(f"{API}/staff/catalog/browse", headers=mine).json()["items"]
    assert live, "the seeded catalogue is published"
    assert set(live[0]) >= {"title", "image_url", "offer_count", "mine", "price"}
    assert "moderation_note" not in live[0]
    assert "status" not in live[0]

    assert client.get(f"{API}/staff/catalog/browse").status_code == 401


def test_a_seller_reads_the_leaves_then_offers_the_whole_card(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The founding move of a marketplace, end to end: somebody arrives, finds
    a card, prices it, sends goods, and the shop shows their price.

    Until now the middle of that was impossible. An offer has to name every
    leaf — a rule enforced with a 422 — and nothing told a seller what the
    leaves were.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900080021")
    seller_id, mine = _linked_seller(staff, "Katalog Besh", "+998900080022")
    product_id, leaf = _card_with_a_colour(client, admin, "MB-BROWSE-1", with_a_size=True)
    # A second size, so "name every leaf" is a rule with something to catch:
    # a card with one leaf cannot be partially named.
    with Session(engine) as session:
        colour_id = session.get(ProductVariant, leaf).parent_id
    assert client.post(
        f"{API}/staff/catalog/products/{product_id}/variants",
        json={"kind": "size", "label": "XL", "value": "XL", "parent_id": colour_id},
        headers=admin,
    ).status_code == 201

    card = client.get(f"{API}/staff/catalog/browse/{product_id}", headers=mine)
    assert card.status_code == 200, card.text
    body = card.json()
    assert body["mine"] is False and body["my_offer_id"] is None

    # The tree, with the rows an offer must name marked as such.
    leaves = [v for v in body["variants"] if v["is_leaf"]]
    assert len(leaves) == 2, body["variants"]
    assert {v["kind"] for v in leaves} == {"size"}, "sizes are the leaves here"
    assert body["leaf_ids"] == [v["id"] for v in leaves]
    # The colour is in the tree and is not a leaf: its count is rolled up.
    assert any(v["kind"] == "color" and not v["is_leaf"] for v in body["variants"])

    # Naming only some of them is still refused — the rule has not moved, and
    # this is the 422 a seller used to hit with no way of knowing why.
    partial = client.post(
        f"{API}/staff/offers",
        json={"product_id": product_id, "price": 200_000, "variant_ids": [leaves[0]["id"]]},
        headers=mine,
    )
    assert partial.status_code == 422, partial.text
    assert leaves[1]["label"] in partial.json()["detail"], "it names what is missing"

    # A variant of some other card is refused too.
    assert client.post(
        f"{API}/staff/offers",
        json={"product_id": product_id, "price": 200_000, "variant_ids": [999_999]},
        headers=mine,
    ).status_code in (400, 422)

    offer = client.post(
        f"{API}/staff/offers",
        json={
            "product_id": product_id,
            "price": 180_000,
            "old_price": 240_000,
            "variant_ids": body["leaf_ids"],
        },
        headers=mine,
    )
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]
    assert offer.json()["seller"]["id"] == seller_id
    # Nothing on the shelf until the warehouse books something in, so a new
    # offer does not win the card the moment it is made.
    assert offer.json()["stock_left"] == 0

    # The browse list now says it is theirs, so a screen can stop offering a
    # button whose only answer is a 409.
    again = client.get(f"{API}/staff/catalog/browse/{product_id}", headers=mine).json()
    assert again["mine"] is True
    assert (again["my_offer_id"], again["my_price"]) == (offer_id, 180_000)

    # Goods arrive.
    leaf_id = body["leaf_ids"][0]
    supply = client.post(
        f"{API}/staff/supplies",
        json={"lines": [{"offer_id": offer_id, "variant_id": leaf_id, "quantity": 6}]},
        headers=mine,
    )
    assert supply.status_code == 201, supply.text
    received = client.post(
        f"{API}/staff/supplies/{supply.json()['id']}/receive",
        json={
            "lines": [
                {"line_id": supply.json()["lines"][0]["id"], "received_quantity": 6}
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text

    # And the shop card carries their price, to a shopper who is nobody.
    page = client.get(f"{API}/products/{product_id}")
    assert page.status_code == 200
    assert page.json()["price"] == 180_000
    assert page.json()["in_stock"] is True
    sellers = client.get(f"{API}/products/{product_id}/offers").json()
    assert [o["seller"]["name"] for o in sellers if o["is_winner"]] == ["Katalog Besh"]

    # Which is exactly why the browse list does not hide a competitor's price:
    # it is already public to anybody, token or not.
    assert client.get(f"{API}/products/{product_id}/offers", headers=auth).status_code == 200
    assert not _stock_is_consistent()


def test_one_seller_gets_one_offer_per_card(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Two offers from one seller on one card is two prices for the same goods
    from the same person — the cheaper would always win and the other would
    sit there confusing the shelf."""
    _, mine = _linked_seller(staff, "Katalog Olti", "+998900080031")
    other_id, other = _linked_seller(staff, "Katalog Yetti", "+998900080032")
    product_id, _ = _card_with_a_colour(client, admin, "MB-BROWSE-2", with_a_size=False)

    def body(price: int, **extra: object) -> dict:
        leaves = client.get(
            f"{API}/staff/catalog/browse/{product_id}", headers=mine
        ).json()["leaf_ids"]
        return {"product_id": product_id, "price": price, "variant_ids": leaves, **extra}

    first = client.post(f"{API}/staff/offers", json=body(300_000), headers=mine)
    assert first.status_code == 201, first.text

    second = client.post(f"{API}/staff/offers", json=body(250_000), headers=mine)
    assert second.status_code == 409, second.text
    assert "taklif" in second.json()["detail"]
    # Changing the price is how a seller lowers it, and that door works.
    assert client.patch(
        f"{API}/staff/offers/{first.json()['id']}", json={"price": 250_000}, headers=mine
    ).status_code == 200

    # A different seller on the same card is the whole point of the model.
    theirs = client.post(f"{API}/staff/offers", json=body(240_000), headers=other)
    assert theirs.status_code == 201, theirs.text

    # And offering as somebody else is refused rather than quietly corrected.
    assert client.post(
        f"{API}/staff/offers", json=body(1_000, seller_id=other_id), headers=mine
    ).status_code == 403

    # Each seller reads their own offers and only their own.
    def sellers_on(headers: dict[str, str]) -> set[str]:
        rows = client.get(f"{API}/staff/offers", headers=headers).json()
        return {row["seller"]["name"] for row in rows}

    assert sellers_on(mine) == {"Katalog Olti"}
    assert sellers_on(other) == {"Katalog Yetti"}

    # The browse list tells each of them the truth about the same card: the
    # public offer count, and their own price.
    seen = client.get(f"{API}/staff/catalog/browse/{product_id}", headers=mine).json()
    assert seen["offer_count"] == 2
    assert seen["my_price"] == 250_000
    theirs_view = client.get(
        f"{API}/staff/catalog/browse/{product_id}", headers=other
    ).json()
    assert theirs_view["offer_count"] == 2
    assert theirs_view["my_price"] == 240_000


# --------------------------------------------------------- the last mile


def _courier(
    staff: Callable[[UserRole, str], dict[str, str]], phone: str
) -> tuple[int, dict[str, str]]:
    headers = staff(UserRole.COURIER, phone)
    with Session(engine) as session:
        return session.exec(select(User).where(User.phone == phone)).one().id, headers


def _key(name: str) -> dict[str, str]:
    """One idempotency key, the way the app makes one per queued action."""
    return {"Idempotency-Key": f"test-{name}"}


def _on_a_round(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    courier_id: int,
    *,
    cash: bool,
    sequence: int = 1,
) -> dict:
    """An order shipped and assigned, ready to be knocked on."""
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(
        f"{API}/products", params={"sort": "price_asc"}
    ).json()["items"][0]
    client.post(f"{API}/cart/items", json=_pick(product["id"]), headers=auth)
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    created = client.post(
        f"{API}/orders",
        json={
            "address_id": address["id"],
            **({"payment_method": "cash"} if cash else {}),
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    order = created.json()

    assigned = client.post(
        f"{API}/staff/orders/{order['id']}/courier",
        json={"courier_id": courier_id, "sequence": sequence},
        headers=operator,
    )
    assert assigned.status_code == 200, assigned.text
    for target in ("packing", "shipped"):
        moved = client.post(
            f"{API}/staff/orders/{order['id']}/status",
            json={"status": target},
            headers=operator,
        )
        assert moved.status_code == 200, moved.text
    return order


def test_an_operator_plans_the_round_and_a_courier_reads_only_their_own(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """`UserRole.COURIER` existed from the first stage and no router ever asked
    about it — so an order did not record who was carrying it and a courier had
    no list of their own. The two gaps were the same gap."""
    mine_id, mine = _courier(staff, "+998900090001")
    other_id, other = _courier(staff, "+998900090002")

    listed = client.get(f"{API}/staff/couriers", headers=operator)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} >= {mine_id, other_id}
    assert all(row["role"] == "courier" for row in listed.json())

    order = _on_a_round(client, auth, operator, mine_id, cash=False, sequence=3)

    round_ = client.get(f"{API}/courier/orders", headers=mine)
    assert round_.status_code == 200, round_.text
    stop = next(row for row in round_.json() if row["id"] == order["id"])
    # What somebody at a door needs, and not the catalogue detail the
    # customer's own shape carries.
    assert stop["sequence"] == 3
    assert stop["recipient_phone"] and stop["address_line"]
    assert stop["attempts"] == 0 and stop["last_failure"] == ""

    # And the operator's own queue says who is carrying it.
    #
    # `Order.courier_id` was readable only through the courier's endpoints, so
    # the panel whose job is planning the round could not see the round: an
    # unassigned order looked no different from an assigned one, and the
    # backoffice had no way to show either. Which is why nothing in it called
    # `POST /staff/orders/{id}/courier` at all, and orders reached `shipped`
    # belonging to nobody — the courier's list came back empty and their
    # delivery was refused as not theirs.
    queue = client.get(f"{API}/staff/orders", headers=operator, params={"page_size": 100})
    assert queue.status_code == 200, queue.text
    rows = {row["id"]: row for row in queue.json()["items"]}
    assert rows[order["id"]]["courier_id"] == mine_id
    assert rows[order["id"]]["courier_sequence"] == 3
    # The name, because a row is read by a person and an id is not a person.
    listed_names = {
        row["id"]: row["full_name"]
        for row in client.get(f"{API}/staff/couriers", headers=operator).json()
    }
    assert rows[order["id"]]["courier_name"] == listed_names[mine_id]

    # An order nobody is carrying says so rather than naming somebody.
    unassigned = [row for row in rows.values() if row["courier_id"] is None]
    assert all(row["courier_name"] == "" for row in unassigned)
    # A card order is already paid: asking for money again is the mistake
    # `cash_due` exists to prevent.
    assert stop["cash_due"] == 0

    # The other courier's round does not contain it, and reaching for it is a
    # refusal rather than a pretence that it is missing.
    assert order["id"] not in [row["id"] for row in client.get(
        f"{API}/courier/orders", headers=other
    ).json()]
    poached = client.post(
        f"{API}/courier/orders/{order['id']}/failed",
        json={"reason": "boshqa kuryerning buyurtmasi"},
        headers={**other, **_key("poach")},
    )
    assert poached.status_code == 403, poached.text

    # Nobody else's door either.
    assert client.get(f"{API}/courier/orders", headers=operator).status_code == 403
    assert client.get(f"{API}/courier/orders", headers=admin).status_code == 403
    assert client.get(f"{API}/courier/orders").status_code == 401

    # A courier is not somebody an operator can invent.
    assert client.post(
        f"{API}/staff/orders/{order['id']}/courier",
        json={"courier_id": 999_999},
        headers=operator,
    ).status_code == 404
    with Session(engine) as session:
        not_a_courier = session.exec(
            select(User).where(User.phone == "+998901234567")
        ).one().id
    assert client.post(
        f"{API}/staff/orders/{order['id']}/courier",
        json={"courier_id": not_a_courier},
        headers=operator,
    ).status_code == 404

    # And a courier does not assign themselves.
    assert client.post(
        f"{API}/staff/orders/{order['id']}/courier",
        json={"courier_id": other_id},
        headers=mine,
    ).status_code == 403

    rows = _audit_rows("order.courier", order["id"])
    assert rows and str(rows[-1].new_value) == str(mine_id)


def test_a_retried_delivery_is_not_a_second_sale(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The sentence the whole idempotency design exists for.

    The app queues writes it cannot send and retries them, so "delivered,
    N so'm at the door" arrives twice as a matter of course. Without a key
    that is a second sale off the shelf and a second N on the shift, and
    nobody notices until the courier is accused of being short.
    """
    courier_id, courier = _courier(staff, "+998900090011")
    order = _on_a_round(client, auth, operator, courier_id, cash=True)

    started = client.post(
        f"{API}/courier/shifts", headers={**courier, **_key("shift-1")}
    )
    assert started.status_code == 201, started.text
    shift_id = started.json()["id"]
    assert started.json()["cash_expected"] == 0

    stop = next(
        row
        for row in client.get(f"{API}/courier/orders", headers=courier).json()
        if row["id"] == order["id"]
    )
    owed = stop["cash_due"]
    assert owed == order["total"] > 0, "cash at the door"

    body = {"recipient_name": "Aziz Toshmatov", "cash_collected": owed}
    door = f"{API}/courier/orders/{order['id']}/deliver"

    first = client.post(door, json=body, headers={**courier, **_key("deliver-1")})
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "delivered"

    # The same request again, with the same key: the answer, not the act.
    again = client.post(door, json=body, headers={**courier, **_key("deliver-1")})
    assert again.status_code == 200, again.text
    assert again.json() == first.json(), "the stored answer, replayed"

    # Sent a third time for good measure, because the app retries until it
    # gets an answer and does not count how many times it tried.
    assert client.post(
        door, json=body, headers={**courier, **_key("deliver-1")}
    ).json() == first.json()

    # The goods left the shelf once — read off the ledger rather than off the
    # cached figure, which is where the claim actually lives. A cash order's
    # goods were *held* from the moment it was placed, so the cache had
    # already dropped; what delivery does is turn the hold into a sale, and a
    # retry that ran twice would leave two sale movements against one order.
    with Session(engine) as session:
        sold = session.exec(
            select(StockMovement).where(
                StockMovement.order_id == order["id"],
                StockMovement.kind == StockMovementKind.SALE,
            )
        ).all()
    assert len(sold) == 1, [(m.id, m.quantity, m.reason) for m in sold]
    assert sold[0].quantity == -1, "signed: what went out"

    # And the cash landed once.
    shift = client.get(f"{API}/courier/shifts/current", headers=courier).json()
    assert shift["id"] == shift_id
    assert shift["cash_expected"] == owed
    assert shift["orders_delivered"] == 1
    assert len(shift["attempts"]) == 1, "one door, one row"
    assert shift["attempts"][0]["cash_collected"] == owed

    # A second attempt on a delivered order is refused rather than replayed:
    # a new key means a new request, and the order has moved on.
    assert client.post(
        door, json=body, headers={**courier, **_key("deliver-2")}
    ).status_code == 409
    assert not _stock_is_consistent()


def test_the_cash_on_a_shift_is_counted_once_however_often_it_is_sent(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Three doors, one of them sent twice, and the shift adds up to three."""
    courier_id, courier = _courier(staff, "+998900090021")
    started = client.post(
        f"{API}/courier/shifts", headers={**courier, **_key("shift-2")}
    )
    assert started.status_code == 201, started.text
    shift_id = started.json()["id"]

    # Starting again is not an error: the app is probably retrying, and the
    # answer to "start my shift" when it is started is the shift.
    twice = client.post(f"{API}/courier/shifts", headers={**courier, **_key("shift-2")})
    assert twice.status_code == 201
    assert twice.json()["id"] == shift_id
    fresh_key = client.post(
        f"{API}/courier/shifts", headers={**courier, **_key("shift-2b")}
    )
    assert fresh_key.json()["id"] == shift_id, "one open shift at a time"

    owed_total = 0
    for index in range(3):
        order = _on_a_round(
            client, auth, operator, courier_id, cash=True, sequence=index + 1
        )
        stop = next(
            row
            for row in client.get(f"{API}/courier/orders", headers=courier).json()
            if row["id"] == order["id"]
        )
        owed = stop["cash_due"]
        owed_total += owed
        door = f"{API}/courier/orders/{order['id']}/deliver"
        body = {"recipient_name": f"Mijoz {index}", "cash_collected": owed}
        assert client.post(
            door, json=body, headers={**courier, **_key(f"d{index}")}
        ).status_code == 200
        if index == 1:
            # The retry the network caused.
            assert client.post(
                door, json=body, headers={**courier, **_key(f"d{index}")}
            ).status_code == 200

    shift = client.get(f"{API}/courier/shifts/current", headers=courier).json()
    assert shift["cash_expected"] == owed_total
    assert shift["orders_delivered"] == 3, "not four"
    # The total is followable: one row per door, and they sum to it.
    assert len(shift["attempts"]) == 3
    assert sum(a["cash_collected"] for a in shift["attempts"]) == owed_total

    # Handing it over, one note short.
    closed = client.post(
        f"{API}/courier/shifts/{shift_id}/close",
        json={"cash_declared": owed_total - 50_000, "note": "bittasi yo'q"},
        headers={**courier, **_key("close-2")},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"
    assert closed.json()["cash_expected"] == owed_total
    assert closed.json()["cash_declared"] == owed_total - 50_000
    # Nothing counted yet, so no difference is claimed.
    assert closed.json()["cash_counted"] is None
    assert closed.json()["difference"] is None

    # Closing twice does not close it twice.
    assert client.post(
        f"{API}/courier/shifts/{shift_id}/close",
        json={"cash_declared": owed_total - 50_000, "note": "bittasi yo'q"},
        headers={**courier, **_key("close-2")},
    ).json() == closed.json()
    # And a fresh key on a closed shift is refused rather than replayed.
    assert client.post(
        f"{API}/courier/shifts/{shift_id}/close",
        json={"cash_declared": 1},
        headers={**courier, **_key("close-2b")},
    ).status_code == 409

    # The office counts, and the gap is a fact rather than an argument.
    counted = client.post(
        f"{API}/staff/shifts/{shift_id}/count",
        json={"cash_counted": owed_total - 50_000},
        headers=operator,
    )
    assert counted.status_code == 200, counted.text
    assert counted.json()["cash_counted"] == owed_total - 50_000
    assert counted.json()["difference"] == -50_000, "counted against the doors"
    assert client.post(
        f"{API}/staff/shifts/{shift_id}/count",
        json={"cash_counted": owed_total},
        headers=operator,
    ).status_code == 409, "counted once"

    rows = _audit_rows("shift.count", shift_id)
    assert rows and "farq" in rows[-1].note
    assert _audit_rows("shift.close", shift_id)
    assert not _stock_is_consistent()


def test_a_key_may_not_be_reused_for_a_different_request(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The same key carrying a different body is a bug in the client, not a
    retry. Replaying the first answer would hide it and lose the second
    request entirely."""
    courier_id, courier = _courier(staff, "+998900090031")
    client.post(f"{API}/courier/shifts", headers={**courier, **_key("shift-3")})
    order = _on_a_round(client, auth, operator, courier_id, cash=False)
    door = f"{API}/courier/orders/{order['id']}/failed"

    assert client.post(
        door, json={"reason": "eshikni ochmadi"}, headers={**courier, **_key("f1")}
    ).status_code == 200

    clash = client.post(
        door, json={"reason": "telefon o'chirilgan"}, headers={**courier, **_key("f1")}
    )
    assert clash.status_code == 409, clash.text
    assert "kalit" in clash.json()["detail"]

    # A missing key is refused too: an optional key is a key some client
    # forgets, and the failure is silent and financial.
    assert client.post(door, json={"reason": "yana"}, headers=courier).status_code == 422

    # Two couriers may use the same key without colliding.
    other_id, other = _courier(staff, "+998900090032")
    client.post(f"{API}/courier/shifts", headers={**other, **_key("shift-3")})
    theirs = _on_a_round(client, auth, operator, other_id, cash=False)
    assert client.post(
        f"{API}/courier/orders/{theirs['id']}/failed",
        json={"reason": "manzil topilmadi"},
        headers={**other, **_key("f1")},
    ).status_code == 200


def test_a_delivery_needs_a_name_and_the_photo_is_optional(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The decision, and its reason.

    The name is required: one field a courier can always fill in while
    standing in front of the person who took the goods, and the answer to "I
    never received it". The photo is not: an upload needs signal, and
    requiring one would stop a courier in a basement finishing a delivery they
    have already made — which is the exact situation the offline design is for.
    """
    courier_id, courier = _courier(staff, "+998900090041")
    client.post(f"{API}/courier/shifts", headers={**courier, **_key("shift-4")})
    order = _on_a_round(client, auth, operator, courier_id, cash=False)
    door = f"{API}/courier/orders/{order['id']}/deliver"

    nameless = client.post(
        door, json={"recipient_name": ""}, headers={**courier, **_key("n1")}
    )
    assert nameless.status_code == 422, nameless.text

    # A courier may upload the picture through the same pipeline a seller
    # uses — that guard was widened rather than a second one built.
    shot = client.post(
        f"{API}/staff/media",
        files={"file": ("door.jpg", _photograph(900, 700), "image/jpeg")},
        headers=courier,
    )
    assert shot.status_code == 201, shot.text

    with_photo = client.post(
        door,
        json={"recipient_name": "Qo'shni", "photo_url": shot.json()["media_url"]},
        headers={**courier, **_key("n2")},
    )
    assert with_photo.status_code == 200, with_photo.text

    shift = client.get(f"{API}/courier/shifts/current", headers=courier).json()
    kept = shift["attempts"][-1]
    assert kept["recipient_name"] == "Qo'shni"
    assert kept["photo_url"], "the evidence is stored"

    # And without one it still goes through, noted as such in the log.
    second = _on_a_round(client, auth, operator, courier_id, cash=False, sequence=2)
    plain = client.post(
        f"{API}/courier/orders/{second['id']}/deliver",
        json={"recipient_name": "Mijozning o'zi"},
        headers={**courier, **_key("n3")},
    )
    assert plain.status_code == 200, plain.text
    rows = _audit_rows("order.deliver", second["id"])
    assert rows and "suratsiz" in rows[-1].note


def test_a_cash_figure_that_does_not_match_is_refused(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A courier who mistypes it is short at the end of the day with nothing
    to point at, and a mismatch is far likelier to be a typo than a part
    payment worth recording."""
    courier_id, courier = _courier(staff, "+998900090051")
    client.post(f"{API}/courier/shifts", headers={**courier, **_key("shift-5")})
    order = _on_a_round(client, auth, operator, courier_id, cash=True)
    door = f"{API}/courier/orders/{order['id']}/deliver"
    owed = order["total"]

    wrong = client.post(
        door,
        json={"recipient_name": "Mijoz", "cash_collected": owed - 1000},
        headers={**courier, **_key("c1")},
    )
    assert wrong.status_code == 400
    assert str(owed) in wrong.json()["detail"]

    # And a delivery outside a shift has nowhere to put the money.
    lone_id, lone = _courier(staff, "+998900090052")
    theirs = _on_a_round(client, auth, operator, lone_id, cash=True)
    refused = client.post(
        f"{API}/courier/orders/{theirs['id']}/deliver",
        json={
            "recipient_name": "Mijoz",
            "cash_collected": theirs["total"],
        },
        headers={**lone, **_key("c2")},
    )
    assert refused.status_code == 409
    assert "smena" in refused.json()["detail"].lower()

    assert client.post(
        door,
        json={"recipient_name": "Mijoz", "cash_collected": owed},
        headers={**courier, **_key("c3")},
    ).status_code == 200
    assert not _stock_is_consistent()


def test_a_failed_attempt_keeps_the_order_and_the_courier(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """There is deliberately no `failed` status: a refusal at a door is an
    event, not a state of the order — it is still on its way. What a dispute
    needs is how many times and why, which is a list.

    And giving up is the operator's: the courier is at one door with one
    refusal, and the person who can see three of them and phone the customer
    is somebody else.
    """
    courier_id, courier = _courier(staff, "+998900090061")
    client.post(f"{API}/courier/shifts", headers={**courier, **_key("shift-6")})
    order = _on_a_round(client, auth, operator, courier_id, cash=False)
    door = f"{API}/courier/orders/{order['id']}/failed"

    for index, reason in enumerate(
        ("Eshikni ochmadi", "Telefon o'chirilgan", "Manzilda yo'q ekan")
    ):
        attempt = client.post(
            door, json={"reason": reason}, headers={**courier, **_key(f"x{index}")}
        )
        assert attempt.status_code == 200, attempt.text
        # Still shipped, still theirs, and the count is climbing.
        assert attempt.json()["status"] == "shipped"
        assert attempt.json()["attempts"] == index + 1
        assert attempt.json()["last_failure"] == reason

    stop = next(
        row
        for row in client.get(f"{API}/courier/orders", headers=courier).json()
        if row["id"] == order["id"]
    )
    assert stop["attempts"] == 3

    # The customer's timeline is untouched: an attempt is not a step their
    # order took, and writing one would put "delivered" in their history
    # before it was true.
    theirs = client.get(f"{API}/orders/{order['id']}", headers=auth).json()
    assert theirs["status"] == "shipped"
    assert not any(e["done"] and e["status"] == "delivered" for e in theirs["events"])

    # A reason is required — "not delivered" with nothing after it is the row
    # nobody can act on.
    assert client.post(
        door, json={"reason": ""}, headers={**courier, **_key("x9")}
    ).status_code == 422

    # The way out is the operator's, and it now exists: goods that never
    # reached the customer were never sold, so cancelling puts the counts back.
    assert client.post(
        f"{API}/staff/orders/{order['id']}/status",
        json={"status": "cancelled", "note": "uch urinish — mijoz javob bermadi"},
        headers=operator,
    ).status_code == 200
    assert client.get(f"{API}/orders/{order['id']}", headers=auth).json()["status"] == "cancelled"
    assert not _stock_is_consistent()


def test_a_collection_run_brings_returns_back_to_the_warehouse(
    client: TestClient,
    auth: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A `RemovalOrder` carries goods out to a seller who wants their stock
    back. This brings goods in from customers whose returns were approved —
    opposite direction, different paperwork, same van.

    Receiving one puts nothing on a shelf: whether returned goods are sellable
    is the refund's decision, and doing it here as well would put the same
    shirt back twice.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900090071")
    courier_id, courier = _courier(staff, "+998900090072")
    request, _, _, _ = _refundable_return(client, auth, operator)

    made = client.post(
        f"{API}/staff/pickups",
        json={
            "courier_id": courier_id,
            "return_request_ids": [request["id"]],
            "note": "ertaga ertalab",
        },
        headers=operator,
    )
    assert made.status_code == 201, made.text
    run = made.json()
    assert run["code"].startswith("PCK-")
    assert run["status"] == "open"
    assert run["next_statuses"] == ["collected", "cancelled"]
    line = run["lines"][0]
    # What a courier needs at the door, without another request.
    assert line["customer_phone"] and line["address_line"]
    assert line["collected"] is None, "nobody has tried yet"

    # One van per parcel.
    assert client.post(
        f"{API}/staff/pickups",
        json={"courier_id": courier_id, "return_request_ids": [request["id"]]},
        headers=operator,
    ).status_code == 409

    # It is on this courier's list and nobody else's.
    assert [r["id"] for r in client.get(f"{API}/courier/pickups", headers=courier).json()] == [
        run["id"]
    ]
    _, other = _courier(staff, "+998900090073")
    assert client.get(f"{API}/courier/pickups", headers=other).json() == []
    assert client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={"lines": [{"return_request_id": request["id"], "collected": True}]},
        headers={**other, **_key("p0")},
    ).status_code == 403

    # Not collected needs a reason, for the same purpose a failed delivery does.
    assert client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={"lines": [{"return_request_id": request["id"], "collected": False}]},
        headers={**courier, **_key("p1")},
    ).status_code == 400

    got = client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={
            "lines": [{"return_request_id": request["id"], "collected": True}],
            "note": "qadoq butun",
        },
        headers={**courier, **_key("p2")},
    )
    assert got.status_code == 200, got.text
    assert got.json()["status"] == "collected"
    assert got.json()["lines"][0]["collected"] is True
    assert got.json()["lines"][0]["attempted_at"]

    # Sent twice, collected once.
    assert client.post(
        f"{API}/courier/pickups/{run['id']}/collect",
        json={
            "lines": [{"return_request_id": request["id"], "collected": True}],
            "note": "qadoq butun",
        },
        headers={**courier, **_key("p2")},
    ).json() == got.json()

    # The warehouse books it in — and the shelf does not move.
    with Session(engine) as session:
        before = _stock_snapshot(session)
    received = client.post(
        f"{API}/staff/pickups/{run['id']}/receive", headers=warehouse
    )
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "received"
    assert received.json()["received_at"]
    assert received.json()["next_statuses"] == []
    with Session(engine) as session:
        assert _stock_snapshot(session) == before, "the refund decides the shelf"

    # A courier does not book goods in at the warehouse desk.
    assert client.post(
        f"{API}/staff/pickups/{run['id']}/receive", headers=courier
    ).status_code == 403
    # And twice is not twice.
    assert client.post(
        f"{API}/staff/pickups/{run['id']}/receive", headers=warehouse
    ).status_code == 409

    # The warehouse can see what is coming, which is the point of it arriving
    # at their desk.
    seen = client.get(
        f"{API}/staff/pickups", params={"status": "received"}, headers=warehouse
    )
    assert seen.status_code == 200
    assert run["id"] in [r["id"] for r in seen.json()]
    assert not _stock_is_consistent()


def _stock_snapshot(session: Session) -> dict[int, int]:
    return {row.id: row.stock_left for row in session.exec(select(Offer)).all()}


# ================================================================== the gaps closed

# Five things the system could not answer. Each one is somebody looking at a
# screen with a reasonable question and being told nothing.


# ------------------------------------------------ what became of what I proposed


def test_a_seller_reads_what_became_of_the_card_they_proposed(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A refusal carries a reason, and the seller could not read it.

    Proposing worked. Approved, the card turns up in the shop and they can
    find it there. Refused, it went nowhere they could look — so a seller was
    being asked to fix something without being told what was wrong with it,
    and the only way to find out was to telephone an admin.
    """
    seller_id, mine = _linked_seller(staff, "Taklif Bir", "+998900100001")
    _, theirs = _linked_seller(staff, "Taklif Ikki", "+998900100002")
    category = client.get(f"{API}/categories").json()[0]["slug"]

    def propose(sku: str, headers: dict[str, str]) -> dict:
        made = client.post(
            f"{API}/staff/catalog/proposals",
            json={
                "sku": sku,
                "title": f"Taklif {sku}",
                "category_slug": category,
                "price": 90_000,
            },
            headers=headers,
        )
        assert made.status_code == 201, made.text
        return made.json()

    refused = propose("MB-GAP-PROP-1", mine)
    accepted = propose("MB-GAP-PROP-2", mine)
    somebody_elses = propose("MB-GAP-PROP-3", theirs)

    # Before anybody has looked: in the queue, and the seller can see that it
    # is — "has anybody read it yet" is the other half of the question.
    waiting = client.get(f"{API}/staff/catalog/proposals", headers=mine)
    assert waiting.status_code == 200, waiting.text
    rows = {row["id"]: row for row in waiting.json()["items"]}
    assert rows[refused["id"]]["status"] == "moderating"
    assert rows[refused["id"]]["moderation_note"] == ""

    # Nobody else's proposals, and that is not a filter they chose: for a
    # seller these are the only rows that exist.
    assert somebody_elses["id"] not in rows
    assert {row["proposed_by"]["id"] for row in waiting.json()["items"]} == {seller_id}

    decided = client.post(
        f"{API}/staff/catalog/products/{refused['id']}/status",
        json={"status": "rejected", "reason": "Surat yo'q — kamida bitta kerak"},
        headers=admin,
    )
    assert decided.status_code == 200, decided.text
    assert client.post(
        f"{API}/staff/catalog/products/{accepted['id']}/status",
        json={"status": "published"},
        headers=admin,
    ).status_code == 200

    # The refusal, and the reason for it, which is the whole point.
    after = client.get(f"{API}/staff/catalog/proposals", headers=mine).json()["items"]
    rows = {row["id"]: row for row in after}
    assert rows[refused["id"]]["status"] == "rejected"
    assert rows[refused["id"]]["moderation_note"] == "Surat yo'q — kamida bitta kerak"
    # And the approved one is here too, so a seller can confirm the card in the
    # shop is theirs rather than hunting the catalogue for it.
    assert rows[accepted["id"]]["status"] == "published"
    assert rows[accepted["id"]]["moderation_note"] == ""

    # The list a seller actually opens after being told "one was refused".
    only_refused = client.get(
        f"{API}/staff/catalog/proposals", params={"status": "rejected"}, headers=mine
    )
    assert only_refused.status_code == 200, only_refused.text
    assert [row["id"] for row in only_refused.json()["items"]] == [refused["id"]]
    assert only_refused.json()["total"] == 1

    # Findable by SKU, which is what a seller's own system calls it.
    found = client.get(
        f"{API}/staff/catalog/proposals",
        params={"q": "MB-GAP-PROP-2"},
        headers=mine,
    ).json()["items"]
    assert [row["id"] for row in found] == [accepted["id"]]

    # An admin has no shop, so they read every seller's proposals — with the
    # provenance on each row — and may narrow it to one.
    everybody = client.get(f"{API}/staff/catalog/proposals", headers=admin)
    assert everybody.status_code == 200, everybody.text
    seen = {row["id"] for row in everybody.json()["items"]}
    assert {refused["id"], accepted["id"], somebody_elses["id"]} <= seen
    # A draft the platform wrote itself is not a proposal and has no business
    # in a list about somebody else's suggestions.
    assert all(row["proposed_by"] for row in everybody.json()["items"])
    narrowed = client.get(
        f"{API}/staff/catalog/proposals",
        params={"seller_id": seller_id},
        headers=admin,
    ).json()["items"]
    assert somebody_elses["id"] not in {row["id"] for row in narrowed}

    # Not a customer's list, and not an anonymous one.
    assert client.get(f"{API}/staff/catalog/proposals", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/catalog/proposals").status_code == 401


# ----------------------------------------------- a weight band is a contract term


def test_a_weight_band_can_be_edited_and_every_change_is_logged(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The bands were readable and unwritable: a rate somebody is charged
    arrived through the seed and could only be changed in the database, which
    is a change with nobody's name on it.

    A band this light covers nothing in the catalogue — the lightest seeded
    band tops out at 500 g — so the suite's other arithmetic is untouched by
    it. That is deliberate: these rates are global, and a test that edited a
    real band would be editing what every other test is charged.
    """
    _, theirs = _linked_seller(staff, "Tarif Bir", "+998900100011")
    seeded = client.get(f"{API}/staff/payouts/tariffs", headers=admin).json()

    made = client.post(
        f"{API}/staff/payouts/tariffs",
        json={
            "max_grams": 12,
            "fee": 1_000,
            "storage_per_day": 5,
            "label": "Sinov guruhi",
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    band = made.json()
    assert (band["max_grams"], band["fee"], band["storage_per_day"]) == (12, 1_000, 5)

    # Writing a band is logged with a name against it, and the log says which
    # band in words — a row id is not a band anybody recognises a year later.
    created = _audit_rows("tariff.create", band["id"])
    assert created and created[-1].actor_role is UserRole.ADMIN
    assert "Sinov guruhi" in created[-1].note

    # One row per field that actually moved. "The band was edited" is not a
    # fact a seller disputing a charge can act on; "the fee went from 1 000 to
    # 4 000 on this day, by this person" is.
    changed = client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}",
        json={"fee": 4_000, "storage_per_day": 5, "label": "Sinov guruhi"},
        headers=admin,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["fee"] == 4_000
    fees = _audit_rows("tariff.fee", band["id"])
    assert [(row.old_value, row.new_value) for row in fees] == [("1000", "4000")]
    # Only when it moved: a panel saving a form it did not change should not
    # fill the log with a change nobody made.
    assert not _audit_rows("tariff.storage_per_day", band["id"])
    assert not _audit_rows("tariff.label", band["id"])

    # Two bands may not share a ceiling. `band_for` takes the lightest band
    # that still covers a parcel, so with two of them the answer to "what does
    # this cost to handle" would depend on row order.
    clash = client.post(
        f"{API}/staff/payouts/tariffs",
        json={"max_grams": 12, "fee": 2_000},
        headers=admin,
    )
    assert clash.status_code == 409
    assert client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}",
        json={"max_grams": 500},
        headers=admin,
    ).status_code == 409, "500 g is the seeded lightest band"

    # The heaviest band is the roof. Delete it and every parcel above the band
    # below falls into no band at all and is handled free — a discount nobody
    # decided to give and nothing would report.
    bands = client.get(f"{API}/staff/payouts/tariffs", headers=admin).json()
    roof = max(bands, key=lambda row: row["max_grams"])
    refused = client.delete(f"{API}/staff/payouts/tariffs/{roof['id']}", headers=admin)
    assert refused.status_code == 409
    assert "guruh" in refused.json()["detail"].lower()
    assert client.get(f"{API}/staff/payouts/tariffs", headers=admin).json() == bands, (
        "a refusal changes nothing"
    )

    # A rate is a term of a contract, so a seller reads it and does not write
    # it — and a customer does neither.
    assert client.post(
        f"{API}/staff/payouts/tariffs",
        json={"max_grams": 14, "fee": 1},
        headers=theirs,
    ).status_code == 403
    assert client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}", json={"fee": 1}, headers=theirs
    ).status_code == 403
    assert client.delete(
        f"{API}/staff/payouts/tariffs/{band['id']}", headers=theirs
    ).status_code == 403
    assert client.get(f"{API}/staff/payouts/tariffs", headers=auth).status_code == 403
    assert client.patch(
        f"{API}/staff/payouts/tariffs/{band['id']}", json={"fee": 1}
    ).status_code == 401

    assert client.patch(
        f"{API}/staff/payouts/tariffs/999999", json={"fee": 1}, headers=admin
    ).status_code == 404

    # Withdrawn, and the withdrawal logged too.
    gone = client.delete(f"{API}/staff/payouts/tariffs/{band['id']}", headers=admin)
    assert gone.status_code == 200, gone.text
    assert _audit_rows("tariff.delete", band["id"])
    # The table as the seed left it: this test edited nothing anybody else is
    # charged, which is what makes it safe to run beside the rest of them.
    assert client.get(f"{API}/staff/payouts/tariffs", headers=admin).json() == seeded
    assert client.delete(
        f"{API}/staff/payouts/tariffs/{band['id']}", headers=admin
    ).status_code == 404


def test_editing_a_tariff_does_not_rewrite_a_closed_statement(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The property that makes the bands safe to edit at all.

    A closed statement is a figure a seller has read. Recomputing it against
    today's rates would mean that reading it twice gives two answers, which
    makes every answer provisional — the same reason the commission on a line
    is the rate it sold at rather than the rate on the seller row today.

    So this walks both halves: the closed run does not move when the band
    under it is doubled a hundredfold, and the next open run does.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900100021")
    seller_id, _ = _linked_seller(staff, "Tarif Ikki", "+998900100022", commission=10)

    # A band nothing else in the catalogue falls into, so this test is not
    # editing what every other test is charged. Written before the sale,
    # because the fee is captured onto the order line at checkout.
    band = client.post(
        f"{API}/staff/payouts/tariffs",
        json={
            "max_grams": 9,
            "fee": 5_000,
            "storage_per_day": 100,
            "label": "Qulf guruhi",
        },
        headers=admin,
    )
    assert band.status_code == 201, band.text
    band_id = band.json()["id"]

    first_id, _ = _card_with_a_colour(client, admin, "MB-GAP-LOCK-1", with_a_size=False)
    second_id, _ = _card_with_a_colour(client, admin, "MB-GAP-LOCK-2", with_a_size=False)
    with Session(engine) as session:
        for product_id in (first_id, second_id):
            row = session.get(Product, product_id)
            row.weight_grams = 7
            session.add(row)
        session.commit()

    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=first_id, price=200_000,
    )

    period = _period(
        client, admin, starts="2047-01-01", ends="2047-12-31", label="Qulflangan"
    )
    before = _statement(client, admin, period["id"], seller_id)
    assert before["fulfilment"] == 5_000, "one unit, at the band's fee"
    assert before["storage"] > 0
    # Nothing has moved for months by the closing day, so the shelf rate is
    # tripled — and the line says so, which is what makes it checkable.
    assert "× 300 so'm" in _lines(before, "storage")[0]["note"]

    closed = client.post(
        f"{API}/staff/payouts/periods/{period['id']}/close", headers=admin
    )
    assert closed.status_code == 200, closed.text
    frozen = client.get(
        f"{API}/staff/payouts/statements/{before['id']}", headers=admin
    ).json()
    assert frozen["status"] == "closed"

    # The contract is renegotiated, steeply.
    bumped = client.patch(
        f"{API}/staff/payouts/tariffs/{band_id}",
        json={"fee": 999_000, "storage_per_day": 9_900},
        headers=admin,
    )
    assert bumped.status_code == 200, bumped.text

    # Every row of the closed account, unchanged — not the totals only, the
    # lines and their workings-out, because the note is what a seller checks
    # the figure against.
    after = client.get(
        f"{API}/staff/payouts/statements/{before['id']}", headers=admin
    )
    assert after.status_code == 200, after.text
    assert after.json() == frozen, "a closed statement is finished"
    assert (after.json()["fulfilment"], after.json()["storage"]) == (
        before["fulfilment"],
        before["storage"],
    )

    # And the lock is a lock rather than an accident of nothing being asked:
    # the next run, still open, is worked out at the new rate.
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=second_id, price=200_000,
    )
    later = _period(
        client, admin, starts="2048-01-01", ends="2048-12-31", label="Yangi stavka"
    )
    now = _statement(client, admin, later["id"], seller_id)
    assert now["fulfilment"] == 999_000, "the parcel sold after the change"
    assert "× 29700 so'm" in _lines(now, "storage")[0]["note"]
    # The settled sale is spent and is not restated into the new run.
    assert [line["order_item_id"] for line in _lines(now, "sale")] != [
        line["order_item_id"] for line in _lines(before, "sale")
    ]

    client.delete(f"{API}/staff/payouts/tariffs/{band_id}", headers=admin)
    assert not _stock_is_consistent()


# ------------------------------------------------------- how the month is going


def test_a_seller_reads_the_period_still_running_and_it_says_it_is_not_final(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    operator: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """"How is this month going" had no answer.

    `/statements` lists the runs an admin has generated, so until somebody
    generated one a seller mid-period was told nothing — while the sales, the
    returns and the days of storage were all in the database being counted
    for them.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900100031")
    seller_id, mine = _linked_seller(staff, "Joriy Bir", "+998900100032", commission=10)
    _, theirs = _linked_seller(staff, "Joriy Ikki", "+998900100033")

    product_id, _ = _card_with_a_colour(client, admin, "MB-GAP-NOW-1", with_a_size=False)
    _sell_and_deliver(
        client, auth, admin, operator, warehouse,
        seller_id=seller_id, product_id=product_id, price=700_000, quantity=2,
    )

    running = client.get(f"{API}/staff/payouts/current", headers=mine)
    assert running.status_code == 200, running.text
    body = running.json()

    # The point of the shape: it says it is a guess before anybody asks. A
    # seller shown a figure and paid a different one has been told the first
    # number was provisional, which makes every number provisional.
    assert body["is_final"] is False
    assert body["as_of"]
    assert body["starts_on"] <= body["ends_on"]

    # The arithmetic is the arithmetic — 2 × 700 000 at the rate on the line.
    assert (body["seller_id"], body["seller_name"]) == (seller_id, "Joriy Bir")
    assert body["gross_sales"] == 1_400_000
    assert body["commission"] == 140_000
    assert body["payable"] == sum(line["amount"] for line in body["lines"])
    assert body["line_count"] == len(body["lines"])
    assert body["lines"], "an account to read, not a number to argue with"

    # Not a statement, and nothing about it could be mistaken for one: no id
    # to fetch, no status that could become `paid`.
    assert "id" not in body and "status" not in body
    assert all("id" not in line for line in body["lines"])

    # And it wrote nothing. A read that persisted a statement would let a
    # seller opening their cabinet create the run an admin is supposed to.
    with Session(engine) as session:
        assert not session.exec(
            select(SellerStatement).where(SellerStatement.seller_id == seller_id)
        ).all()

    # Somebody else's sales are not in it.
    others = client.get(f"{API}/staff/payouts/current", headers=theirs)
    assert others.status_code == 200, others.text
    assert others.json()["seller_id"] != seller_id
    assert others.json()["gross_sales"] == 0

    # An admin has no shop of their own, so they say whose.
    assert client.get(f"{API}/staff/payouts/current", headers=admin).status_code == 400
    for_them = client.get(
        f"{API}/staff/payouts/current",
        params={"seller_id": seller_id},
        headers=admin,
    )
    assert for_them.status_code == 200, for_them.text
    assert for_them.json()["gross_sales"] == 1_400_000
    assert client.get(
        f"{API}/staff/payouts/current", params={"seller_id": 999999}, headers=admin
    ).status_code == 404

    assert client.get(f"{API}/staff/payouts/current", headers=auth).status_code == 403
    assert client.get(f"{API}/staff/payouts/current").status_code == 401

    # It is a preview of the run, not a second opinion about it: generating a
    # period over the same days reaches the same figure from the same lines.
    period = _period(
        client, admin, starts="2049-01-01", ends="2049-12-31", label="Joriy sinov"
    )
    statement = _statement(client, admin, period["id"], seller_id)
    assert statement["gross_sales"] == body["gross_sales"]
    assert statement["commission"] == body["commission"]
    assert [
        (line["kind"], line["amount"], line["order_item_id"])
        for line in _lines(statement, "sale")
    ] == [
        (line["kind"], line["amount"], line["order_item_id"])
        for line in body["lines"]
        if line["kind"] == "sale"
    ]

    # Closing it is what turns the number into a promise — and the running
    # total then reads zero for what has been settled, because a closed
    # statement's sources are spent.
    client.post(f"{API}/staff/payouts/periods/{period['id']}/close", headers=admin)
    settled = client.get(f"{API}/staff/payouts/current", headers=mine).json()
    assert settled["is_final"] is False
    assert settled["gross_sales"] == 0, "paid for once"
    assert not _stock_is_consistent()


# ------------------------------------------------------------ the brand index


def test_the_brand_index_says_how_many_cards_carry_each_brand(
    client: TestClient, admin: dict[str, str]
) -> None:
    """`product_count` was in the shape and was always nought.

    The figure was only ever computed in `/products/filters`, where it is
    scoped to one listing so the tick-boxes add up to the grid beside them. An
    A-to-Z of marques with "(0)" against every one of them tells a shopper
    nothing and reads like a bug.
    """
    assert client.post(
        f"{API}/staff/catalog/brands",
        json={"slug": "sinov-sanoq-index", "name": "Sanoq Index"},
        headers=admin,
    ).status_code == 201
    category = client.get(f"{API}/categories").json()[0]["slug"]

    def counted() -> int:
        rows = client.get(f"{API}/brands")
        assert rows.status_code == 200, rows.text
        return next(
            row["product_count"]
            for row in rows.json()
            if row["slug"] == "sinov-sanoq-index"
        )

    # A brand with nothing in the shop is still listed — the index is a
    # directory — and counts nought, which is the truth about it.
    assert counted() == 0

    card = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "MB-GAP-BRAND-1",
            "title": "Sanoq kartochkasi",
            "category_slug": category,
            "brand_slug": "sinov-sanoq-index",
            "price": 60_000,
        },
        headers=admin,
    )
    assert card.status_code == 201, card.text

    # A draft is not in the shop, and tapping the brand would open an empty
    # listing — the listing is narrowed the same way, so the count is too.
    assert counted() == 0

    assert client.post(
        f"{API}/staff/catalog/products/{card.json()['id']}/status",
        json={"status": "published"},
        headers=admin,
    ).status_code == 200
    assert counted() == 1

    # The same window the filter sheet counts in, so the two screens agree.
    sheet = client.get(f"{API}/products/filters").json()["brands"]
    assert next(
        row["product_count"] for row in sheet if row["slug"] == "sinov-sanoq-index"
    ) == 1

    # Every seeded marque is counted, not just the one this test wrote: the
    # figure was nought for all of them.
    assert sum(row["product_count"] for row in client.get(f"{API}/brands").json()) > 1

    # Withdrawn from the shop, and the count follows it out.
    assert client.post(
        f"{API}/staff/catalog/products/{card.json()['id']}/status",
        json={"status": "archived", "reason": "sinov tugadi"},
        headers=admin,
    ).status_code == 200
    assert counted() == 0


def test_the_running_total_names_the_run_it_belongs_to_when_there_is_one(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """Two windows "so far" can mean, and the answer says which it is.

    Between runs there is no period to belong to — the last one is closed and
    the next is not open — and answering with silence would be answering "how
    is this month going" with "an admin has not got round to it". So the days
    since the last period are worked out instead and come back with no id,
    because they are not a period: calling them one would invite somebody to
    close them.

    Once a run does cover today, that is the window, and its dates were
    somebody's decision rather than ours.
    """
    _, mine = _linked_seller(staff, "Oyna Bir", "+998900100041")

    # No run covers today, so the window is the gap and says so.
    gap = client.get(f"{API}/staff/payouts/current", headers=mine)
    assert gap.status_code == 200, gap.text
    assert gap.json()["period_id"] is None
    assert gap.json()["period_status"] is None
    assert gap.json()["period_label"], "a window with no name still says what it is"
    assert gap.json()["ends_on"] == utcnow().date().isoformat(), "through today"

    # Opened. Periods may not overlap and every test here shares one database,
    # so this run starts today: the days behind it are taken by the storage
    # test, which dates its window to yesterday. A test added after this one
    # can no longer open a run covering today — take a window in the future,
    # the way the rest of this section does.
    today = utcnow().date()
    period = _period(
        client,
        admin,
        starts=today.isoformat(),
        ends=(today + timedelta(days=5)).isoformat(),
        label="Joriy oy",
    )

    now = client.get(f"{API}/staff/payouts/current", headers=mine)
    assert now.status_code == 200, now.text
    body = now.json()
    assert body["period_id"] == period["id"]
    assert body["period_status"] == "open"
    assert body["period_label"] == "Joriy oy"
    assert body["starts_on"] == period["starts_on"]
    assert body["ends_on"] == period["ends_on"], "the run's days, not ours"
    # Still not the figure they will be paid: closing is what makes it one.
    assert body["is_final"] is False


# ================================================== the same answer on both databases

# SQLite for development, Postgres for production. Anything that answers
# differently on the two is a bug that reaches the user through whichever one
# the tests are not running on, so these run on both and assert the same thing.


def test_search_ignores_case_in_russian_as_well_as_english(
    client: TestClient,
    admin: dict[str, str],
    auth: dict[str, str],
    sign_in: Callable[[str], dict[str, str]],
) -> None:
    """`lower()` is not the same function on the two databases.

    Every search here is already written the portable way —
    `func.lower(column).like(needle)` with the needle lowered in Python — so
    that `LIKE`'s own case rules never come into it. SQLite's `LIKE` ignores
    ASCII case and Postgres' does not, and with both sides lowercase that
    difference cannot bite.

    What it misses is that **SQLite's `lower()` is ASCII-only**:

        lower('Чайники')   -> 'Чайники'   unchanged, on SQLite
        'ЧАЙНИКИ'.lower()  -> 'чайники'   Python, which is not ASCII-only
        'Чайники' LIKE '%чайники%'  ->  no match

    Postgres lowercases Cyrillic properly and matches. So this was live on
    SQLite — every developer's machine — and would have been *fixed* by the
    move to Postgres, which is the worst way for a bug to go: nothing raises,
    no test that searches in Latin notices, and the symptom is a customer
    typing a Russian name into a trilingual shop and being told there is
    nothing there.

    `app.db` now replaces SQLite's `lower` with Python's, so this test is the
    same on both. It searches in upper case on purpose: matching only works if
    both sides really were folded.
    """
    category = client.get(f"{API}/categories").json()[0]["slug"]
    made = client.post(
        f"{API}/staff/catalog/products",
        json={
            "sku": "MB-CYR-1",
            "title": "Чайник электрический",
            "subtitle": "Стеклянный",
            "description": "Чайник с подсветкой",
            "category_slug": category,
            "price": 250_000,
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    product_id = made.json()["id"]

    # The editor's search, before it is even published.
    def admin_hits(q: str) -> list[int]:
        got = client.get(
            f"{API}/staff/catalog/products", params={"q": q}, headers=admin
        )
        assert got.status_code == 200, got.text
        return [row["id"] for row in got.json()["items"]]

    assert product_id in admin_hits("Чайник"), "as typed"
    assert product_id in admin_hits("ЧАЙНИК"), "upper case Cyrillic"
    assert product_id in admin_hits("чайник"), "lower case Cyrillic"
    assert product_id in admin_hits("ЭЛЕКТРИЧЕСКИЙ"), "a later word, upper case"
    # And Latin still behaves, which is what would have broken if the fix had
    # been to stop lowering at all.
    assert admin_hits("MB-CYR-1") == admin_hits("mb-cyr-1") == [product_id]

    assert client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "published"},
        headers=admin,
    ).status_code == 200

    # The shopper's listing, and the typeahead behind the search box.
    def shop_hits(q: str) -> list[int]:
        got = client.get(f"{API}/products", params={"q": q, "show_sold_out": True})
        assert got.status_code == 200, got.text
        return [row["id"] for row in got.json()["items"]]

    assert product_id in shop_hits("ЧАЙНИК")
    assert product_id in shop_hits("чайник")
    # The description is searched too, and it only has the word in one case.
    assert product_id in shop_hits("ПОДСВЕТКОЙ")

    # A staff account found by name — the search an admin uses to appoint
    # somebody, and the one most likely to be given a Cyrillic name.
    theirs = sign_in("+998900110001")
    named = client.patch(
        f"{API}/me", json={"full_name": "Дилноза Расулова"}, headers=theirs
    )
    assert named.status_code == 200, named.text

    def users_found(q: str) -> list[str]:
        got = client.get(f"{API}/staff/users", params={"q": q}, headers=admin)
        assert got.status_code == 200, got.text
        return [row["phone"] for row in got.json()["items"]]

    assert "+998900110001" in users_found("Дилноза")
    assert "+998900110001" in users_found("ДИЛНОЗА"), "upper case Cyrillic"
    assert "+998900110001" in users_found("расулова"), "surname, lower case"
    # The phone half of the same search, which is what it is mostly used for.
    assert "+998900110001" in users_found("900110001")

    # Nothing matches a word that is not there — a search that found
    # everything would satisfy every assertion above.
    assert product_id not in shop_hits("самовар")
    assert "+998900110001" not in users_found("Гулнора")


def test_the_same_row_gets_the_same_id_on_a_freshly_seeded_database() -> None:
    """`reset()` has to put the id counters back, not just empty the tables.

    On SQLite the next rowid is `max(rowid) + 1`, so an empty table starts at 1
    again by itself. On Postgres a sequence is its own object and `DELETE` does
    not touch it — a second seed numbered the same catalogue from 63 instead of
    1, which broke every test that names a row by id and, worse, meant two
    freshly seeded databases could not be compared at all.

    The suite's own database is seeded once per session, so this asserts the
    property that made that safe: the seeded rows occupy the bottom of the
    range, from 1.
    """
    with Session(engine) as session:
        first = session.exec(
            select(Product).order_by(col(Product.id)).limit(1)
        ).one()
        assert first.id == 1, "the seed's first product is id 1, on either database"

        # Every seeded table that the suite names by id starts from 1 too.
        for model in (Category, Brand, User):
            lowest = session.exec(
                select(func.min(model.id)).select_from(model)
            ).one()
            assert lowest == 1, f"{model.__name__} ids start at 1"


def test_every_column_type_survives_the_round_trip_on_this_database() -> None:
    """The types SQLite is relaxed about and Postgres is not.

    SQLite stores what you hand it and barely inspects the declared type;
    Postgres enforces one. So a value that goes in and comes back unchanged on
    a developer's machine is not evidence that it will in production, and the
    classes that differ are well known: a JSON column, a naive datetime, a
    boolean, an enum, a float.

    This writes one of each through the models and reads it back through a
    fresh session — fresh so the answer comes from the database rather than
    from the identity map, which would happily hand back the Python object
    that was just put in and prove nothing.

    Nothing here is a fix; it is the assertion that no fix is needed, made on
    whichever database the suite was pointed at.
    """
    from app.models import ReturnRequest, ReturnStatus, Review, ReviewStatus

    with Session(engine) as session:
        # An existing order to hang a return on, so the foreign keys are real.
        item = session.exec(select(OrderItem).order_by(col(OrderItem.id))).first()
        assert item is not None, "the seed writes orders"
        # Plain integers, read out while the session is still open: the ORM
        # object goes stale the moment the block closes.
        product_id, order_id, item_id = item.product_id, item.order_id, item.id
        user_id = session.exec(select(User.id).order_by(col(User.id))).first()

        stamp = utcnow().replace(microsecond=123456)
        review = Review(
            product_id=product_id,
            user_id=user_id,
            rating=4,
            text="Turlar tekshiruvi",
            # JSON: a list of strings, non-ASCII among them, and an empty list
            # in the column beside it — `[]` and NULL are different values and
            # a driver that confused them would be found here.
            tags=["сифатли", "tez", "o'lchamiga mos"],
            photos=[],
            status=ReviewStatus.PUBLISHED,
            created_at=stamp,
        )
        request = ReturnRequest(
            user_id=user_id,
            order_id=order_id,
            order_item_id=item_id,
            reason="Turlar tekshiruvi",
            photos=["returns/a.png", "returns/b.png"],
            status=ReturnStatus.SUBMITTED,
        )
        session.add(review)
        session.add(request)
        session.commit()
        review_id, request_id = review.id, request.id

    with Session(engine) as fresh:
        got = fresh.get(Review, review_id)

        # JSON, both directions and both shapes.
        assert got.tags == ["сифатли", "tez", "o'lchamiga mos"]
        assert got.photos == [], "an empty list is a list, not a null"
        assert fresh.get(ReturnRequest, request_id).photos == [
            "returns/a.png",
            "returns/b.png",
        ]

        # A naive UTC datetime, to the microsecond. Every timestamp in this
        # codebase comes from `models.utcnow`, which strips the tzinfo, and the
        # columns are `DateTime` with no timezone — so both databases hold
        # `timestamp without time zone` and neither is doing a conversion.
        assert got.created_at.tzinfo is None, "naive on the way out as well as in"
        assert got.created_at == stamp, "microseconds included"

        # An enum, which is a VARCHAR with a check on SQLite and a real type on
        # Postgres. Read back as the Python member, not as its name.
        assert got.status is ReviewStatus.PUBLISHED
        assert got.rating == 4 and isinstance(got.rating, int)

        # And the enum is usable in a WHERE, which is where a native type
        # would bite if the value were being sent as the wrong thing.
        found = fresh.exec(
            select(Review).where(
                Review.id == review_id,
                col(Review.status).in_([ReviewStatus.PUBLISHED]),
                Review.created_at <= utcnow(),
            )
        ).first()
        assert found is not None, "enum in an IN, datetime in a comparison"

        # A float column, on a row the seed wrote.
        product = fresh.get(Product, product_id)
        assert isinstance(product.rating, float)

        # Boolean, and the `.is_(True)` form every listing uses.
        assert isinstance(product.in_stock, bool)
        assert fresh.exec(
            select(func.count()).select_from(Product).where(Product.in_stock.is_(True))
        ).one() >= 0

    # Tidy up: these rows would otherwise show up in another test's counts.
    with Session(engine) as session:
        session.delete(session.get(Review, review_id))
        session.delete(session.get(ReturnRequest, request_id))
        session.commit()


# ============================================ a seller's own product, end to end

# The catalogue is not the platform's alone. A seller opens their own product,
# photographs it, prices it and says what colours and sizes they have; what the
# warehouse confirms is that the goods turned up, not that the listing was
# permitted. These hold that whole line together, because it is one line and
# breaking it anywhere leaves a seller with a product nobody can buy.


def _listing_body(
    client: TestClient, seller: dict[str, str], title: str, **over
) -> dict:
    """A two-colour, five-size listing with real uploaded photographs."""
    images = []
    for name in ("front.jpg", "back.jpg"):
        got = client.post(
            f"{API}/staff/media",
            files={"file": (name, _photograph(900, 900), "image/jpeg")},
            headers=seller,
        )
        assert got.status_code == 201, got.text
        images.append(got.json()["media_url"])

    sizes = (("S", 6), ("M", 9), ("L", 7), ("XL", 4), ("XXL", 2))
    body = {
        "title": title,
        "subtitle": "Yumshoq trikotaj",
        "description": "Kunlik kiyish uchun.",
        "category_slug": client.get(f"{API}/categories").json()[0]["slug"],
        "price": 149_000,
        "weight_grams": 300,
        "images": images,
        "colors": [
            {
                "label": "Oq",
                "value": "#FFFFFF",
                "image_url": images[0],
                "sizes": [{"label": s, "quantity": q} for s, q in sizes],
            },
            {
                "label": "Qora",
                "value": "#111113",
                "image_url": images[1],
                "sizes": [{"label": s, "quantity": q - 1} for s, q in sizes],
            },
        ],
    }
    body.update(over)
    return body


def test_a_seller_adds_their_own_product_and_the_warehouse_confirms_it_arrived(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The whole line, in the order it happens.

    A seller adds a product with its photographs; it reaches the warehouse as
    *their* goods, declared and not yet counted; the warehouse counts it and
    **that** is what puts it in the shop. Approval here is not the platform
    deciding whether a card may exist — it is somebody confirming the box
    turned up.

    Six calls decomposed into one on purpose: create the card, post each
    image, post each colour, post each size, open the offer, declare the batch.
    Each of those is a chance to be the last one that worked, and the result of
    a half-run is a seller staring at a product nobody can buy with no way to
    tell which half is missing.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900120001")
    seller_id, mine = _linked_seller(staff, "Sotuvchi Do'kon", "+998900120002")

    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Mening futbolkam"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    listing = made.json()
    product_id = listing["id"]

    # The SKU is ours: a seller does not think in stock codes and should not
    # have to invent a unique one.
    assert listing["sku"].startswith("S"), listing["sku"]
    assert listing["price"] == 149_000

    # Two colours, five sizes each — ten cells that get counted.
    assert len(listing["stock"]) == 10
    assert {cell["color_label"] for cell in listing["stock"]} == {"Oq", "Qora"}
    assert sum(cell["declared"] for cell in listing["stock"]) == 28 + 23

    # Declared is a promise. Nothing is on the shelf, and the quantities in the
    # request went onto supply lines rather than onto a stock figure.
    assert listing["on_hand_total"] == 0
    assert all(cell["on_hand"] == 0 for cell in listing["stock"])
    assert listing["supply_code"] and listing["supply_status"] == "declared"

    # The pictures survived in the order they were given, first one primary.
    assert len(listing["images"]) == 2

    # Waiting on the warehouse, and the seller is told so in their own words.
    assert listing["stage"] == "awaiting_warehouse"
    assert listing["stage_label"]

    # And it is not in the shop. Not the listing, not the product page.
    assert client.get(f"{API}/products/{product_id}").status_code == 404
    shop = client.get(
        f"{API}/products", params={"q": "Mening futbolkam", "show_sold_out": True}
    ).json()
    assert product_id not in [row["id"] for row in shop["items"]]

    # The warehouse sees the batch, and whose goods it is.
    queue = client.get(
        f"{API}/staff/supplies", params={"status": "declared"}, headers=warehouse
    )
    assert queue.status_code == 200, queue.text
    batch = next(
        row for row in queue.json() if row["code"] == listing["supply_code"]
    )
    assert batch["seller"]["id"] == seller_id
    assert len(batch["lines"]) == 10

    # Counting it in is the confirmation, and the confirmation is what sells it.
    received = client.post(
        f"{API}/staff/supplies/{batch['id']}/receive",
        json={
            "lines": [
                {"line_id": row["id"], "received_quantity": row["declared_quantity"]}
                for row in batch["lines"]
            ]
        },
        headers=warehouse,
    )
    assert received.status_code == 200, received.text

    assert client.get(f"{API}/products/{product_id}").status_code == 200
    now = client.get(
        f"{API}/staff/catalog/listings/{product_id}", headers=mine
    ).json()
    assert now["stage"] == "on_sale"
    assert now["on_hand_total"] == 51
    # The card's own figures are a cache of the offers, and they were
    # recomputed when it became visible rather than left describing a product
    # that was not in the shop.
    page = client.get(f"{API}/products/{product_id}").json()
    assert page["price"] == 149_000
    assert page["in_stock"] is True
    assert len([v for v in page["variants"] if v["kind"] == "color"]) == 2

    # The move is logged as a status change like any other, with the reason.
    rows = _audit_rows("product.status", product_id)
    assert rows and listing["supply_code"] in rows[-1].note
    assert not _stock_is_consistent()


def test_buying_one_size_takes_it_off_that_size_and_no_other(
    client: TestClient,
    auth: dict[str, str],
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The invariant the grid exists for.

    A shop that has sold its last white M has sold it in white. If the count
    came off the product's total, or off the colour, the page would go on
    offering that M out of the black ones — and there is no working out
    afterwards which shirt the customer got.
    """
    warehouse = staff(UserRole.WAREHOUSE, "+998900120011")
    _, mine = _linked_seller(staff, "Razmer Do'kon", "+998900120012")

    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Razmer futbolkasi"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    product_id = made.json()["id"]
    batch_code = made.json()["supply_code"]

    batch = next(
        row
        for row in client.get(f"{API}/staff/supplies", headers=warehouse).json()
        if row["code"] == batch_code
    )
    client.post(
        f"{API}/staff/supplies/{batch['id']}/receive",
        json={
            "lines": [
                {"line_id": row["id"], "received_quantity": row["declared_quantity"]}
                for row in batch["lines"]
            ]
        },
        headers=warehouse,
    )

    variants = client.get(f"{API}/products/{product_id}").json()["variants"]
    white = next(v for v in variants if v["label"] == "Oq")
    black = next(v for v in variants if v["label"] == "Qora")
    white_m = next(
        v
        for v in variants
        if v["kind"] == "size" and v["label"] == "M" and v["parent_id"] == white["id"]
    )
    black_m = next(
        v
        for v in variants
        if v["kind"] == "size" and v["label"] == "M" and v["parent_id"] == black["id"]
    )
    white_l = next(
        v
        for v in variants
        if v["kind"] == "size" and v["label"] == "L" and v["parent_id"] == white["id"]
    )

    def cells() -> dict[int, int]:
        rows = client.get(
            f"{API}/staff/catalog/listings/{product_id}", headers=mine
        ).json()["stock"]
        return {row["variant_id"]: row["on_hand"] for row in rows}

    before = cells()
    assert before[white_m["id"]] == 9
    assert before[black_m["id"]] == 8
    assert before[white_l["id"]] == 7

    client.delete(f"{API}/cart", headers=auth)
    added = client.post(
        f"{API}/cart/items",
        json={
            "product_id": product_id,
            "variant_id": white_m["id"],
            "color_variant_id": white["id"],
            "quantity": 2,
        },
        headers=auth,
    )
    assert added.status_code == 201, added.text
    address = client.get(f"{API}/addresses", headers=auth).json()[0]
    placed = client.post(
        f"{API}/orders", json={"address_id": address["id"]}, headers=auth
    )
    assert placed.status_code == 201, placed.text

    after = cells()
    assert after[white_m["id"]] == 7, "the white M, and by exactly two"
    assert after[black_m["id"]] == 8, "the black M did not move"
    assert after[white_l["id"]] == 7, "nor did the white L"
    assert sum(after.values()) == sum(before.values()) - 2
    assert not _stock_is_consistent()


def test_a_listing_refuses_what_would_make_the_shelf_uncountable(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """The three refusals, each protecting a warehouse invariant.

    Mixing sized and unsized colours puts some counts a level above where the
    ledger looks for them, with no way to say how a colour's stock divides
    between sizes it has not got. A repeated colour or size makes two cells
    that mean the same thing, and the sum of the colours stops equalling the
    offer's total the first time either is counted.
    """
    _, mine = _linked_seller(staff, "Qoida Do'kon", "+998900120022")
    body = _listing_body(client, mine, "Qoida futbolkasi")

    mixed = {**body, "colors": [
        {**body["colors"][0]},
        {**body["colors"][1], "sizes": []},
    ]}
    refused = client.post(f"{API}/staff/catalog/listings", json=mixed, headers=mine)
    assert refused.status_code == 400
    assert "razmer" in refused.json()["detail"].lower()

    twice = {**body, "colors": [body["colors"][0], {**body["colors"][1], "label": "Oq"}]}
    assert client.post(
        f"{API}/staff/catalog/listings", json=twice, headers=mine
    ).status_code == 400

    dup_size = {**body, "colors": [
        {**body["colors"][0],
         "sizes": [{"label": "M", "quantity": 1}, {"label": "m", "quantity": 2}]},
    ]}
    assert client.post(
        f"{API}/staff/catalog/listings", json=dup_size, headers=mine
    ).status_code == 400

    # A picture is not optional: a card with no photograph is a card nobody taps.
    assert client.post(
        f"{API}/staff/catalog/listings", json={**body, "images": []}, headers=mine
    ).status_code == 400

    # Somebody else's door.
    assert client.post(
        f"{API}/staff/catalog/listings", json=body, headers=admin
    ).status_code == 400, "an admin has no shop of their own"
    assert client.get(f"{API}/staff/catalog/listings").status_code == 401


def test_a_seller_reads_the_reason_their_product_was_refused(
    client: TestClient,
    admin: dict[str, str],
    staff: Callable[[UserRole, str], dict[str, str]],
) -> None:
    """A refusal is a sentence the seller is owed.

    They are being asked to fix something; without the reason they are being
    asked to guess. `moderation_note` has always been on the row — what was
    missing was anywhere for a seller to read it.
    """
    _, mine = _linked_seller(staff, "Rad Do'kon", "+998900120032")
    made = client.post(
        f"{API}/staff/catalog/listings",
        json=_listing_body(client, mine, "Rad etiladigan futbolka"),
        headers=mine,
    )
    assert made.status_code == 201, made.text
    product_id = made.json()["id"]

    refused = client.post(
        f"{API}/staff/catalog/products/{product_id}/status",
        json={"status": "rejected", "reason": "Rasmda tovar ko'rinmaydi"},
        headers=admin,
    )
    assert refused.status_code == 200, refused.text

    mine_rows = client.get(f"{API}/staff/catalog/listings", headers=mine)
    assert mine_rows.status_code == 200, mine_rows.text
    row = next(r for r in mine_rows.json() if r["id"] == product_id)
    assert row["stage"] == "rejected"
    assert row["moderation_note"] == "Rasmda tovar ko'rinmaydi"
    assert row["stage_label"]

    # And a refused product is nobody else's to read.
    _, theirs = _linked_seller(staff, "Boshqa Do'kon", "+998900120042")
    assert product_id not in [
        r["id"] for r in client.get(f"{API}/staff/catalog/listings", headers=theirs).json()
    ]
    assert client.get(
        f"{API}/staff/catalog/listings/{product_id}", headers=theirs
    ).status_code == 404
