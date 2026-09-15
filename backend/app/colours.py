"""The palette — one row per colour the shop sells, and how two rows become one.

The colour used to be a text box at the receiving desk, and a text box learns
typos: this shop's live database holds ``Oq``, ``Qora``, ``Ko'k`` **and**
``Siniy``, which is one blue written in two languages and counted as two
colours by every filter, every photograph group and the publishing gate that
wants a picture per colour. ``GET /warehouse/vocab`` hid the worst of it by
offering the most-used spelling as a chip, which is a plaster applied at
display time over rows that are still wrong underneath.

**The variant column does not change.** ``product_variants.colour`` goes on
holding the name as a string, and so do ``product_images.colour`` and every
order line. Making it a foreign key would rewrite the ledger's neighbours to
fix a problem that is entirely upstream of them — the problem is what gets
typed, and the cure is a list to pick from.

**The list is additive.** A colour on a variant that is not in this table is
still a colour; nothing validates against the palette and nothing refuses a
receipt because of it. §5.2's form offers **"+ yangi rang"**, which writes the
new colour in here so the next person picks it instead of retyping it.

**Matching is punctuation-blind and case-folded**, the same rule
``app.brands`` uses — ``to'q qizil``, ``To'q  Qizil`` and ``TO'Q-QIZIL`` are
one key. That is what makes "is this colour already in the palette" have one
answer rather than three.
"""

from __future__ import annotations

import re

from sqlmodel import Session, col, func, select

from app import audit, i18n
from app import brands
from app import products as pr
from app.models import Colour, Product, ProductImage, ProductVariant, User


def key(name: str) -> str:
    """The lookup key for a spelling.

    Deliberately the brand rule and not a second one that means to be the
    same: two flattening rules that drift apart is how ``On Cloud`` and
    ``To'q qizil`` end up obeying different notions of what a duplicate is.
    """
    return brands.key(name)


def by_spelling(session: Session, name: str) -> Colour | None:
    """The palette row this spelling means, or nothing."""
    wanted = key(name)
    if not wanted:
        return None
    return session.exec(select(Colour).where(Colour.key == wanted)).first()


def free_slug(session: Session, name: str) -> str:
    """A slug nobody is using, from the name somebody typed.

    Uzbek names transliterate to very little — ``To'q qizil`` gives ``to-q-qizil``
    and ``Feruza`` gives ``feruza`` — so the numbered fallback is not a corner
    case here. It is the ordinary outcome for two colours whose names differ
    only by an apostrophe.
    """
    stem = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "rang"
    slug = stem
    n = 2
    while session.exec(select(Colour).where(Colour.slug == slug)).first() is not None:
        slug = f"{stem}-{n}"
        n += 1
    return slug


def next_sort(session: Session) -> int:
    """Where a newly written colour goes: the end, with room after it.

    Gaps of ten, because the admin's next move after adding a colour is often
    to put it next to the one it is a shade of — and with consecutive integers
    that means renumbering the whole palette to insert one row.
    """
    last = session.exec(select(func.max(Colour.sort))).one()
    return int(last or 0) + 10


def named(session: Session, name: str, *, hex: str = "") -> Colour:
    """The palette row this spelling means, written if it is new. Commits.

    The "+ yangi rang" door. A colour the shop has never sold is typed once
    and is a swatch from then on, without anybody leaving the form — which is
    the only version of this that a receiving desk actually uses.
    """
    wanted = pr.tidy_label(name)
    found = by_spelling(session, wanted)
    if found is not None:
        # A row written before the tidying existed goes on lending its
        # spelling to every card titled from it, so the swatch reads `Qora`
        # and the card reads `qora`. Same key, so nothing that used to land
        # here stops landing here.
        if found.name != wanted and key(found.name) == key(wanted):
            found.name = wanted
            session.add(found)
            session.commit()
            session.refresh(found)
        return found

    row = Colour(
        slug=free_slug(session, wanted),
        name=wanted,
        key=key(wanted),
        hex=hex,
        sort=next_sort(session),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def spellings_in_use(session: Session) -> dict[str, list[tuple[str, int]]]:
    """Every colour string on a variant, grouped by key, with its count.

    The whole variant table has a handful of distinct colours, so this is one
    ``GROUP BY`` and not a scan — and it has to be done in Python rather than
    in SQL because the key is a regex over Unicode that SQLite cannot express.
    """
    found: dict[str, list[tuple[str, int]]] = {}
    for name, count in session.exec(
        select(ProductVariant.colour, func.count())
        .where(col(ProductVariant.colour) != "")
        .group_by(col(ProductVariant.colour))
    ).all():
        found.setdefault(key(name), []).append((name, int(count)))
    return found


def variant_count(session: Session, colour: Colour) -> int:
    """How many variants name this colour — the answer to "can this go".

    Counted on the **key** rather than on the exact string: the whole reason
    this table exists is that ``qora`` and ``Qora`` are one colour, and a
    delete that only noticed the exact spelling would happily remove the
    swatch that thirty variants are wearing a variation of.
    """
    return sum(
        count for _, count in spellings_in_use(session).get(colour.key, [])
    )


def merge(
    session: Session, *, actor: User | None, loser: Colour, winner: Colour
) -> tuple[int, int]:
    """Rename every ``loser`` variant and photograph to ``winner``. No commit.

    Returns ``(variants, images)``. This is the door that repairs the damage
    the palette exists to prevent: ``Siniy`` and ``Ko'k`` are already in this
    shop's data and no amount of picking from a list retroactively joins them.

    **It renames strings; it moves no stock.** A movement names a
    ``variant_id`` and a placement names ``(location, variant)`` — neither
    holds a colour — so every ledger row and every shelf figure is untouched
    and still balances afterwards. ``product_images.colour`` is renamed
    alongside, and it must be: the publishing gate wants a photograph *per
    colour*, and renaming the variants alone would leave every card in the
    merge suddenly missing a picture.

    **Order lines are left exactly as they are.** An ``OrderItem`` is a
    snapshot of what somebody bought, in the words the shop used that day;
    rewriting it would edit a sale after the fact to make a vocabulary tidy.

    The caller has already refused the case this cannot do — a card carrying
    both spellings — because joining those two variants means joining two
    stock ledgers, which is a decision and not a rename. See
    ``collisions``.
    """
    # The spellings the loser answers to are worked out first, and every row
    # is then fetched by an indexed ``IN`` on them. Doing it the other way —
    # loading the tables and testing ``key(row.colour)`` in Python — is fine
    # on a shop with four hundred cards and reads the whole catalogue on one
    # with forty thousand, for an operation that touches a handful of rows.
    # The key is a Unicode regex SQLite cannot express, so this is the only
    # way the database gets to do the filtering.
    spellings = _spellings(session, loser.key)

    variants = (
        session.exec(
            select(ProductVariant).where(col(ProductVariant.colour).in_(spellings))
        ).all()
        if spellings
        else []
    )
    for row in variants:
        row.colour = winner.name
        # The swatch comes with the name. Leaving the old hex would draw the
        # merged variants in the colour of a row that no longer exists.
        row.colour_hex = winner.hex
        session.add(row)

    # The photographs are keyed on their own colour strings, which need not be
    # the same set: a card can hold a `Siniy` picture and no `Siniy` variant.
    photo_spellings = _spellings(session, loser.key, model=ProductImage)
    images = (
        session.exec(
            select(ProductImage).where(col(ProductImage.colour).in_(photo_spellings))
        ).all()
        if photo_spellings
        else []
    )
    for row in images:
        row.colour = winner.name
        session.add(row)

    audit.record(
        session,
        actor=actor,
        action="colour.merge",
        entity="colour",
        entity_id=winner.id,
        field="colour",
        old=loser.name,
        new=winner.name,
        note=i18n.label(
            "colour_merged_note",
            loser=loser.name,
            winner=winner.name,
            variants=len(variants),
        ),
    )

    i18n.forget(session, "colour", loser.id)
    session.delete(loser)
    return len(variants), len(images)


def collisions(session: Session, *, loser: Colour, winner: Colour) -> list[str]:
    """Cards that hold both spellings at the same size — why a merge is refused.

    ``uq_variant_cell`` is ``(product_id, colour, size)``, so renaming the
    ``Siniy`` 42 to ``Ko'k`` on a card that already has a ``Ko'k`` 42 is two
    rows trying to be one. They may genuinely be one thing, but they are two
    rows in the ledger with two placements and two barcodes, and joining those
    is a stock decision somebody makes with the shelf in front of them — not
    something a vocabulary tidy-up should do silently on forty cards.

    So the merge names the cards and stops, and the answer is to deal with
    those variants first.
    """
    wanted = _spellings(session, loser.key) + _spellings(session, winner.key)
    if not wanted:
        return []

    theirs: set[tuple[int, str]] = set()
    mine: set[tuple[int, str]] = set()
    for row in session.exec(
        select(ProductVariant).where(col(ProductVariant.colour).in_(wanted))
    ).all():
        found = key(row.colour)
        if found == loser.key:
            theirs.add((row.product_id, row.size))
        elif found == winner.key:
            mine.add((row.product_id, row.size))

    clashing = {product_id for product_id, _ in theirs & mine}
    if not clashing:
        return []
    return [
        title
        for title in session.exec(
            select(Product.title).where(col(Product.id).in_(clashing))
        ).all()
    ]


def _spellings(
    session: Session,
    wanted: str,
    model: type[ProductVariant] | type[ProductImage] = ProductVariant,
) -> list[str]:
    """Every colour string in ``model`` that folds onto this key.

    The *distinct* colours in a catalogue are a handful whatever its size —
    this shop has four — so the ``DISTINCT`` is the cheap half and the Python
    that follows it runs over four rows rather than over the stock table.
    """
    return [
        name
        for name in session.exec(
            select(model.colour).where(col(model.colour) != "").distinct()
        ).all()
        if key(name) == wanted
    ]
