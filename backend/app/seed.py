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
  to write them from.

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
from sqlmodel import Session, SQLModel, delete, select

from app import locations as loc
from app.core.security import hash_secret
from app.db import engine, require_current_schema
from app.models import (
    CancelReason,
    ReturnReason,
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
SELLER_PHONE = "+998900000004"
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

    if session.exec(select(User)).first():
        print("Database already seeded — nothing to do. Use --reset to start over.")
        return

    users = _seed_users(session)
    _seed_reasons(session)
    session.commit()
    translated = seed_translations(session)

    print(f"Seeded {len(users)} accounts and {translated} translation rows (ru, en).")
    print(f"Customer: {DEMO_PHONE} · SMS code 123456 (dev) · PIN {DEMO_PIN}")
    print(f"Admin:     {ADMIN_PHONE} · SMS code 123456 (dev)")
    print(f"Warehouse: {WAREHOUSE_PHONE} · SMS code 123456 (dev)")
    print(f"Seller:    {SELLER_PHONE} · SMS code 123456 (dev)")
    print(f"Courier:   {COURIER_PHONE} · SMS code 123456 (dev)")


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
    seller = User(
        phone=SELLER_PHONE,
        full_name="Sotuvchi",
        role=UserRole.SELLER,
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
        "seller": seller,
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
