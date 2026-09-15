"""The description is markup now, and two things follow from that.

§5.2 ·4 asks for a rich text description and says, in one sentence, that the
server stores HTML, sanitises on the way in, and keeps the plain text beside
it for search. The editor's own schema already refuses everything the phone
apps cannot draw — but the editor is not the door. ``PATCH
/admin/products/{id}`` takes JSON, and what it stores is rendered as markup by
two native apps. So the whitelist is asserted here, against the API, and not
only in the component.

The search half is the quieter of the two and the easier to ship broken: it
fails by returning nothing, which reads like "we do not sell that" rather than
like a bug.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.models import Product, ProductStatus
from app.richtext import clean, plain

API = "/api/v1"


def _card(client: TestClient, admin: dict[str, str], *, sku: str, description: str) -> int:
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
            "title": "Krossovka",
            "kind": "Krossovka",
            "category_slug": "oyoq-kiyim",
            "price": 290_000,
            "description": description,
        },
        headers=admin,
    )
    assert card.status_code == 201, card.text
    return card.json()["id"]


# --------------------------------------------------------------------------- the whitelist


def test_the_tags_the_apps_can_draw_survive() -> None:
    html = (
        "<p>Charm <strong>oyoq kiyim</strong>, <em>yengil</em></p>"
        "<h2>Tarkib</h2><ul><li>Charm</li><li>Rezina</li></ul><ol><li>Bir</li></ol>"
    )
    assert clean(html) == html


def test_a_tag_the_apps_cannot_draw_is_unwrapped_and_its_words_kept() -> None:
    # A table is somebody's prose in the wrong markup. The markup goes; losing
    # the words with it would be a worse answer than either.
    assert clean("<table><tr><td>Charm</td></tr></table>") == "Charm"


def test_a_script_goes_and_takes_its_body_with_it() -> None:
    # The one case where dropping the tag and keeping the text is wrong: it
    # turns a blocked script into visible gibberish on the product page.
    assert clean("<script>alert(1)</script><p>Xavfsiz</p>") == "<p>Xavfsiz</p>"
    assert clean("<style>p{color:red}</style><p>Matn</p>") == "<p>Matn</p>"


def test_every_attribute_is_dropped_not_filtered() -> None:
    # There is no `style`, `class` or `href` either app reads, so an attribute
    # that survives is at best dead weight and at worst an event handler.
    assert clean('<p onclick="x()" style="color:red" class="a">Salom</p>') == "<p>Salom</p>"
    assert clean('<a href="http://evil">bosing</a>') == "bosing"


def test_an_unclosed_tag_is_closed_and_a_stray_close_is_ignored() -> None:
    assert clean("<p>ochiq <em>yopilmagan") == "<p>ochiq <em>yopilmagan</em></p>"
    assert clean("yolg'iz</p>") == "yolg'iz"


def test_the_text_is_escaped_on_the_way_through() -> None:
    assert clean("<p>Narx < 100 & > 50</p>") == "<p>Narx &lt; 100 &amp; &gt; 50</p>"


# --------------------------------------------------------------------------- the words


def test_the_words_come_out_with_the_block_boundaries_as_spaces() -> None:
    # Without the boundary this is "CharmRezina" and a search for either misses.
    assert plain("<ul><li>Charm</li><li>Rezina</li></ul>") == "Charm Rezina"
    assert plain("<p>Bir</p><p>Ikki</p>") == "Bir Ikki"
    assert plain("Bir<br />Ikki") == "Bir Ikki"


def test_entities_come_back_as_characters_so_the_needle_matches() -> None:
    assert plain("<p>Narx &lt; 100 &amp; &gt; 50</p>") == "Narx < 100 & > 50"


def test_nothing_in_is_nothing_out() -> None:
    assert clean("") == "" and plain("") == ""


# --------------------------------------------------------------------------- the doors


def test_the_create_door_stores_clean_markup_and_the_words_beside_it(
    client: TestClient, admin: dict[str, str]
) -> None:
    card_id = _card(
        client,
        admin,
        sku="MB-RT-0001",
        description='<p onclick="x()">Charm <strong>krossovka</strong></p><script>alert(1)</script>',
    )
    got = client.get(f"{API}/admin/products/{card_id}", headers=admin)
    assert got.status_code == 200, got.text
    assert got.json()["description"] == "<p>Charm <strong>krossovka</strong></p>"


def test_the_update_door_cleans_too_because_it_is_the_one_the_editor_uses(
    client: TestClient, admin: dict[str, str]
) -> None:
    card_id = _card(client, admin, sku="MB-RT-0002", description="<p>Eski</p>")
    wrote = client.patch(
        f"{API}/admin/products/{card_id}",
        json={"description": '<h2 class="x">Yangi</h2><iframe src="http://evil"></iframe>'},
        headers=admin,
    )
    assert wrote.status_code == 200, wrote.text
    assert wrote.json()["description"] == "<h2>Yangi</h2>"


def test_the_shop_search_matches_a_word_in_the_description_not_a_tag(
    client: TestClient, admin: dict[str, str]
) -> None:
    card_id = _card(
        client,
        admin,
        sku="MB-RT-0003",
        description="<ul><li>Marokash charmi</li></ul>",
    )
    # Put it in the shop window directly. The publishing gates want a
    # photograph per colour (§6.6) and this test is about the needle, not the
    # gates — the same shortcut `test_reference` takes with the variant grid.
    with Session(engine) as session:
        card = session.get(Product, card_id)
        assert card is not None
        card.status = ProductStatus.ACTIVE
        session.add(card)
        session.commit()

    # The word is inside a list item, so it only matches once the search reads
    # the words rather than the markup.
    hit = client.get(f"{API}/products", params={"q": "marokash", "show_sold_out": True})
    assert hit.status_code == 200, hit.text
    assert card_id in [p["id"] for p in hit.json()["items"]]

    # And the tag name itself is not a product search term.
    miss = client.get(f"{API}/products", params={"q": "li", "show_sold_out": True})
    assert card_id not in [p["id"] for p in miss.json()["items"]]
