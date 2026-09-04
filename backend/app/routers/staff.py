"""The backoffice, at its first endpoint.

Five interfaces will hang off this prefix — admin, seller, warehouse, operator,
courier — and they all begin the same way: the person has signed in through the
ordinary OTP flow and now needs to know which of the five they are looking at.
``/staff/me`` answers exactly that and nothing more.

The guards are the point of the file. ``StaffUser`` on an endpoint means "not a
customer"; ``AdminUser`` means one role only. Both come from ``require_role``
in ``app.deps``, so a new backoffice endpoint declares who may call it in its
signature rather than in a body check that is easy to forget.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import StaffUser
from app.schemas import StaffMeOut

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/me", response_model=StaffMeOut, summary="Which backoffice am I?")
def staff_me(user: StaffUser) -> StaffMeOut:
    return StaffMeOut(
        id=user.id,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
    )
