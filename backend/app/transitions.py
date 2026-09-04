"""What may follow what.

Three of the tables carry a status that the data model always allowed to move
and that nothing in the API could actually move: a return request stuck at
``submitted``, a review stuck at ``moderating``, an order stuck at ``placed``.
The endpoints that move them are in ``app.routers.operations``; the rules they
enforce are here, as maps, so that "can a delivered order go back to packing"
is answered by reading a table rather than by reading a chain of ifs.

Every map is exhaustive over its enum. A status that appears as a key with an
empty set is a deliberate dead end, and a status missing from the keys is a
bug rather than a dead end — ``next_states`` treats the two the same on
purpose, but the tests below the maps assert the keys are complete.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status as http

from app import i18n
from app.models import OrderStatus, ProductStatus, ReturnStatus, ReviewStatus

# An order goes forward, and may be called off while nothing has left the
# building yet. Cancelling stops at ``packing`` for the same reason the
# customer's own cancel button does — once it is with a courier, the way out is
# a delivery and then a return, not a cancellation. A failed delivery wants a
# row of its own here one day; it is a new rule, not a missing one.
ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PLACED: frozenset({OrderStatus.PACKING, OrderStatus.CANCELLED}),
    OrderStatus.PACKING: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
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

# Moderation is not one-way: a published review can be taken down when
# somebody complains about it, and a refusal can be reversed on appeal. What
# is not allowed is a move to the state it is already in — that is somebody
# double-clicking, and it should be told so rather than silently rewriting the
# row and logging a change from a value to itself.
REVIEW_TRANSITIONS: dict[ReviewStatus, frozenset[ReviewStatus]] = {
    ReviewStatus.MODERATING: frozenset({ReviewStatus.PUBLISHED, ReviewStatus.REJECTED}),
    ReviewStatus.PUBLISHED: frozenset({ReviewStatus.REJECTED}),
    ReviewStatus.REJECTED: frozenset({ReviewStatus.PUBLISHED}),
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
