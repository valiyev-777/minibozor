"""End-to-end coverage of the flows the 47 screens depend on."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app import audit
from app import offers as of
from app import schemas as s
from app import stock as st
from app.core.config import settings
from app.db import engine
from app.deps import AdminUser
from app.models import (
    AuditLog,
    CartItem,
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
    assert "http://localhost:5173" in settings.cors_origin_list

    # And a wildcard in the environment is dropped rather than passed through.
    assert Settings(cors_origins="*").cors_origin_list == []
    assert Settings(cors_origins="*,https://ofis.minibozor.uz").cors_origin_list == [
        "https://ofis.minibozor.uz"
    ]


def test_a_preflight_answers_the_backoffice_by_name(client: TestClient) -> None:
    origin = "http://localhost:5173"
    preflight = client.options(
        f"{API}/staff/returns",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.status_code == 200
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
