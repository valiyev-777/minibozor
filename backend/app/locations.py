"""The room: what places there are, what they are called, and how you walk it.

The old code knew how many of a thing there were and nothing at all about
where they stood, so "fetch two black 42s" was a question only somebody who
already knew the room could answer. This module is the part that was missing.

**The racks are data.** Three units of four columns by four rows is where the
owner starts, not where they end. ``RACKS`` below is a list the seed reads;
a fourth unit, or a second room, is a row in that list. Nothing here or
anywhere else writes 3, 4 or 48 as a number.

**The staging areas are places, not statuses.** ``QABUL`` is where goods stand
between the van and a shelf, and being in it *is* the unplaced state — which
can be counted, listed and alerted on in a way a boolean on a row cannot.

**A courier is a place too.** A parcel in a bag has not left the building's
books: it is at ``KURYER-7`` until somebody opens a door and takes it, and
until then it is findable.
"""

from __future__ import annotations

from sqlmodel import Session, col, select

from app.models import Location, LocationKind

# The shelf units, as data. (rack letter, columns, rows, capacity per cell).
#
# One model per cell is the working discipline — every colour and every size
# of it together — so a cell's capacity is counted in units of a shoe rather
# than in models. Sixty is what a cell of this size holds without a pile
# falling over; it is shown rather than enforced, because a cell that refuses
# the last pair at nine in the evening is a cell somebody works around.
RACKS: tuple[tuple[str, int, int, int], ...] = (
    ("A", 4, 4, 60),
    ("B", 4, 4, 60),
    ("C", 4, 4, 60),
)

# The areas with a job. Codes are Uzbek because the people reading them off a
# label are, and a code somebody has to translate in their head is a code they
# will write down wrong.
QABUL = "QABUL"        # off the van, not yet shelved
YIGIM = "YIGIM"        # picked for an order, waiting for a courier
BRAK = "BRAK"          # broken, not sellable
QAYTGAN = "QAYTGAN"    # came back from a customer, not yet inspected

STAGING: tuple[tuple[str, LocationKind, str], ...] = (
    (QABUL, LocationKind.RECEIVING, "Qabul qilingan, hali joylashtirilmagan"),
    (YIGIM, LocationKind.PACKING, "Buyurtma uchun terilgan, kuryerni kutmoqda"),
    (BRAK, LocationKind.DAMAGED, "Buzilgan — sotilmaydi"),
    (QAYTGAN, LocationKind.RETURNS, "Mijozdan qaytdi — hali ko'rilmagan"),
)

COURIER_PREFIX = "KURYER"


def cell_code(rack: str, column_no: int, row_no: int) -> str:
    """``A-01-01``. Two digits so the codes sort as they read."""
    return f"{rack}-{column_no:02d}-{row_no:02d}"


def courier_code(user_id: int) -> str:
    return f"{COURIER_PREFIX}-{user_id}"


def walk_order(location: Location) -> tuple[int, int, int, int]:
    """Where this place falls in one walk of the room, serpentine.

    Up one column and down the next — ``A-01-01 → A-01-02 → … → A-02-04 →
    A-02-03 → …`` — because a picker walking a rack does not return to the
    bottom of every column to start the next one. Odd columns run bottom to
    top and even ones top to bottom, which is what somebody actually does with
    a trolley.

    The staging areas sort first: goods that never reached a shelf are picked
    on the way past the receiving desk, before the racks begin.
    """
    if location.kind is not LocationKind.BIN:
        return (0, 0, 0, location.id or 0)

    rack = location.rack or ""
    column = location.column_no or 0
    row = location.row_no or 0
    down = column % 2 == 0
    return (1, ord(rack[0]) if rack else 0, column, -row if down else row)


def seed_locations(session: Session) -> int:
    """Write every place the room has, and say how many were new.

    Idempotent on the code, so running it again after a fourth rack is added
    to ``RACKS`` adds that rack and touches nothing else. Deliberately does
    not delete: a cell that disappeared from the list may still be holding
    something, and the honest way to retire one is ``POST
    /warehouse/cells/{code}/active``, which switches ``is_active`` off and
    leaves the row and its history where they are.

    A retired cell is not resurrected by a seed run either: its code is in
    ``existing``, so the loop steps over it. Being taken out of the room is a
    decision somebody made and it survives a deployment.
    """
    existing = {
        code
        for code in session.exec(select(Location.code)).all()
    }
    written = 0

    for code, kind, note in STAGING:
        if code in existing:
            continue
        session.add(Location(code=code, kind=kind, note=note))
        written += 1

    for rack, columns, rows, capacity in RACKS:
        for column_no in range(1, columns + 1):
            for row_no in range(1, rows + 1):
                code = cell_code(rack, column_no, row_no)
                if code in existing:
                    continue
                session.add(
                    Location(
                        code=code,
                        kind=LocationKind.BIN,
                        rack=rack,
                        column_no=column_no,
                        row_no=row_no,
                        capacity=capacity,
                    )
                )
                written += 1

    session.commit()
    return written


def by_code(session: Session, code: str) -> Location | None:
    """The place with this code, retired or not.

    Deliberately blind to ``is_active``: a code is a name and a retired cell
    still owns its name — the movements that named it have to resolve, the
    detail screen has to open it so somebody can decide to bring it back, and
    building a rack over the top of it has to see that the code is taken.

    It follows that a caller putting goods *somewhere* cannot use this alone.
    Arriving goods go through ``_open_cell`` in ``app.routers.warehouse``, and
    ``st.move`` refuses a retired destination whatever the caller checked.
    """
    return session.exec(
        select(Location).where(Location.code == code.strip().upper())
    ).first()


def staging(session: Session, code: str) -> Location:
    """One of the four areas, which the seed guarantees exists.

    Raises rather than creating one: a receiving area conjured up mid-request
    is a second ``QABUL`` on a database that was never seeded, and every count
    written into it would be invisible to the map.
    """
    row = by_code(session, code)
    if row is None:
        raise LookupError(
            f"location {code!r} is missing — run `python -m app.seed`"
        )
    return row


def for_courier(session: Session, user_id: int) -> Location:
    """The bag one courier is carrying, made the first time they carry one.

    Created on demand, unlike the staging areas: couriers are hired and leave,
    and seeding a place per person would mean a seed that has to be re-run
    whenever somebody joins.
    """
    code = courier_code(user_id)
    row = by_code(session, code)
    if row is None:
        row = Location(code=code, kind=LocationKind.COURIER, note=f"Kuryer #{user_id}")
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def cells(session: Session) -> list[Location]:
    """Every shelf cell the room still has, in walk order.

    Retired ones are left out, which is the whole point of the flag: a cell
    that was taken out of the building should not be planned into, printed a
    label for, or walked past by a picker. Whoever wants to *see* them — the
    map, drawing the hole and offering the way back — asks ``GET
    /warehouse/cells/retired``.
    """
    rows = session.exec(
        select(Location).where(
            Location.kind == LocationKind.BIN, col(Location.is_active).is_(True)
        )
    ).all()
    return sorted(rows, key=walk_order)
