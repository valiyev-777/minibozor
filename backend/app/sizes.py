"""Named runs of sizes, so a European 43 never shares a card with a UK 9.

The receiving desk typed the size, which is fine for one shop selling one kind
of shoe and stops being fine the first time somebody books in a pair labelled
in UK numbers. Nothing on the card said which scale the numbers were in, so a
``9`` beside a ``43`` was two sizes of the same shoe as far as the grid, the
labels and the shelf map were concerned — and no later screen could tell them
apart, because the information was never written down.

So a card **names a system** (``products.size_system_id``) and the form offers
that system's values. The values themselves are ordinary strings on the
variant, exactly as before: nothing about the ledger changes, and a card whose
sizes predate this table goes on working with no system named.

**A system is not a validator.** It decides what the form *offers*. A size
already on a variant that is not in its system's list is not rejected and not
rewritten — the alternative is a migration that edits stock rows to match a
lookup table, which is the wrong way round.

**Sizeless stays sizeless.** No system means no sizes, which is what
``VocabOut.sizeless`` already reports and what §6.3 keeps as a single
either/or. There is deliberately no "sizeless system" row: that would make
sizelessness a thing you can be *and* have.
"""

from __future__ import annotations

import re

from sqlmodel import Session, col, func, select

from app import products as pr
from app.models import Product, SizeSystem, SizeValue


def tidy(value: str) -> str:
    """One spelling per size — the same function every variant door runs.

    Not a second rule that agrees with ``app.products.tidy_size`` today. §6.4
    says ``xl`` and ``XL`` are one size *at every door that writes a variant*,
    and a palette that tidied by its own rule would be the one door in the
    system where they are two.
    """
    return pr.tidy_size(value)


def free_slug(session: Session, name: str) -> str:
    """A slug nobody is using, from the name somebody typed."""
    stem = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "olcham"
    slug = stem
    n = 2
    while (
        session.exec(select(SizeSystem).where(SizeSystem.slug == slug)).first()
        is not None
    ):
        slug = f"{stem}-{n}"
        n += 1
    return slug


def next_sort(session: Session) -> int:
    """The end of the list, with room after it — see ``app.colours.next_sort``."""
    last = session.exec(select(func.max(SizeSystem.sort))).one()
    return int(last or 0) + 10


def values(session: Session, system_id: int) -> list[str]:
    """This system's sizes, in the order it says they go.

    By stored ``sort`` and not by ``pr.size_order``: a shop that sells belts in
    ``90 95 100`` and another that sells them in ``S M L`` both have an order,
    and only one of them is an order a function can work out.
    """
    return [
        row.value
        for row in session.exec(
            select(SizeValue)
            .where(SizeValue.system_id == system_id)
            .order_by(col(SizeValue.sort), col(SizeValue.id))
        ).all()
    ]


def replace_values(session: Session, system_id: int, wanted: list[str]) -> list[str]:
    """Make this system offer exactly these sizes, in this order. No commit.

    Rewritten wholesale rather than diffed, because the order is half the
    content: ``S M L XL`` reordered is a different answer to the same question
    and there is no sensible patch shape for "the third one moved". The rows
    carry nothing but the value and its place, so there is nothing to lose by
    replacing them — no stock, no barcode, no history hangs off a ``SizeValue``.

    Tidied and de-duplicated on the way in, so ``["xl", "XL"]`` is one size
    rather than a unique-constraint error thrown at whoever typed it.
    """
    tidied: list[str] = []
    for value in wanted:
        clean = tidy(value)
        if clean and clean not in tidied:
            tidied.append(clean)

    for row in session.exec(
        select(SizeValue).where(SizeValue.system_id == system_id)
    ).all():
        session.delete(row)
    # Flushed before the inserts, or `uq_size_value` sees the old rows and the
    # new ones in the same statement batch and refuses a value that is simply
    # staying where it was.
    session.flush()

    for sort, value in enumerate(tidied):
        session.add(SizeValue(system_id=system_id, value=value, sort=sort))
    return tidied


def card_count(session: Session, system_id: int) -> int:
    """How many cards name this system — the answer to "can this be deleted"."""
    return int(
        session.exec(
            select(func.count())
            .select_from(Product)
            .where(Product.size_system_id == system_id)
        ).one()
    )
