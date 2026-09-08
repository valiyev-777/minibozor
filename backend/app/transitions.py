"""What may follow what.

Several tables carry a status that the data model always allowed to move and
that nothing in the API could actually move: a return request stuck at
``submitted``, an order stuck at ``placed``. The endpoints that move them are
in ``app.routers.operations``; the rules they enforce are here, as maps, so
that "can a delivered order go back to packing" is answered by reading a table
rather than by reading a chain of ifs.

Every map is exhaustive over its enum. A status that appears as a key with an
empty set is a deliberate dead end, and a status missing from the keys is a
bug rather than a dead end — ``next_states`` treats the two the same on
purpose, but the tests below the maps assert the keys are complete.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status as http

from app import i18n
from app.models import (
    OrderStatus,
    PickupRunStatus,
    ProductStatus,
    ReturnStatus,
)

# An order goes forward, and may be called off while it has not been handed
# over. ``shipped`` used to be a one-way street to ``delivered`` on the
# reasoning that once goods are with a courier the way out is a delivery and
# then a return.
#
# Failed deliveries changed that. A courier who has knocked three times at a
# door nobody answers is not holding a delivery-then-return; they are holding
# goods that were never sold, and the honest end for that order is a
# cancellation, which puts the counts back. So ``shipped`` may now be
# cancelled — **by an operator**. The courier records attempts and never
# decides to give up: they are at one door with one refusal, and the person
# who can see three of them and phone the customer is somebody else.
#
# There is deliberately no ``failed`` status. A refusal at a door is an event,
# not a state of the order — the order is still on its way — and what a
# dispute needs is how many times and why, which is a list of
# ``DeliveryAttempt`` rows rather than a word.
ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PLACED: frozenset({OrderStatus.PACKING, OrderStatus.CANCELLED}),
    OrderStatus.PACKING: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.RETURNED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.RETURNED: frozenset(),
}

# A decision, then the money. ``approved`` is not the end of it: the customer
# has been told yes and is still waiting to be paid, and keeping the two apart
# is what makes "approved but never refunded" a question anyone can ask.
RETURN_TRANSITIONS: dict[ReturnStatus, frozenset[ReturnStatus]] = {
    ReturnStatus.SUBMITTED: frozenset({ReturnStatus.APPROVED, ReturnStatus.REJECTED}),
    ReturnStatus.APPROVED: frozenset({ReturnStatus.REFUNDED}),
    ReturnStatus.REJECTED: frozenset(),
    ReturnStatus.REFUNDED: frozenset(),
}

# A card's way into the shop, and out again.
#
# ``draft`` is ours and may go straight up; a seller's proposal lands in
# ``moderating`` and waits. A refusal is not a dead end — the seller fixes what
# was wrong and sends it back — but ``published`` never returns to a queue: a
# card in the shop is taken out by archiving it, which is a different act with
# a different consequence for the offers hanging off it.
PRODUCT_TRANSITIONS: dict[ProductStatus, frozenset[ProductStatus]] = {
    ProductStatus.DRAFT: frozenset(
        {ProductStatus.MODERATING, ProductStatus.PUBLISHED, ProductStatus.ARCHIVED}
    ),
    ProductStatus.MODERATING: frozenset(
        {ProductStatus.PUBLISHED, ProductStatus.REJECTED}
    ),
    ProductStatus.REJECTED: frozenset(
        {ProductStatus.MODERATING, ProductStatus.ARCHIVED}
    ),
    ProductStatus.PUBLISHED: frozenset({ProductStatus.ARCHIVED}),
    ProductStatus.ARCHIVED: frozenset({ProductStatus.DRAFT}),
}


# A round of collections from customers, out and back.
#
# ``collected`` and ``received`` are kept apart because they are two different
# people's claims: the courier says they have the goods, and the warehouse
# says they arrived. Collapsing them would make "the courier collected it and
# it never reached us" unsayable, which is the one case worth being able to
# say.
PICKUP_TRANSITIONS: dict[PickupRunStatus, frozenset[PickupRunStatus]] = {
    PickupRunStatus.OPEN: frozenset(
        {PickupRunStatus.COLLECTED, PickupRunStatus.CANCELLED}
    ),
    PickupRunStatus.COLLECTED: frozenset({PickupRunStatus.RECEIVED}),
    PickupRunStatus.RECEIVED: frozenset(),
    PickupRunStatus.CANCELLED: frozenset(),
}


def next_states(table: dict, current) -> list:
    """The moves open from ``current``, in the enum's own order.

    Handed to the backoffice so its buttons come from the rules rather than
    from a copy of the rules written again in the client.
    """
    allowed = table.get(current, frozenset())
    return [state for state in type(current) if state in allowed]


def ensure(table: dict, current, target) -> None:
    """Let a legal move through; refuse an illegal one with 409.

    409 rather than 400: the request is well formed and would have been fine a
    moment ago. What is wrong is the state of the thing, which is exactly what
    a conflict is.
    """
    if target not in table.get(current, frozenset()):
        raise HTTPException(
            http.HTTP_409_CONFLICT,
            i18n.label("bad_transition", from_=current.value, to=target.value),
        )
