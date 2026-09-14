"""Writing the audit trail.

One function, called from the endpoint that makes the change, in the same
session and therefore the same transaction: if the change rolls back the log
row goes with it, and there is no way to end up with a record of something
that never happened — or a change nobody recorded.

Reading them back is ``GET /admin/audit`` in ``app.routers.staff``, and it was
a long time coming: for a while thirty-eight places wrote rows here and
nothing anywhere read one, which made the table a write-only log and the
question it exists to answer a job for a database client on the server.
"""

from __future__ import annotations

from app.models import AuditLog, User


def _text(value: object) -> str | None:
    """A value as the log stores it: text, or nothing at all.

    ``None`` stays ``None`` — "this field had no value" and "this field held
    the string 'None'" are different statements about the past.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def record(
    session,
    *,
    action: str,
    entity: str,
    entity_id: int | None = None,
    actor: User | None = None,
    field: str = "",
    old: object = None,
    new: object = None,
    note: str = "",
) -> AuditLog:
    """Add one audit row to ``session``, without committing.

    The caller commits, along with the change being recorded::

        audit.record(
            session,
            actor=user,
            action="product.price",
            entity="product",
            entity_id=product.id,
            field="price",
            old=product.price,
            new=payload.price,
        )
        product.price = payload.price
        session.add(product)
        session.commit()
    """
    row = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        entity=entity,
        entity_id=entity_id,
        field=field,
        old_value=_text(old),
        new_value=_text(new),
        note=note,
    )
    session.add(row)
    return row
