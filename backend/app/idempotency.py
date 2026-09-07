"""Making a repeated request harmless.

The courier's app works without a network. It queues what it cannot send and
sends it later — possibly twice, because a request that timed out may well
have arrived. So a repeat is the normal case here rather than a fault, and
every write in ``app.routers.courier`` is keyed.

What a key buys, exactly: the second arrival of the same request **does not
do the thing again**, and answers with what the first one answered. Not with a
fresh computation of the same shape — with the stored bytes. Recomputing could
give a different answer once the world has moved on, and the client asking is
entitled to the reply it never received rather than to today's news.

The expensive case is cash. A retried "delivered, 240 000 so'm at the door" is
a second sale off the shelf and a second 240 000 on the shift, and nobody
notices until a courier is accused of being short. Everything here exists for
that one sentence.

Three rules:

* **The key is required, not optional.** An optional key is a key some client
  forgets, and the failure is silent and financial. The header is
  ``Idempotency-Key``.
* **The body is hashed along with the key.** The same key carrying a different
  request is not a retry, it is a bug; replaying the first answer would hide
  it and lose the second request entirely, so it is refused.
* **The record commits with the work.** One transaction, so there is no window
  in which the thing happened and the key does not exist — which is the window
  a retry would walk straight into.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from fastapi import status as http
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import i18n
from app.models import IdempotencyRecord, User

# Long enough for a uuid with room to spare, short enough that a client
# cannot use the column as storage.
MAX_KEY = 80


def digest(payload: BaseModel | dict | None) -> str:
    """A stable fingerprint of the request body.

    Sorted keys, so two encodings of the same request hash the same — the app
    is not obliged to serialise its fields in any particular order.
    """
    if payload is None:
        body: Any = None
    elif isinstance(payload, BaseModel):
        body = payload.model_dump(mode="json")
    else:
        body = payload
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def replay(
    session: Session,
    user: User,
    key: str,
    endpoint: str,
    payload: BaseModel | dict | None,
) -> dict | None:
    """The answer we already gave, or ``None`` to go ahead and do the work.

    Refuses two things rather than guessing at them: a key that is too long or
    empty, and a key that has been used on this endpoint with a different
    body.
    """
    trimmed = (key or "").strip()
    if not trimmed or len(trimmed) > MAX_KEY:
        raise HTTPException(
            http.HTTP_400_BAD_REQUEST, i18n.label("idempotency_key_required")
        )

    row = session.exec(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user.id, IdempotencyRecord.key == trimmed
        )
    ).first()
    if row is None:
        return None

    if row.endpoint != endpoint or row.request_hash != digest(payload):
        # The same key on a different request. Replaying would answer the
        # wrong question and drop this one on the floor.
        raise HTTPException(
            http.HTTP_409_CONFLICT, i18n.label("idempotency_key_reused")
        )
    return json.loads(row.response) if row.response else {}


def keep(
    session: Session,
    user: User,
    key: str,
    endpoint: str,
    payload: BaseModel | dict | None,
    response: BaseModel | dict,
) -> None:
    """Remember what we answered. The caller commits, along with the work.

    Deliberately not committing here: the record and the thing it records have
    to land together or a crash between them leaves a delivery that a retry
    would make twice.
    """
    body = (
        response.model_dump(mode="json")
        if isinstance(response, BaseModel)
        else response
    )
    session.add(
        IdempotencyRecord(
            user_id=user.id,
            key=key.strip(),
            endpoint=endpoint,
            request_hash=digest(payload),
            response=json.dumps(body, ensure_ascii=False),
        )
    )


def commit(session: Session, user: User, key: str, endpoint: str) -> dict | None:
    """Commit the work and its key together, surviving a genuine race.

    Two copies of one queued request can arrive at once — a flaky connection
    retrying while the first attempt is still in flight. One of them wins the
    unique index and the other raises here; the loser did no harm, because the
    transaction it was in rolls back with it, and the right answer for it is
    the winner's answer.
    """
    try:
        session.commit()
        return None
    except IntegrityError:
        session.rollback()
        row = session.exec(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user.id,
                IdempotencyRecord.key == key.strip(),
                IdempotencyRecord.endpoint == endpoint,
            )
        ).first()
        if row is None:
            raise
        return json.loads(row.response) if row.response else {}
