"""What a fresh database needs before anybody can sign in.

**It does not seed a catalogue.** It used to: forty-seven screens' worth of
products, photographs, orders and reviews, so the design could be demoed
without a backing service. That shop was somebody's idea of a shop. This one
is a real one, and the owner types their own products in — a card invented
here would be a card somebody has to notice and delete, and a demo order is a
sale that never happened sitting in the same table as the ones that did.

So what is seeded is what cannot be typed in:

* **the room** — every shelf cell and every staging area, from the list in
  ``app.locations``. A cell is a physical fact about a building rather than
  something anybody enters on a screen, and a warehouse with no places in it
  cannot receive its first sack. Adding a fourth rack is a line in that list
  and a second run of this file;
* **the accounts**, one per role, because there is no way into an empty system
  otherwise and no second login to make one with;
* **the vocabulary a picker needs** — why an order was called off, why
  something came back. Both are lists the apps render and neither has a screen
  to write them from;
* **the palette and the size systems** — the colours and the runs of sizes the
  card form offers instead of a text box. A starting point rather than a rule:
  the admin edits them, and a shop that starts selling belts adds a row. They
  are here because the alternative is a form whose pickers are empty on day
  one, which is a form that teaches its first user to type.

Everything else starts empty. The categories, the brands, the cards and the
orders are all the shop's own, and the shop does not exist yet.

    python -m app.seed          # fill an empty database
    python -m app.seed --reset  # drop everything first
"""

from __future__ import annotations

import sys

# Aliased: `text` is a local name in the label rows below, and that is the
# right name there.
from sqlalchemy import text as sql_text
from sqlmodel import Session, SQLModel, delete, func, select

from app import colours
from app import locations as loc
from app import sizes
from app.core.security import hash_secret
from app.db import engine, require_current_schema
from app.models import (
    Banner,
    CancelReason,
    Colour,
    HomeSection,
    ReturnReason,
    SizeSystem,
    User,
    UserRole,
)
from app.seed_i18n import seed_translations

DEMO_PHONE = "+998901234567"
DEMO_PIN = "1234"

# One account per role. Each signs in the way every customer does — the SMS
# code, in dev the fixed one — so there is nothing here that could become a
# second way in.
ADMIN_PHONE = "+998900000001"
WAREHOUSE_PHONE = "+998900000002"
COURIER_PHONE = "+998900000003"

CANCEL_REASONS = [
    ("Fikrimdan qaytdim", False),
    ("Boshqa joydan arzon topdim", False),
    ("Yetkazish vaqti to'g'ri kelmadi", False),
    ("Xato tovar tanlagan edim", False),
    ("Boshqa sabab", True),
]

RETURN_REASONS = [
    ("O'lcham to'g'ri kelmadi", False),
    ("Sifati kutganimdek emas", False),
    ("Rasmga mos kelmadi", False),
    ("Nuqsonli yoki shikastlangan", True),
    ("Boshqa tovar keldi", True),
]

# The palette a clothes-and-shoes shop needs, in the words used at the counter
# — not a colour wheel. Names are Uzbek because the form is Uzbek; the shop's
# live data already holds `Siniy` beside `Ko'k`, which is exactly the split
# this list exists to stop happening again.
#
# The hex is the swatch and not the truth: a colour is chosen by looking at
# the goods, so the photograph wins the moment there is one. This is what the
# picker draws before there is.
COLOURS = [
    ("Oq", "#ffffff"),
    ("Sut rang", "#faf7f0"),
    ("Krem", "#fffdd0"),
    ("Bej", "#e8d9bf"),
    ("Qora", "#000000"),
    ("Kulrang", "#808080"),
    ("Kulrang melanj", "#b5b5b5"),
    ("Kumush", "#c0c0c0"),
    ("Oltin", "#d4af37"),
    ("Bronza", "#cd7f32"),
    ("Jigarrang", "#6f4e37"),
    ("To'q jigarrang", "#3e2723"),
    ("Xaki", "#78866b"),
    ("Qizil", "#e53935"),
    ("To'q qizil", "#8b0000"),
    ("Bordo", "#6d071a"),
    ("Pushti", "#f48fb1"),
    ("To'q pushti", "#d81b60"),
    ("To'q sariq", "#ef6c00"),
    ("Sariq", "#fdd835"),
    ("Sarg'ish", "#e8d98a"),
    ("Sarg'ish melanj", "#d8cfa8"),
    ("Yashil", "#2e7d32"),
    ("Och yashil", "#8bc34a"),
    ("To'q yashil", "#1b5e20"),
    ("Ko'k", "#1e88e5"),
    ("To'q ko'k", "#0d47a1"),
    ("Havorang", "#87ceeb"),
    ("Feruza", "#40e0d0"),
    ("Binafsha", "#8e24aa"),
    ("Siyohrang", "#283593"),
]

# `(slug, name, family, scale, values)`. One row per *scale*, because that is
# what a card has to name: a European 43 and a UK 9 on one card is the thing
# this table exists to make impossible, and a single "Erkaklar poyabzali" row
# would let both in again.
#
# The numbers are the ones this shop has actually been typing — 41, 42, 43 on
# trainers and S, M, L, XL on shirts — widened to the run a market stall
# carries rather than to the full international chart, which would be a
# picker nobody can scroll.
SIZE_SYSTEMS = [
    ("erkaklar-poyabzali-eur", "Erkaklar poyabzali EUR", "Erkaklar poyabzali", "EUR",
     ["39", "40", "41", "42", "43", "44", "45", "46", "47"]),
    ("erkaklar-poyabzali-uk", "Erkaklar poyabzali UK", "Erkaklar poyabzali", "UK",
     ["6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10", "10.5", "11", "12"]),
    ("erkaklar-poyabzali-us", "Erkaklar poyabzali US", "Erkaklar poyabzali", "US",
     ["7", "7.5", "8", "8.5", "9", "9.5", "10", "10.5", "11", "11.5", "12", "13"]),
    ("erkaklar-poyabzali-rus", "Erkaklar poyabzali RUS", "Erkaklar poyabzali", "RUS",
     ["40", "41", "42", "43", "44", "45", "46", "47"]),

    ("ayollar-poyabzali-eur", "Ayollar poyabzali EUR", "Ayollar poyabzali", "EUR",
     ["35", "36", "37", "38", "39", "40", "41"]),
    ("ayollar-poyabzali-uk", "Ayollar poyabzali UK", "Ayollar poyabzali", "UK",
     ["2.5", "3", "3.5", "4", "4.5", "5", "5.5", "6", "6.5", "7", "7.5", "8"]),
    ("ayollar-poyabzali-us", "Ayollar poyabzali US", "Ayollar poyabzali", "US",
     ["5", "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "9.5", "10"]),
    ("ayollar-poyabzali-rus", "Ayollar poyabzali RUS", "Ayollar poyabzali", "RUS",
     ["34", "35", "36", "37", "38", "39", "40", "41"]),

    ("kiyim", "Kiyim", "Kiyim", "",
     ["XS", "S", "M", "L", "XL", "XXL", "XXXL"]),
    # Uzum and the Russian-language labels on half the stock number clothing
    # 42-58, and the desk has typed both. Two systems rather than one mixed
    # list, for the same reason EUR and UK are two.
    ("kiyim-raqamli", "Kiyim (raqamli)", "Kiyim", "RUS",
     ["42", "44", "46", "48", "50", "52", "54", "56", "58"]),

    ("kamar", "Kamar", "Kamar", "",
     ["85", "90", "95", "100", "105", "110", "115", "120", "125", "130"]),
]


# --------------------------------------------------------------------------- runner


def reset(session: Session) -> None:
    """Empty every table, and put the id counters back where they started.

    On SQLite, ``DELETE`` is the whole job: the next rowid is ``max(rowid) + 1``
    and an empty table has no max, so ids begin at 1 again by themselves.

    On Postgres a sequence is an object in its own right and ``DELETE`` does
    not touch it. A second seed therefore numbered everything from where the
    first one stopped — same rows, same order, different ids — which is not a
    reset at all. Two freshly seeded databases that disagree about every
    primary key cannot be compared, and a fixture that says "reset" and leaves
    the counters running will mislead somebody later.

    ``TRUNCATE ... RESTART IDENTITY`` does both in one statement, and
    ``CASCADE`` saves ordering the tables by dependency. It is deliberately
    limited to the tables the models declare: ``alembic_version`` is not one of
    them and must survive, or the next thing to open this database would refuse
    to start.
    """
    tables = list(SQLModel.metadata.sorted_tables)
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        names = ", ".join(f'"{table.name}"' for table in tables)
        session.exec(sql_text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    else:
        for table in reversed(tables):
            session.exec(delete(table))
    session.commit()


def seed(session: Session) -> None:
    # The room first, and on its own terms: it is idempotent on the code, so
    # a database that already has accounts but has just grown a fourth rack
    # gets the new cells rather than being told there is nothing to do.
    places = loc.seed_locations(session)
    if places:
        print(f"Seeded {places} places — {len(loc.RACKS)} racks and the staging areas.")

    # The vocabulary the card form picks from, on the same terms as the room:
    # idempotent on the name, and therefore ahead of the "already seeded" gate
    # below. A shop that has been running for a month has accounts and no
    # palette, and that is exactly the database this has to reach.
    swatches = _seed_colours(session)
    systems = _seed_size_systems(session)
    if swatches or systems:
        print(f"Seeded {swatches} colours and {systems} size systems.")

    if session.exec(select(User)).first():
        print("Database already seeded — nothing to do. Use --reset to start over.")
        return

    users = _seed_users(session)
    _seed_home(session)
    _seed_reasons(session)
    session.commit()
    translated = seed_translations(session)

    print(f"Seeded {len(users)} accounts and {translated} translation rows (ru, en).")
    print(f"Customer: {DEMO_PHONE} · SMS code 123456 (dev) · PIN {DEMO_PIN}")
    print(f"Admin:     {ADMIN_PHONE} · SMS code 123456 (dev)")
    print(f"Warehouse: {WAREHOUSE_PHONE} · SMS code 123456 (dev)")
    print(f"Courier:   {COURIER_PHONE} · SMS code 123456 (dev)")


def _seed_colours(session: Session) -> int:
    """Write the palette, and say how many swatches were new.

    Idempotent **on the key** rather than on the name: a shop that already
    typed ``qora`` has a row the desk has been landing on for weeks, and
    writing ``Qora`` beside it would create the very duplicate the palette
    exists to prevent. So a colour already in the table is left exactly as it
    is — its hex too, because a hex somebody corrected is a decision and this
    file is not the place it gets undone.

    Deliberately does not delete. A colour taken out of the palette was taken
    out by somebody, and a deployment is not a reason to put it back.
    """
    existing = {row.key for row in session.exec(select(Colour)).all()}
    written = 0
    # Tens, so a shade can later be slotted in beside the colour it is a shade
    # of without renumbering the palette.
    sort = (
        int(session.exec(select(func.max(Colour.sort))).one() or 0) + 10
        if existing
        else 0
    )
    for name, hex_code in COLOURS:
        wanted = colours.key(name)
        if wanted in existing:
            continue
        session.add(
            Colour(
                slug=colours.free_slug(session, name),
                name=name,
                key=wanted,
                hex=hex_code,
                sort=sort,
            )
        )
        existing.add(wanted)
        written += 1
        sort += 10
    if written:
        session.commit()
    return written


def _seed_size_systems(session: Session) -> int:
    """Write the size systems and their values. Idempotent on the slug.

    A system already there keeps its values untouched, including values
    somebody added or removed by hand: the list is the shop's, and the seed's
    job is to give a new database a starting point rather than to hold every
    database to this file's opinion for ever.
    """
    existing = {row.slug for row in session.exec(select(SizeSystem)).all()}
    written = 0
    sort = (
        int(session.exec(select(func.max(SizeSystem.sort))).one() or 0) + 10
        if existing
        else 0
    )
    for slug, name, family, scale, values in SIZE_SYSTEMS:
        if slug in existing:
            continue
        row = SizeSystem(
            slug=slug, name=name, family=family, scale=scale, sort=sort
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        # Through the same tidying every variant door runs, so the palette can
        # never be the one place where `xl` and `XL` are two sizes (§6.4).
        sizes.replace_values(session, row.id, values)
        session.commit()
        written += 1
        sort += 10
    return written


def _seed_home(session: Session) -> None:
    """The shop window, as three rails that fill themselves.

    Nothing wrote a ``home_sections`` row: the merchandising endpoints went
    with the marketplace and nothing replaced them, so `GET /home` answered
    with no banners, no categories and **no sections** — and the phone drew a
    city, a search box and a blank screen. The design was not the problem; the
    feed was empty.

    So these three, and they need no maintenance because none of them names a
    category: what they select is "newest", "cheapest against its old price"
    and "most sold", which are answers the catalogue already has. A shop with
    four products has a full window and a shop with four hundred has a better
    one, and neither needs anybody to curate it.
    """
    if session.exec(select(HomeSection)).first() is None:
        _seed_rails(session)
    if session.exec(select(Banner)).first() is None:
        _seed_banners(session)


def _seed_banners(session: Session) -> None:
    """Four, and none of them needs a picture drawn for it.

    A banner is a gradient, four lines of type and a chip — the photograph
    beside it is 110dp of product shot, and `app/routers/home.py` fills it from
    whatever the banner points at. So these carry no `image_url` and never go
    stale: the first one shows whatever came off the van most recently.

    Two of the four say something about the shop rather than about a category —
    when it delivers, and that nothing is paid up front. On a shop this size
    those are the two questions a first-time customer actually has, and a
    banner is where they get answered without being asked.
    """
    for sort, (kicker, title, subtitle, cta, frm, to) in enumerate(
        [
            (
                "MINI BOZOR", "Yangi keldi",
                "Bozordan bugun kelgan tovarlar", "Ko'rish",
                "#14162A", "#0E7BF5",
            ),
            (
                "CHEGIRMA", "Eski narxidan arzon",
                "Narxi tushgan tovarlar", "Arzonlari",
                "#E23A6A", "#14162A",
            ),
            (
                "YETKAZIB BERISH", "Ertaga qo'lingizda",
                "Kuryer eshikkacha olib boradi", "Buyurtma berish",
                "#0E7BF5", "#14162A",
            ),
            (
                "TO'LOV", "Naqd yoki karta",
                "Eshikda to'laysiz — oldindan to'lov yo'q", "Xarid qilish",
                "#3A4050", "#0E0F12",
            ),
        ]
    ):
        session.add(
            Banner(
                kicker=kicker,
                title=title,
                subtitle=subtitle,
                cta=cta,
                image_url="",
                gradient_from=frm,
                gradient_to=to,
                target_type="category",
                target_value="",
                sort=sort,
            )
        )
    session.commit()


def _seed_rails(session: Session) -> None:

    for sort, (key, title, subtitle, layout, pick) in enumerate(
        [
            ("new", "Yangi keldi", "Bozordan hozir kelgan tovarlar", "rail", "new"),
            ("deals", "Chegirmada", "Eski narxidan arzon", "deals", "deals"),
            # Everything else, and the last thing on the page: a small shop
            # has no "most bought" worth the name, and a customer who has
            # scrolled this far is browsing rather than looking for something.
            ("all", "Barcha tovarlar", "Do'kondagi hamma narsa", "grid", "popular"),
        ]
    ):
        session.add(
            HomeSection(
                key=key,
                title=title,
                subtitle=subtitle,
                layout=layout,
                pick=pick,
                sort=sort,
            )
        )
    session.commit()


def _seed_users(session: Session) -> dict[str, User]:
    demo = User(
        phone=DEMO_PHONE,
        full_name="Aziz Toshmatov",
        pin_hash=hash_secret(DEMO_PIN),
    )
    admin = User(
        phone=ADMIN_PHONE,
        full_name="Mini Bozor administratori",
        role=UserRole.ADMIN,
    )
    warehouse = User(
        phone=WAREHOUSE_PHONE,
        full_name="Ombor xodimi",
        role=UserRole.WAREHOUSE,
    )
    courier = User(
        phone=COURIER_PHONE,
        full_name="Kuryer",
        role=UserRole.COURIER,
    )
    people = {
        "demo": demo,
        "admin": admin,
        "warehouse": warehouse,
        "courier": courier,
    }
    for user in people.values():
        session.add(user)
    session.commit()
    for user in people.values():
        session.refresh(user)
    return people


def _seed_reasons(session: Session) -> None:
    for sort, (label, comment) in enumerate(CANCEL_REASONS):
        session.add(CancelReason(label=label, sort=sort, requires_comment=comment))
    for sort, (label, comment) in enumerate(RETURN_REASONS):
        session.add(ReturnReason(label=label, sort=sort, requires_comment=comment))
    session.commit()


def main() -> None:
    require_current_schema()
    with Session(engine) as session:
        if "--reset" in sys.argv:
            reset(session)
        seed(session)


if __name__ == "__main__":
    main()
