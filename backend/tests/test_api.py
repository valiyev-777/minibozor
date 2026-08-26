"""End-to-end coverage of the flows the 47 screens depend on."""

from __future__ import annotations

from fastapi.testclient import TestClient

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
        f"{API}/cart/items", json={"product_id": product["id"], "quantity": 2}, headers=auth
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
        f"{API}/cart/items", json={"product_id": cheap["id"], "quantity": 1}, headers=auth
    ).json()
    assert cart["totals"]["delivery_fee"] > 0

    expensive = client.get(f"{API}/products", params={"sort": "price_desc"}).json()["items"][0]
    cart = client.post(
        f"{API}/cart/items", json={"product_id": expensive["id"], "quantity": 1}, headers=auth
    ).json()
    assert cart["totals"]["subtotal"] >= cart["totals"]["free_delivery_threshold"]
    assert cart["totals"]["delivery_fee"] == 0


def test_promo_code(client: TestClient, auth: dict[str, str]) -> None:
    client.delete(f"{API}/cart", headers=auth)
    product = client.get(f"{API}/products", params={"sort": "price_desc"}).json()["items"][0]
    client.post(f"{API}/cart/items", json={"product_id": product["id"]}, headers=auth)

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
    client.post(f"{API}/cart/items", json={"product_id": product["id"]}, headers=auth)

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
    client.post(f"{API}/cart/items", json={"product_id": product["id"]}, headers=auth)

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
    client.post(f"{API}/cart/items", json={"product_id": product["id"]}, headers=auth)

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
