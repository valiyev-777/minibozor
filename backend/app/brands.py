"""One row per make, whatever anybody typed — and how two rows become one.

The receiving desk names the make on the form, because two black trainers of
different makes are two cards: the make is part of the goods' identity rather
than a detail, and there is no vocabulary screen to keep up to date. Which
meant every novel spelling typed at nine in the evening became a permanent
``brands`` row — ``On Cloud``, ``on cloud``, ``ON-CLOUD``, three makes as far
as the catalogue's filters are concerned. ``GET /warehouse/vocab`` hid most of
the damage by showing only the most-used spelling, which is a plaster at
display time over rows that are still there underneath it.

**The lookup is an alias table, not the name column.** Matching
case-insensitively on ``brands.name`` — what the desk used to do — catches
``nike`` beside ``Nike`` and misses the case that actually bites. Correct
``On Cloud`` to ``On Running`` in the admin panel and the only spelling the
desk could match on has moved, so the very next sack typed as "On Cloud"
writes a second row: the correction is undone by the next receipt, and so is
a merge. So a brand answers to **every spelling it has ever answered to** —
its own name, the names it has been renamed away from, and the names of the
brands folded into it. A rename adds a spelling rather than replacing one,
which is the whole difference between a correction that holds and one that
lasts until the next van.

**The key is punctuation-blind, not word-blind.** ``on-cloud``, ``On  Cloud``
and ``ON CLOUD`` are one key; ``oncloud`` is a different one. Collapsing the
spaces as well would fold ``Red Wing`` into ``redwing`` — right — and would
equally fold together two makes that genuinely differ only by a space, which
is a guess that cannot be taken back once both makes' cards sit on one row.
Spelling that is really different is what ``POST /admin/brands/{slug}/merge``
is for, and that is a judgement a person makes once rather than a rule this
file applies to every receipt.

Every spelling belongs to at most one brand — the key is unique — so "which
row does this spelling mean" has exactly one answer and the desk never has to
choose between two right ones.
"""

from __future__ import annotations

import re

from sqlmodel import Session, col, func, select

from app import audit, i18n
from app import products as pr
from app.models import Brand, BrandAlias, Product, User


def key(name: str) -> str:
    """The lookup key for a spelling.

    Case folded — ``casefold`` and not ``lower``, because the catalogue holds
    Cyrillic and Turkish spellings and ``lower`` gets those wrong — with every
    run of punctuation, underscore or whitespace flattened to a single space.
    An empty answer means there was nothing there to name.
    """
    return " ".join(re.sub(r"[\W_]+", " ", name, flags=re.UNICODE).casefold().split())


def by_spelling(session: Session, name: str) -> Brand | None:
    """The brand this spelling belongs to, or nothing."""
    wanted = key(name)
    if not wanted:
        return None
    row = session.exec(select(BrandAlias).where(BrandAlias.key == wanted)).first()
    return session.get(Brand, row.brand_id) if row else None


def remember(session: Session, brand: Brand, name: str) -> bool:
    """Make ``brand`` answer to this spelling as well. Does not commit.

    Returns whether anything was added. A spelling already held by *another*
    brand is left where it is rather than stolen: it is somebody else's chip,
    the desk has been landing on that row for weeks, and silently repointing
    it would move goods onto a card nobody chose. The endpoints refuse the
    write that would need it and name the merge instead.
    """
    wanted = key(name)
    if not wanted:
        return False
    held = session.exec(select(BrandAlias).where(BrandAlias.key == wanted)).first()
    if held is not None:
        return False
    session.add(BrandAlias(brand_id=brand.id, name=pr.tidy_label(name), key=wanted))
    return True


def spellings(session: Session, brand_id: int) -> list[str]:
    """Every spelling this brand answers to, the current name first.

    What a merge screen reads. Not a similarity score and not a guess: these
    are the words people have actually typed at the desk, which is the only
    evidence there is that two rows are one make.
    """
    rows = session.exec(
        select(BrandAlias)
        .where(BrandAlias.brand_id == brand_id)
        .order_by(col(BrandAlias.id))
    ).all()
    return [row.name for row in rows]


def named(session: Session, name: str) -> Brand:
    """The brand this spelling means, written if it is new. Commits.

    The receiving desk's door. A make that has never been seen is typed once
    and is a chip from then on, without anybody leaving the form — which is
    the whole reason the brand is free text and not a picker.
    """
    wanted = pr.tidy_label(name)
    found = by_spelling(session, wanted)
    if found is not None:
        # Tidied in place on the way past. A row written as `nike` before the
        # tidying existed goes on lending its spelling to every card titled
        # from it, so the chip reads `Nike` and the card reads `nike`. The old
        # spelling stays in the alias table, so nothing that used to land here
        # stops landing here.
        if found.name != wanted and key(found.name) == key(wanted):
            found.name = wanted
            session.add(found)
        remember(session, found, wanted)
        session.commit()
        session.refresh(found)
        return found

    row = Brand(slug=free_slug(session, wanted), name=wanted)
    session.add(row)
    session.commit()
    session.refresh(row)
    remember(session, row, wanted)
    session.commit()
    session.refresh(row)
    return row


def free_slug(session: Session, name: str) -> str:
    """A slug nobody is using, from the name somebody typed."""
    stem = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "brend"
    slug = stem
    n = 2
    while session.exec(select(Brand).where(Brand.slug == slug)).first() is not None:
        slug = f"{stem}-{n}"
        n += 1
    return slug


def merge(session: Session, *, actor: User | None, loser: Brand, winner: Brand) -> int:
    """Fold ``loser`` into ``winner``. Returns how many cards moved. No commit.

    **Why this is an endpoint and not three of the ones that existed.**
    ``DELETE /admin/brands/{slug}`` refuses while any card names the brand,
    and nothing repoints a card's brand in bulk — so the only way to join two
    rows was to open every card, change its brand, and then delete. One
    transaction instead: the cards move, the spellings move, the loser goes.

    **Nothing downstream needs repairing, which is why this is safe.**
    ``Product`` carries the foreign key and no denormalised brand name, and
    ``OrderItem`` snapshots the product's *title* rather than its brand — so
    no order, no receipt and no report is rewritten by this, and none of them
    is wrong afterwards. ``GET /warehouse/vocab``, the catalogue's brand
    filters and the brand index all read the ``brands`` table live, so they
    are right on the next request without anything being cleared.

    **The loser's spellings come with it.** That is the point: they are the
    words that made the duplicate in the first place, and a merge that dropped
    them would be undone by the next sack typed the old way.

    **Translations: the winner wins, and the loser fills its gaps.** A Russian
    name on the row that survives is the one somebody chose for the row that
    survives, so it is not overwritten; a language the winner has nothing for
    takes the loser's rather than losing the work. Then the loser's are
    forgotten, because SQLite hands out a deleted row's id again and a brand
    created later at that id would arrive already translated under a dead
    one's name.
    """
    cards = session.exec(select(Product).where(Product.brand_id == loser.id)).all()
    for card in cards:
        card.brand_id = winner.id
        session.add(card)

    _inherit_translations(session, loser=loser, winner=winner)

    for alias in session.exec(
        select(BrandAlias).where(BrandAlias.brand_id == loser.id)
    ).all():
        # The winner may already answer to this exact spelling — two rows that
        # differ only by their slug, for instance. Then there is nothing to
        # move and the row goes with the loser.
        held = session.exec(
            select(BrandAlias).where(
                BrandAlias.key == alias.key, BrandAlias.brand_id == winner.id
            )
        ).first()
        if held is None:
            alias.brand_id = winner.id
            session.add(alias)
        else:
            session.delete(alias)

    audit.record(
        session,
        actor=actor,
        action="brand.merge",
        entity="brand",
        entity_id=winner.id,
        field="brand_id",
        old=loser.slug,
        new=winner.slug,
        note=i18n.label(
            "brand_merged_note",
            loser=loser.name,
            winner=winner.name,
            cards=len(cards),
        ),
    )

    i18n.forget(session, "brand", loser.id)
    session.delete(loser)
    return len(cards)


def _inherit_translations(session: Session, *, loser: Brand, winner: Brand) -> None:
    """Give the winner every language it has nothing of its own for."""
    from app.models import Translation

    theirs = session.exec(
        select(Translation).where(
            Translation.entity == "brand", Translation.entity_id == loser.id
        )
    ).all()
    if not theirs:
        return
    mine = {
        (row.lang, row.field)
        for row in session.exec(
            select(Translation).where(
                Translation.entity == "brand", Translation.entity_id == winner.id
            )
        ).all()
    }
    for row in theirs:
        if (row.lang, row.field) in mine:
            continue
        session.add(
            Translation(
                entity="brand",
                entity_id=winner.id,
                field=row.field,
                lang=row.lang,
                value=row.value,
            )
        )
    i18n.invalidate()


def card_count(session: Session, brand_id: int) -> int:
    """How many cards carry this brand — the answer to "can this be deleted"."""
    return int(
        session.exec(
            select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
        ).one()
    )
