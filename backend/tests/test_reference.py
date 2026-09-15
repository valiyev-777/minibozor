"""The two reference tables the card form picks from: colours and size systems.

Three things are being held down here, and only the first is CRUD.

**The palette is not a whitelist.** A colour on a variant that is not in the
table is still a colour, a receipt naming it still books goods in, and nothing
validates against the list. That is what makes it safe to ship against this
shop's existing data, which holds ``Siniy`` beside ``Ko'k``.

**One spelling means one row.** ``qora`` and ``Qora`` land on the same swatch
and the second cannot be written, or the picker offers two right answers and
the table has recreated the problem it was installed to remove.

**A merge renames strings and moves no stock.** The ledger names variant ids
and never a colour, so the assertion after a merge is that the placements
still equal the movements — the same invariant every other warehouse test
ends on.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import stock as st
from app.db import engine
from app.models import (
    Location,
    Product,
    ProductImage,
    ProductVariant,
    StockMovementKind,
)

API = "/api/v1"


# --------------------------------------------------------------------------- helpers


def _a_card(
    client: TestClient,
    admin: dict[str, str],
    *,
    sku: str,
    title: str = "Krossovka",
) -> int:
    made = client.post(
        f"{API}/admin/categories",
        json={"slug": "oyoq-kiyim", "name": "Oyoq kiyim", "icon": "shoe"},
        headers=admin,
    )
    assert made.status_code in (201, 409), made.text

    card = client.post(
        f"{API}/admin/products",
        json={
            "sku": sku,
            "title": title,
            "kind": "Krossovka",
            "category_slug": "oyoq-kiyim",
            "price": 290_000,
        },
        headers=admin,
    )
    assert card.status_code == 201, card.text
    return card.json()["id"]


def _variant(product_id: int, *, colour: str, size: str, hex_code: str = "") -> int:
    """One grid cell written straight on, because the grid door is not what is
    being tested and its shape is another agent's this wave."""
    with Session(engine) as session:
        row = ProductVariant(
            product_id=product_id,
            colour=colour,
            colour_hex=hex_code,
            size=size,
            sku=f"{product_id}-{colour}-{size}",
            barcode=f"MB{product_id}{colour}{size}",
            price=290_000,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


# --------------------------------------------------------------------------- the palette


def test_the_palette_is_seeded_in_uzbek_with_swatches(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Read by the bench, because the bench is where a colour is chosen."""
    answer = client.get(f"{API}/admin/colours", headers=warehouse)
    assert answer.status_code == 200, answer.text
    palette = answer.json()

    names = [row["name"] for row in palette]
    assert "Oq" in names and "Qora" in names and "Ko'k" in names
    assert "Sarg'ish melanj" in names, "§5.3's own example is not in the seed"
    # Every swatch is drawable, and drawable the same way.
    assert all(row["hex"].startswith("#") and len(row["hex"]) == 7 for row in palette)
    # Sorted, so the picker does not reorder itself between two renders.
    assert [row["sort"] for row in palette] == sorted(row["sort"] for row in palette)


def test_seeding_twice_writes_nothing_twice() -> None:
    """The seed is idempotent on the key, not on the name.

    A shop that already typed ``qora`` must not get a second row when the seed
    installs ``Qora`` — that is the duplicate this whole table exists to
    prevent, arriving by way of the fix for it.
    """
    from app.models import Colour, SizeSystem
    from app.seed import _seed_colours, _seed_size_systems

    with Session(engine) as session:
        before = len(session.exec(select(Colour)).all())
        systems_before = len(session.exec(select(SizeSystem)).all())
        assert _seed_colours(session) == 0
        assert _seed_size_systems(session) == 0
        assert len(session.exec(select(Colour)).all()) == before
        assert len(session.exec(select(SizeSystem)).all()) == systems_before


def test_a_new_colour_can_be_added_from_the_bench(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """"+ yangi rang" is pressed at `/qabul`, with a sack open.

    Guarded as a reader and not a writer on purpose: a warehouse that cannot
    add a colour mid-receipt types it into the nearest box that will take it,
    which is how the palette came to be needed.
    """
    made = client.post(
        f"{API}/admin/colours",
        json={"name": "shokolad", "hex": "#4a2c17"},
        headers=warehouse,
    )
    assert made.status_code == 201, made.text
    row = made.json()
    # Tidied on the way in, like every other learned word at the desk.
    assert row["name"] == "Shokolad"
    assert row["slug"] == "shokolad"
    assert row["variant_count"] == 0


def test_hex_is_normalised_rather_than_merely_accepted(
    client: TestClient, admin: dict[str, str]
) -> None:
    """``#FFF``, ``ffffff`` and ``#FFFFFF`` are one swatch, so they are one string."""
    made = client.post(
        f"{API}/admin/colours",
        json={"name": "Qor rang", "hex": "#FFF"},
        headers=admin,
    )
    assert made.status_code == 201, made.text
    assert made.json()["hex"] == "#ffffff"

    refused = client.post(
        f"{API}/admin/colours",
        json={"name": "Yolg'on rang", "hex": "qizil"},
        headers=admin,
    )
    assert refused.status_code == 422


def test_one_spelling_means_one_swatch(
    client: TestClient, admin: dict[str, str]
) -> None:
    """``QORA``, ``qora`` and ``Qora`` are the seeded row, and refused as new ones.

    Punctuation-blind too — ``to'q  qizil`` is ``To'q qizil`` — which is the
    same rule ``app.brands`` matches makes by, deliberately shared rather than
    written twice.
    """
    for spelling in ("QORA", "qora", "  Qora "):
        clash = client.post(
            f"{API}/admin/colours", json={"name": spelling}, headers=admin
        )
        assert clash.status_code == 409, spelling
        assert "qora" in clash.json()["detail"].lower()

    clash = client.post(
        f"{API}/admin/colours", json={"name": "to'q  qizil"}, headers=admin
    )
    assert clash.status_code == 409


def test_a_colour_outside_the_palette_still_works(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The palette is additive. Nothing validates a variant against it.

    ``Siniy`` is in this shop's live data and is not an Uzbek colour name, so
    it is not seeded — and a card wearing it must go on working exactly as it
    did, or shipping the palette breaks the catalogue it was meant to tidy.
    """
    product_id = _a_card(client, admin, sku="REF-OUTSIDE")
    _variant(product_id, colour="Siniy", size="42")

    with Session(engine) as session:
        rows = session.exec(
            select(ProductVariant).where(ProductVariant.product_id == product_id)
        ).all()
    assert [row.colour for row in rows] == ["Siniy"]

    # And the palette knows nothing about it, which is the point: it is a
    # valid colour that simply is not offered.
    palette = client.get(f"{API}/admin/colours", headers=admin).json()
    assert "Siniy" not in [row["name"] for row in palette]


def test_a_swatch_in_use_cannot_be_deleted_and_counts_every_spelling(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Counted on the key: a ``qora`` variant protects the ``Qora`` swatch.

    A delete that only saw the exact string would remove a colour thirty
    variants are wearing a variation of, and the picker would stop offering a
    colour the shop demonstrably sells.
    """
    product_id = _a_card(client, admin, sku="REF-INUSE")
    _variant(product_id, colour="qora", size="41")

    listed = client.get(f"{API}/admin/colours", headers=admin).json()
    black = next(row for row in listed if row["name"] == "Qora")
    assert black["variant_count"] >= 1
    assert "qora" in black["spellings"]

    refused = client.delete(f"{API}/admin/colours/{black['slug']}", headers=admin)
    assert refused.status_code == 409

    # One nothing is wearing goes cleanly.
    spare = client.post(
        f"{API}/admin/colours", json={"name": "Vaqtinchalik rang"}, headers=admin
    ).json()
    gone = client.delete(f"{API}/admin/colours/{spare['slug']}", headers=admin)
    assert gone.status_code == 200


def test_the_bench_may_add_a_colour_but_not_edit_or_delete_one(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Adding is additive and reversible; renaming moves a swatch under other
    people's cards, and that is the shop's vocabulary rather than this sack."""
    listed = client.get(f"{API}/admin/colours", headers=warehouse).json()
    slug = listed[0]["slug"]

    assert client.patch(
        f"{API}/admin/colours/{slug}", json={"name": "Boshqa"}, headers=warehouse
    ).status_code == 403
    assert client.delete(
        f"{API}/admin/colours/{slug}", headers=warehouse
    ).status_code == 403
    assert client.post(
        f"{API}/admin/colours/{slug}/merge", json={"into": "oq"}, headers=warehouse
    ).status_code == 403


def test_renaming_a_swatch_leaves_the_variants_alone(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A rename changes what the picker offers next, not what is already out there.

    The string on the variant is what the photographs, the past orders and the
    shelf map agree on; moving it is ``merge``, which is a different sentence.
    """
    made = client.post(
        f"{API}/admin/colours", json={"name": "Zangori", "hex": "#2a6f97"},
        headers=admin,
    ).json()
    product_id = _a_card(client, admin, sku="REF-RENAME")
    _variant(product_id, colour="Zangori", size="43")

    patched = client.patch(
        f"{API}/admin/colours/{made['slug']}",
        json={"name": "Moviy", "hex": "#1a5f87", "sort": 999},
        headers=admin,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "Moviy"

    with Session(engine) as session:
        row = session.exec(
            select(ProductVariant).where(ProductVariant.product_id == product_id)
        ).one()
    assert row.colour == "Zangori", "a rename must not rewrite the ledger's neighbours"


def test_merging_two_colours_renames_variants_and_photographs_and_moves_no_stock(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """The repair for the duplicate that is already in the data.

    ``Siniy`` beside ``Ko'k`` cannot be fixed by offering a list — that only
    stops the next one. The merge renames every variant **and every
    photograph**, because the publishing gate wants a picture per colour and
    renaming the variants alone would take it away.

    And the ledger is untouched: a movement names a variant id, so the
    placements still equal the movements afterwards, which is the invariant
    every warehouse test ends on.
    """
    loser = client.post(
        f"{API}/admin/colours", json={"name": "Siniy", "hex": "#1565c0"},
        headers=admin,
    ).json()
    winner = client.post(
        f"{API}/admin/colours", json={"name": "Moviy rang", "hex": "#1e88e5"},
        headers=admin,
    ).json()

    product_id = _a_card(client, admin, sku="REF-MERGE")
    variant_id = _variant(product_id, colour="Siniy", size="42", hex_code="#1565c0")

    with Session(engine) as session:
        session.add(
            ProductImage(
                product_id=product_id, colour="Siniy", url="/media/siniy.jpg", sort=0
            )
        )
        session.commit()
        qabul = session.exec(select(Location).where(Location.code == "QABUL")).one()
        st.move(
            session,
            variant=session.get(ProductVariant, variant_id),
            kind=StockMovementKind.RECEIPT,
            qty=5,
            to=qabul,
        )
        session.commit()
        before = st.on_hand(session, variant_id)

    merged = client.post(
        f"{API}/admin/colours/{loser['slug']}/merge",
        json={"into": winner["slug"]},
        headers=admin,
    )
    assert merged.status_code == 200, merged.text
    body = merged.json()
    # Every ``Siniy`` in the database, not only this test's: the suite shares
    # one database and the test above deliberately puts an unpalette'd
    # ``Siniy`` on a card, which is exactly the kind of row a merge is for.
    assert body["variants_moved"] >= 1
    assert body["images_moved"] >= 1

    with Session(engine) as session:
        assert not [
            row
            for row in session.exec(select(ProductVariant)).all()
            if row.colour.casefold() == "siniy"
        ]
        variant = session.get(ProductVariant, variant_id)
        assert variant.colour == "Moviy rang"
        # The swatch comes with the name, or the merged variants are drawn in
        # the colour of a row that no longer exists.
        assert variant.colour_hex == "#1e88e5"
        image = session.exec(
            select(ProductImage).where(ProductImage.product_id == product_id)
        ).one()
        assert image.colour == "Moviy rang"
        assert st.on_hand(session, variant_id) == before

    assert client.get(
        f"{API}/admin/colours/{loser['slug']}", headers=admin
    ).status_code in (404, 405)


def test_a_merge_that_would_collide_is_refused_rather_than_guessed(
    client: TestClient, admin: dict[str, str]
) -> None:
    """A card holding both colours at one size is two ledger rows.

    Joining those means joining two stocks, two placements and two barcodes,
    which is a decision somebody makes with the shelf in front of them — not
    something a vocabulary tidy-up does silently across forty cards. So the
    refusal names the cards.
    """
    first = client.post(
        f"{API}/admin/colours", json={"name": "Nilufar"}, headers=admin
    ).json()
    second = client.post(
        f"{API}/admin/colours", json={"name": "Lotos"}, headers=admin
    ).json()

    product_id = _a_card(client, admin, sku="REF-CLASH", title="Ikki rangli krossovka")
    _variant(product_id, colour="Nilufar", size="44")
    _variant(product_id, colour="Lotos", size="44")

    refused = client.post(
        f"{API}/admin/colours/{first['slug']}/merge",
        json={"into": second["slug"]},
        headers=admin,
    )
    assert refused.status_code == 409, refused.text
    assert "Ikki rangli krossovka" in refused.json()["detail"]

    itself = client.post(
        f"{API}/admin/colours/{first['slug']}/merge",
        json={"into": first["slug"]},
        headers=admin,
    )
    assert itself.status_code == 409


# --------------------------------------------------------------------------- the size systems


def test_the_seeded_size_systems_are_the_ones_the_brief_names(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Four for men's shoes, four for women's, the letters, and belts.

    One row per *scale* and not per family, because that is what a card has to
    name: a European 43 beside a UK 9 on one card is the thing this table
    exists to make impossible.
    """
    answer = client.get(f"{API}/admin/size-systems", headers=warehouse)
    assert answer.status_code == 200, answer.text
    systems = {row["slug"]: row for row in answer.json()}

    for slug in (
        "erkaklar-poyabzali-eur",
        "erkaklar-poyabzali-uk",
        "erkaklar-poyabzali-us",
        "erkaklar-poyabzali-rus",
        "ayollar-poyabzali-eur",
        "kiyim",
        "kamar",
    ):
        assert slug in systems, slug

    assert "43" in systems["erkaklar-poyabzali-eur"]["values"]
    assert systems["kiyim"]["values"][:5] == ["XS", "S", "M", "L", "XL"]
    # The grouping is data and not a display string split on a space, or the
    # first system called "Kamar" breaks the picker.
    assert systems["erkaklar-poyabzali-eur"]["family"] == "Erkaklar poyabzali"
    assert systems["erkaklar-poyabzali-eur"]["scale"] == "EUR"
    assert systems["kamar"]["scale"] == ""


def test_xl_and_lower_case_xl_are_one_value(
    client: TestClient, admin: dict[str, str]
) -> None:
    """§6.4, at this door too.

    The values are tidied by the same function every variant door runs, so the
    palette cannot be the one place in the system where ``xl`` and ``XL`` are
    two sizes — and a list typed with both is one size rather than a
    unique-constraint error thrown at whoever typed it.
    """
    made = client.post(
        f"{API}/admin/size-systems",
        json={
            "name": "Sinov kiyimi",
            "family": "Kiyim",
            "values": ["s", "S", "m", "xl", "XL", " l "],
        },
        headers=admin,
    )
    assert made.status_code == 201, made.text
    assert made.json()["values"] == ["S", "M", "XL", "L"]

    gone = client.delete(f"{API}/admin/size-systems/{made.json()['slug']}", headers=admin)
    assert gone.status_code == 200


def test_replacing_the_values_keeps_the_order_that_was_sent(
    client: TestClient, admin: dict[str, str]
) -> None:
    """The order is half the content — ``S M L`` reordered is a different answer.

    And dropping a value only stops it being *offered*: a variant already
    carrying it keeps its size and its barcode, because the list is what the
    form suggests and never a validator run against stock.
    """
    made = client.post(
        f"{API}/admin/size-systems",
        json={"name": "Qo'lqop", "values": ["7", "8", "9"]},
        headers=admin,
    ).json()

    patched = client.patch(
        f"{API}/admin/size-systems/{made['slug']}",
        json={"values": ["9", "8", "7", "10"], "scale": "EUR", "sort": 500},
        headers=admin,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["values"] == ["9", "8", "7", "10"]
    assert patched.json()["scale"] == "EUR"

    # Absent leaves the list alone; [] empties it.
    untouched = client.patch(
        f"{API}/admin/size-systems/{made['slug']}",
        json={"name": "Qo'lqop (qishki)"},
        headers=admin,
    ).json()
    assert untouched["values"] == ["9", "8", "7", "10"]

    emptied = client.patch(
        f"{API}/admin/size-systems/{made['slug']}", json={"values": []}, headers=admin
    ).json()
    assert emptied["values"] == []

    client.delete(f"{API}/admin/size-systems/{made['slug']}", headers=admin)


def test_a_size_system_is_the_admin_s_to_write(
    client: TestClient, warehouse: dict[str, str]
) -> None:
    """Read by the bench, written by the owner.

    Nothing about a sack on the table requires inventing a size system, and a
    bench that could would invent "Erkaklar poyabzali EUR" a second time under
    another name.
    """
    assert client.get(f"{API}/admin/size-systems", headers=warehouse).status_code == 200
    assert client.post(
        f"{API}/admin/size-systems", json={"name": "Yangi", "values": ["1"]},
        headers=warehouse,
    ).status_code == 403
    assert client.delete(
        f"{API}/admin/size-systems/kamar", headers=warehouse
    ).status_code == 403


def test_two_systems_cannot_share_a_name(
    client: TestClient, admin: dict[str, str]
) -> None:
    """Two rows called "Kiyim" is two answers to what sizes a shirt comes in."""
    clash = client.post(
        f"{API}/admin/size-systems", json={"name": "kiyim", "values": ["S"]},
        headers=admin,
    )
    assert clash.status_code == 409, clash.text
    assert "kiyim" in clash.json()["detail"].lower()


def test_a_card_names_its_system_and_null_means_sizeless(
    client: TestClient, admin: dict[str, str], warehouse: dict[str, str]
) -> None:
    """§6.3's either/or, in the one column that answers it.

    ``null`` is not "not filled in yet" — it is a cap, a bag, a thing with no
    size. And naming a system changes no variant: a card already carrying 41,
    42 and 43 goes on carrying them.
    """
    product_id = _a_card(client, admin, sku="REF-SYSTEM")
    _variant(product_id, colour="Oq", size="43")

    start = client.get(
        f"{API}/admin/products/{product_id}/size-system", headers=warehouse
    )
    assert start.status_code == 200, start.text
    assert start.json()["size_system"] is None

    # The bench sets it, because §5.4 opens this same form at /qabul.
    named = client.put(
        f"{API}/admin/products/{product_id}/size-system",
        json={"slug": "erkaklar-poyabzali-eur"},
        headers=warehouse,
    )
    assert named.status_code == 200, named.text
    assert named.json()["size_system"]["slug"] == "erkaklar-poyabzali-eur"
    assert "43" in named.json()["size_system"]["values"]

    with Session(engine) as session:
        row = session.exec(
            select(ProductVariant).where(ProductVariant.product_id == product_id)
        ).one()
        assert row.size == "43", "naming a system must not touch a variant"
        assert session.get(Product, product_id).size_system_id is not None

    # A system a card names cannot be deleted — the card would be sized in
    # nothing, which is neither sized nor sizeless.
    refused = client.delete(
        f"{API}/admin/size-systems/erkaklar-poyabzali-eur", headers=admin
    )
    assert refused.status_code == 409

    back = client.put(
        f"{API}/admin/products/{product_id}/size-system",
        json={"slug": None},
        headers=admin,
    )
    assert back.status_code == 200
    assert back.json()["size_system"] is None

    missing = client.put(
        f"{API}/admin/products/{product_id}/size-system",
        json={"slug": "yoq-bunday-tizim"},
        headers=admin,
    )
    assert missing.status_code == 404
