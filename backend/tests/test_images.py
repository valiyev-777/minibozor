"""Choosing which photograph a customer sees first.

The panel used to say, out loud: "the order cannot be changed — to make
another one the cover you must delete the ones in front of it". Four shots of
a jacket with the good one third meant throwing two away. These tests hold the
door that replaced that sentence.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

API = "/api/v1"

# The suite shares one shop and one sku namespace, so a card written here and
# a card written in `test_api.py` under the same code is a 409 that only shows
# up when the whole suite runs. Everything this file writes is `RASM-…`.


# --------------------------------------------------------------------------- scaffolding


def _card(client: TestClient, admin: dict[str, str], *, sku: str) -> dict:
    """A draft card, filed and priced, so only the pictures are ever missing."""
    filed = client.post(
        f"{API}/admin/categories",
        json={"slug": "krossovkalar", "name": "Krossovkalar", "icon": "shoe"},
        headers=admin,
    )
    assert filed.status_code in (201, 409), filed.text
    made = client.post(
        f"{API}/admin/products",
        json={
            "sku": sku,
            "title": f"Krossovka {sku}",
            "category_slug": "krossovkalar",
            "price": 500_000,
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    return made.json()


def _grid(
    client: TestClient, admin: dict[str, str], product_id: int, colours: list[str]
) -> None:
    made = client.put(
        f"{API}/admin/products/{product_id}/variants",
        json={
            "colours": [{"colour": c, "hex": "#0E0F12"} for c in colours],
            "sizes": ["42"],
            "price": 500_000,
        },
        headers=admin,
    )
    assert made.status_code == 200, made.text


def _hang(
    client: TestClient,
    admin: dict[str, str],
    product_id: int,
    colour: str,
    name: str,
) -> int:
    """One photograph, and the id it was given."""
    hung = client.post(
        f"{API}/admin/products/{product_id}/images",
        json={"url": f"products/{name}.jpg", "colour": colour},
        headers=admin,
    )
    assert hung.status_code == 201, hung.text
    return next(row["id"] for row in hung.json() if row["url"].endswith(f"{name}.jpg"))


def _images(client: TestClient, admin: dict[str, str], product_id: int) -> list[dict]:
    got = client.get(f"{API}/admin/products/{product_id}/images", headers=admin)
    assert got.status_code == 200, got.text
    return got.json()


def _of(images: list[dict], colour: str) -> list[int]:
    """The ids of one colour's photographs, in the order the card holds them."""
    return [row["id"] for row in images if row["colour"] == colour]


def _promote(
    client: TestClient, headers: dict[str, str], product_id: int, image_id: int
):
    return client.put(
        f"{API}/admin/products/{product_id}/images/{image_id}/cover", headers=headers
    )


def _two_colours(
    client: TestClient, admin: dict[str, str], *, sku: str
) -> tuple[int, list[int], list[int]]:
    """A card photographed three times in black and twice in white."""
    card = _card(client, admin, sku=sku)
    _grid(client, admin, card["id"], ["Qora", "Oq"])
    black = [_hang(client, admin, card["id"], "Qora", f"{sku}-qora-{n}") for n in (1, 2, 3)]
    white = [_hang(client, admin, card["id"], "Oq", f"{sku}-oq-{n}") for n in (1, 2)]
    return card["id"], black, white


# --------------------------------------------------------------------------- the door


def test_the_third_photograph_becomes_the_cover_and_the_rest_keep_their_order(
    client: TestClient, admin: dict[str, str]
) -> None:
    product_id, black, _ = _two_colours(client, admin, sku="RASM-COVER")
    assert _of(_images(client, admin, product_id), "Qora") == black

    promoted = _promote(client, admin, product_id, black[2])
    assert promoted.status_code == 200, promoted.text

    # The chosen one first; the two it overtook still in the order they were
    # in — promoting is not shuffling.
    assert _of(promoted.json(), "Qora") == [black[2], black[0], black[1]]
    assert _of(_images(client, admin, product_id), "Qora") == [
        black[2],
        black[0],
        black[1],
    ]


def test_the_card_comes_back_densely_numbered_so_every_reader_agrees(
    client: TestClient, admin: dict[str, str]
) -> None:
    """``sort`` is written as 0 by everything that hangs a picture.

    Which means the stored order is a tie broken by ``id``, and the read paths
    do not all break it the same way. After a promotion the card is numbered
    0,1,2,… colour block by colour block, which is the only state in which
    "order by sort" and "order by sort, id" are the same sentence.
    """
    product_id, black, white = _two_colours(client, admin, sku="RASM-DENSE")
    assert {row["sort"] for row in _images(client, admin, product_id)} == {0}

    rows = _promote(client, admin, product_id, black[2]).json()
    assert [row["sort"] for row in rows] == [0, 1, 2, 3, 4]
    # And the blocks are still blocks: no colour is interleaved with another.
    assert [row["colour"] for row in rows] == ["Qora"] * 3 + ["Oq"] * 2
    assert _of(rows, "Oq") == white


def test_promoting_one_colour_leaves_the_other_colour_alone(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Colours are independent: `Qora`'s cover is not `Oq`'s business."""
    product_id, black, white = _two_colours(client, admin, sku="RASM-APART")

    rows = _promote(client, admin, product_id, black[2]).json()
    assert _of(rows, "Oq") == white

    # And the other way round, on the same card.
    rows = _promote(client, admin, product_id, white[1]).json()
    assert _of(rows, "Oq") == [white[1], white[0]]
    assert _of(rows, "Qora") == [black[2], black[0], black[1]]


def test_a_colourless_card_is_a_group_like_any_other(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The "umumiy" pile — a card with no colours is photographed too."""
    card = _card(client, admin, sku="RASM-PLAIN")
    shots = [_hang(client, admin, card["id"], "", f"rasm-plain-{n}") for n in (1, 2, 3)]

    rows = _promote(client, admin, card["id"], shots[1]).json()
    assert _of(rows, "") == [shots[1], shots[0], shots[2]]


def test_promoting_the_cover_answers_and_the_second_time_writes_nothing(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Polite, not clever: the same 200 and the same list.

    The first call on an untidy card still renumbers it — every ``sort`` is 0
    until somebody promotes something — so "no-op" is asserted on the second,
    where there is genuinely nothing left to move.
    """
    product_id, black, _ = _two_colours(client, admin, sku="RASM-ALREADY")

    first = _promote(client, admin, product_id, black[0])
    assert first.status_code == 200, first.text
    assert _of(first.json(), "Qora") == black

    second = _promote(client, admin, product_id, black[0])
    assert second.status_code == 200, second.text
    assert second.json() == first.json()


def test_a_photograph_of_another_card_is_refused(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A wrong id must not renumber somebody else's card."""
    mine, _, _ = _two_colours(client, admin, sku="RASM-MINE")
    theirs, black, _ = _two_colours(client, admin, sku="RASM-THEIRS")

    refused = _promote(client, admin, mine, black[2])
    assert refused.status_code == 404, refused.text
    # Untouched: still the order it was hung in, still unnumbered.
    rows = _images(client, admin, theirs)
    assert _of(rows, "Qora") == black
    assert {row["sort"] for row in rows} == {0}

    missing = _promote(client, admin, mine, 10_000_000)
    assert missing.status_code == 404, missing.text


def test_the_bench_may_not_choose_the_cover_and_the_owner_may(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """`CatalogWriter`: the shop window is the owner's, not the shelf's."""
    product_id, black, _ = _two_colours(client, admin, sku="RASM-ROLE")

    refused = _promote(client, warehouse, product_id, black[2])
    assert refused.status_code == 403, refused.text

    allowed = _promote(client, admin, product_id, black[2])
    assert allowed.status_code == 200, allowed.text


def test_promoting_a_photograph_does_not_move_the_publishing_gates(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The three gates count photographs per colour; order is not one of them."""
    product_id, black, _ = _two_colours(client, admin, sku="RASM-GATES")
    live = client.post(
        f"{API}/admin/products/{product_id}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert live.status_code == 200, live.text

    def card() -> dict:
        got = client.get(f"{API}/admin/products/{product_id}", headers=admin)
        assert got.status_code == 200, got.text
        return got.json()

    before = card()
    assert before["unready"] == []

    assert _promote(client, admin, product_id, black[2]).status_code == 200

    after = card()
    assert after["status"] == before["status"] == "active"
    assert after["unready"] == before["unready"]
    assert after["listing_gaps"] == before["listing_gaps"]


# --------------------------------------------------------------------------- the cover in the table


def _listed(client: TestClient, admin: dict[str, str], sku: str) -> dict:
    """One card as the catalogue table draws it, found by its code."""
    page = client.get(f"{API}/admin/products", params={"q": sku}, headers=admin)
    assert page.status_code == 200, page.text
    return next(row for row in page.json()["items"] if row["sku"] == sku)


def test_the_catalogue_table_reports_the_cover_photograph(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The first by `sort` then `id` — the same picture the phone shows."""
    sku = "RASM-LISTPIC"
    product_id, _, _ = _two_colours(client, admin, sku=sku)

    row = _listed(client, admin, sku)
    assert row["cover_url"] == f"products/{sku}-qora-1.jpg"
    assert row["image_count"] == 5
    # And the single-card shape agrees, so the table and the form cannot
    # disagree about which photograph is the cover.
    detail = client.get(f"{API}/admin/products/{product_id}", headers=admin).json()
    assert detail["cover_url"] == row["cover_url"]


def test_a_card_with_no_photographs_reports_an_empty_cover(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The `Rasmsiz` queue: empty string, not a broken tile.

    Not `snapshot_url` either — the receiving desk's picture over the open
    sack is a heap in a bag and is never what the catalogue should show.
    """
    sku = "RASM-NOPIC"
    _card(client, admin, sku=sku)

    row = _listed(client, admin, sku)
    assert row["cover_url"] == ""
    assert row["image_count"] == 0


def test_promoting_a_photograph_changes_what_the_table_shows(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The two features are one feature: the cover-setter sets *this*."""
    sku = "RASM-LISTMOVE"
    product_id, black, _ = _two_colours(client, admin, sku=sku)
    before = _listed(client, admin, sku)["cover_url"]
    assert before == f"products/{sku}-qora-1.jpg"

    assert _promote(client, admin, product_id, black[2]).status_code == 200

    after = _listed(client, admin, sku)["cover_url"]
    assert after == f"products/{sku}-qora-3.jpg"


def test_promoting_a_later_colour_leaves_the_card_cover_where_it_was(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A card's cover is its *first* colour's cover.

    Choosing the white jacket's best shot must not put a white jacket at the
    head of a card whose first colour is black.
    """
    sku = "RASM-LISTKEEP"
    product_id, _, white = _two_colours(client, admin, sku=sku)

    assert _promote(client, admin, product_id, white[1]).status_code == 200
    still = _listed(client, admin, sku)["cover_url"]
    assert still == f"products/{sku}-qora-1.jpg"
