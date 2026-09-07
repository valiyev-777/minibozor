#!/usr/bin/env python3
"""A courier, a round, and a collection run — for developing against.

The backend's own `app.seed` builds a catalogue and a demo customer, and stops
there: nothing in it assigns anybody a delivery, because until this app existed
nothing read one. This puts a day's work in front of a courier so the screens
can be driven end to end, including the parts that only appear when there is no
network.

It writes to the database through the backend's own models rather than through
the API. Placing an order over HTTP means a cart, an address, a slot and a
checkout — four flows that have nothing to do with what is being tested — and
the round would still need an operator to assign it. Nothing here is imported
by the application; it is a fixture, and it lives in `courier/tools` rather
than in `backend/` because it belongs to this app's development loop.

    MB_DATABASE_URL=sqlite:///.../courier-dev.db \
    PYTHONPATH=../backend python3 tools/seed-round.py

Re-runnable: existing rows for the same courier are left alone and the round is
rebuilt from scratch.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

if "MB_DATABASE_URL" not in os.environ:
    sys.exit("Set MB_DATABASE_URL to the database the dev server is using.")

from sqlmodel import Session, delete, select  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.models import (  # noqa: E402
    AttemptResult,
    CourierShift,
    IdempotencyRecord,
    DeliveryAttempt,
    DeliveryKind,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PickupLine,
    PickupRun,
    PickupRunStatus,
    ReturnRequest,
    ReturnStatus,
    User,
    UserRole,
)

COURIER_PHONE = "+998900000007"

# Eleven stops would be a realistic day and an unreadable screenshot. Five, with
# the three cases that behave differently: cash at the door, already paid by
# card, and one that has been tried twice already.
ROUND = [
    {
        "code": "MB-104721",
        "address_line": "Chilonzor 9-kvartal, 24-uy, 37-xonadon",
        "address_meta": "2-podyezd, 5-qavat, domofon 37",
        "recipient_name": "Aziza Karimova",
        "recipient_phone": "+998901112233",
        "payment_method": PaymentMethod.CASH,
        "total": 240_000,
        "window": ("10:00", "12:00"),
        "items": [("Erkaklar ko'ylagi, oq", 1, 189_000), ("Paxtali paypoq, 3 juft", 1, 51_000)],
    },
    {
        "code": "MB-104722",
        "address_line": "Yunusobod 12-kvartal, 5-uy, 12-xonadon",
        "address_meta": "1-podyezd, 3-qavat",
        "recipient_name": "Sardor Aliyev",
        "recipient_phone": "+998902223344",
        "payment_method": PaymentMethod.CARD,
        "total": 1_090_000,
        "window": ("10:00", "12:00"),
        "items": [("Simsiz quloqchin", 1, 1_090_000)],
    },
    {
        "code": "MB-104723",
        "address_line": "Mirzo Ulug'bek, Buyuk Ipak Yo'li 145",
        "address_meta": "Ofis 4, 1-qavat",
        "recipient_name": "Nilufar Tosheva",
        "recipient_phone": "+998903334455",
        "payment_method": PaymentMethod.CASH,
        "total": 68_000,
        "window": ("12:00", "15:00"),
        "items": [("Termos, 500 ml", 1, 68_000)],
    },
    {
        "code": "MB-104724",
        "address_line": "Sergeli 7-kvartal, 3-uy, 61-xonadon",
        "address_meta": "Kirish hovlidan",
        "recipient_name": "Jasur Ergashev",
        "recipient_phone": "+998904445566",
        "payment_method": PaymentMethod.CASH,
        "total": 415_000,
        "window": ("15:00", "18:00"),
        "items": [("Choynak to'plami", 1, 415_000)],
        # Two failed attempts already: the screen has to show them before the
        # courier knocks.
        "attempts": 2,
    },
    {
        "code": "MB-104725",
        "address_line": "Shayxontohur, Navoiy ko'chasi 12",
        "address_meta": "",
        "recipient_name": "Kamola Yusupova",
        "recipient_phone": "+998905556677",
        "payment_method": PaymentMethod.CARD,
        "total": 329_000,
        "window": ("15:00", "18:00"),
        "items": [("Bolalar kurtkasi", 1, 329_000)],
    },
]


ATTEMPT_REASONS = ["Telefonni ko'tarmadi", "Uyda yo'q"]


def main() -> None:
    init_db()
    today = date.today()

    with Session(engine) as session:
        courier = session.exec(select(User).where(User.phone == COURIER_PHONE)).first()
        if courier is None:
            courier = User(phone=COURIER_PHONE, full_name="Bekzod Rahimov")
            session.add(courier)
        # Set every time: an account that lost the role mid-development is the
        # most confusing possible state to debug this app in.
        courier.role = UserRole.COURIER
        courier.is_active = True
        session.add(courier)
        session.commit()
        session.refresh(courier)

        customer = session.exec(
            select(User).where(User.role == UserRole.CUSTOMER)
        ).first()
        if customer is None:
            sys.exit("No customer in the database — run `python -m app.seed` first.")

        # A clean day: no half-open shift from the last run, no delivery
        # attempts, and no idempotency records — a key left over from a
        # previous fixture would replay yesterday's answer to today's request
        # and look like the queue misbehaving.
        session.exec(
            delete(CourierShift).where(CourierShift.courier_id == courier.id)
        )
        session.exec(
            delete(IdempotencyRecord).where(IdempotencyRecord.user_id == courier.id)
        )
        session.commit()

        # Rebuild the round rather than adding a second one on top of it.
        old = session.exec(select(Order).where(Order.courier_id == courier.id)).all()
        for order in old:
            session.exec(delete(OrderItem).where(OrderItem.order_id == order.id))
            session.exec(delete(DeliveryAttempt).where(DeliveryAttempt.order_id == order.id))
            requests = session.exec(
                select(ReturnRequest).where(ReturnRequest.order_id == order.id)
            ).all()
            for request in requests:
                session.exec(
                    delete(PickupLine).where(PickupLine.return_request_id == request.id)
                )
                session.delete(request)
            session.delete(order)
        for run in session.exec(
            select(PickupRun).where(PickupRun.courier_id == courier.id)
        ).all():
            session.exec(delete(PickupLine).where(PickupLine.run_id == run.id))
            session.delete(run)
        session.commit()

        orders: list[Order] = []
        for index, spec in enumerate(ROUND, start=1):
            start, end = spec["window"]
            order = Order(
                code=spec["code"],
                user_id=customer.id,
                # Shipped: on the van, which is the only status a courier can
                # act on. `failed` is not a status anywhere — an attempt is a
                # row, not a state.
                status=OrderStatus.SHIPPED,
                delivery_kind=DeliveryKind.COURIER,
                address_line=spec["address_line"],
                address_meta=spec["address_meta"],
                delivery_day=today,
                delivery_start=start,
                delivery_end=end,
                payment_method=spec["payment_method"],
                # A card order is paid before it leaves; a cash one becomes
                # paid at the door, which is what `cash_due` keys off.
                paid=spec["payment_method"] is PaymentMethod.CARD,
                recipient_name=spec["recipient_name"],
                recipient_phone=spec["recipient_phone"],
                courier_id=courier.id,
                courier_sequence=index,
                subtotal=spec["total"],
                total=spec["total"],
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            orders.append(order)

            # A door somebody has already knocked on twice. The detail screen
            # has to show that before the courier knocks a third time, and the
            # count comes from these rows rather than from a column.
            for note in ATTEMPT_REASONS[: spec.get("attempts", 0)]:
                session.add(
                    DeliveryAttempt(
                        order_id=order.id,
                        courier_id=courier.id,
                        result=AttemptResult.FAILED,
                        reason=note,
                    )
                )

            for title, quantity, price in spec["items"]:
                # No `product_id` and no `offer_id` on purpose. Delivering a
                # cash order calls `inventory.sell`, which moves stock for the
                # offer behind the line; a fixture has no business writing to
                # the stock ledger, and with no offer the call is a no-op.
                session.add(
                    OrderItem(
                        order_id=order.id,
                        title=title,
                        quantity=quantity,
                        price=price,
                        total=price * quantity,
                    )
                )
            session.commit()

        # One collection run: two approved returns from an older order.
        past = Order(
            code="MB-104690",
            user_id=customer.id,
            status=OrderStatus.DELIVERED,
            delivery_kind=DeliveryKind.COURIER,
            address_line="Chilonzor 9-kvartal, 24-uy, 37-xonadon",
            recipient_name="Aziza Karimova",
            recipient_phone="+998901112233",
            payment_method=PaymentMethod.CARD,
            paid=True,
            delivery_day=today - timedelta(days=6),
            courier_id=courier.id,
            courier_sequence=0,
            subtotal=430_000,
            total=430_000,
        )
        session.add(past)
        session.commit()
        session.refresh(past)

        requests = []
        for title, reason in (
            ("Ayollar poyabzali, 37", "O'lchami to'g'ri kelmadi"),
            ("Devor soati", "Yetib kelganda singan edi"),
        ):
            item = OrderItem(
                order_id=past.id, title=title, quantity=1, price=215_000, total=215_000
            )
            session.add(item)
            session.commit()
            session.refresh(item)
            request = ReturnRequest(
                user_id=customer.id,
                order_id=past.id,
                order_item_id=item.id,
                reason=reason,
                # Only an approved request goes on a run: one still being
                # decided is not something to send a van for.
                status=ReturnStatus.APPROVED,
            )
            session.add(request)
            session.commit()
            session.refresh(request)
            requests.append(request)

        run = PickupRun(
            code="PCK-000001", courier_id=courier.id, status=PickupRunStatus.OPEN
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        for request in requests:
            session.add(PickupLine(run_id=run.id, return_request_id=request.id))
        session.commit()

        print(f"Courier: {courier.full_name} · {courier.phone} · SMS 123456 (dev)")
        print(f"Round:   {len(orders)} stops, {sum(1 for s in ROUND if s['payment_method'] is PaymentMethod.CASH)} of them cash")
        print(f"Pickup:  {run.code}, {len(requests)} lines")


if __name__ == "__main__":
    main()
