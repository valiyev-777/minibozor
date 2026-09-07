"""The shop window: banners, the home screen's rails, and promo codes.

None of this could be changed without a developer. A seasonal banner, the
order of the rails on the home screen, a promo code for a weekend — all of it
arrived through ``seed.py``, which meant the marketing calendar ran at the
speed of deployments.

Independent of the catalogue on purpose: nothing here creates or edits a card.
A rail points at a category and a banner points at whatever it likes, so this
is arrangement rather than content — which is why it is its own file and its
own screen.

Two decisions worth naming:

* **Order is set as a whole.** A screen where rows are dragged into place
  knows the final order and nothing else, so `.../order` takes the whole list.
  Setting `sort` one row at a time would cost a request per row and could be
  left half applied.
* **Nothing is deleted while it is in use.** A promo code that has been
  redeemed and a rail that is only out of season are switched off, not
  removed: the alternative is writing them again from memory next year.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app import audit, i18n
from app import schemas as s
from app.deps import AdminUser, SessionDep
from app.models import Banner, Category, HomeSection, PromoCode

router = APIRouter(prefix="/staff/showcase", tags=["staff"])


# --------------------------------------------------------------------------- banners


@router.get("/banners", response_model=list[s.AdminBannerOut])
def list_banners(user: AdminUser, session: SessionDep) -> list[s.AdminBannerOut]:
    rows = session.exec(
        select(Banner).order_by(col(Banner.sort), col(Banner.id))
    ).all()
    return [_banner_out(row) for row in rows]


@router.post(
    "/banners", response_model=s.AdminBannerOut, status_code=status.HTTP_201_CREATED
)
def create_banner(
    payload: s.BannerWriteIn, user: AdminUser, session: SessionDep
) -> s.AdminBannerOut:
    row = Banner(**payload.model_dump(), sort=_next_sort(session, Banner))
    session.add(row)
    session.commit()
    session.refresh(row)
    return _banner_out(row)


@router.patch("/banners/{banner_id}", response_model=s.AdminBannerOut)
def update_banner(
    banner_id: int, payload: s.BannerUpdateIn, user: AdminUser, session: SessionDep
) -> s.AdminBannerOut:
    row = session.get(Banner, banner_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("banner_not_found"))
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _banner_out(row)


@router.delete("/banners/{banner_id}", response_model=s.Message)
def delete_banner(banner_id: int, user: AdminUser, session: SessionDep) -> s.Message:
    row = session.get(Banner, banner_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("banner_not_found"))
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


@router.post(
    "/banners/order",
    response_model=list[s.AdminBannerOut],
    summary="Set the order of the banners, top to bottom",
)
def reorder_banners(
    payload: s.ReorderIn, user: AdminUser, session: SessionDep
) -> list[s.AdminBannerOut]:
    _reorder(session, Banner, payload.ids, "banner")
    return list_banners(user, session)


# --------------------------------------------------------------------------- rails


@router.get("/sections", response_model=list[s.AdminSectionOut])
def list_sections(user: AdminUser, session: SessionDep) -> list[s.AdminSectionOut]:
    rows = session.exec(
        select(HomeSection).order_by(col(HomeSection.sort), col(HomeSection.id))
    ).all()
    return [_section_out(row) for row in rows]


@router.post(
    "/sections", response_model=s.AdminSectionOut, status_code=status.HTTP_201_CREATED
)
def create_section(
    payload: s.SectionWriteIn, user: AdminUser, session: SessionDep
) -> s.AdminSectionOut:
    if session.exec(select(HomeSection).where(HomeSection.key == payload.key)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("slug_exists"))
    _check_category(session, payload.category_slug)
    row = HomeSection(**payload.model_dump(), sort=_next_sort(session, HomeSection))
    session.add(row)
    session.commit()
    session.refresh(row)
    return _section_out(row)


@router.patch("/sections/{key}", response_model=s.AdminSectionOut)
def update_section(
    key: str, payload: s.SectionUpdateIn, user: AdminUser, session: SessionDep
) -> s.AdminSectionOut:
    row = _section(session, key)
    if payload.category_slug is not None:
        _check_category(session, payload.category_slug)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _section_out(row)


@router.delete("/sections/{key}", response_model=s.Message)
def delete_section(key: str, user: AdminUser, session: SessionDep) -> s.Message:
    row = _section(session, key)
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


@router.post(
    "/sections/order",
    response_model=list[s.AdminSectionOut],
    summary="Set the order of the home screen's rails",
)
def reorder_sections(
    payload: s.ReorderIn, user: AdminUser, session: SessionDep
) -> list[s.AdminSectionOut]:
    _reorder(session, HomeSection, payload.ids, "home_section")
    return list_sections(user, session)


# --------------------------------------------------------------------------- promo codes


@router.get("/promos", response_model=list[s.AdminPromoOut])
def list_promos(user: AdminUser, session: SessionDep) -> list[s.AdminPromoOut]:
    rows = session.exec(select(PromoCode).order_by(col(PromoCode.code))).all()
    return [_promo_out(row) for row in rows]


@router.post(
    "/promos", response_model=s.AdminPromoOut, status_code=status.HTTP_201_CREATED
)
def create_promo(
    payload: s.PromoWriteIn, user: AdminUser, session: SessionDep
) -> s.AdminPromoOut:
    if session.exec(select(PromoCode).where(PromoCode.code == payload.code)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("promo_exists"))
    if not payload.percent_off and not payload.amount_off:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("promo_empty"))

    row = PromoCode(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    # A discount is money. Who created one, and how much of it, is logged.
    audit.record(
        session,
        actor=user,
        action="promo.create",
        entity="promo_code",
        entity_id=row.id,
        field="percent_off" if row.percent_off else "amount_off",
        old=None,
        new=row.percent_off or row.amount_off,
        note=row.code,
    )
    session.commit()
    return _promo_out(row)


@router.patch("/promos/{code}", response_model=s.AdminPromoOut)
def update_promo(
    code: str, payload: s.PromoUpdateIn, user: AdminUser, session: SessionDep
) -> s.AdminPromoOut:
    row = _promo(session, code)
    changes = payload.model_dump(exclude_none=True)
    for field, value in changes.items():
        if value != getattr(row, field):
            audit.record(
                session,
                actor=user,
                action=f"promo.{field}",
                entity="promo_code",
                entity_id=row.id,
                field=field,
                old=getattr(row, field),
                new=value,
                note=row.code,
            )
        setattr(row, field, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _promo_out(row)


@router.delete("/promos/{code}", response_model=s.Message)
def delete_promo(code: str, user: AdminUser, session: SessionDep) -> s.Message:
    """Refused for a code that has been used. Switch it off instead.

    An order that was discounted names the code it was discounted by, and
    deleting the row would leave that figure unexplainable.
    """
    from app.models import Order

    row = _promo(session, code)
    if session.exec(select(Order).where(Order.discount > 0)).first() and row.active:
        raise HTTPException(status.HTTP_409_CONFLICT, i18n.label("promo_in_use"))
    session.delete(row)
    session.commit()
    return s.Message(message=i18n.label("deleted"))


# --------------------------------------------------------------------------- helpers


def _next_sort(session: SessionDep, model) -> int:
    """New rows go at the bottom, where a person expects to find them."""
    rows = session.exec(select(model)).all()
    return max((row.sort for row in rows), default=-1) + 1


def _reorder(session: SessionDep, model, ids: list[int], entity: str) -> None:
    """Renumber `sort` to match the order given.

    Every row named has to exist and every row has to be named once: a partial
    list would leave the rest holding numbers that mean something else, which
    is the half-applied order this endpoint exists to avoid.
    """
    if len(set(ids)) != len(ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("order_repeats"))
    rows = {row.id: row for row in session.exec(select(model)).all()}
    if set(ids) != set(rows):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, i18n.label("order_incomplete"))
    for position, row_id in enumerate(ids):
        rows[row_id].sort = position
        session.add(rows[row_id])
    session.commit()


def _section(session: SessionDep, key: str) -> HomeSection:
    row = session.exec(select(HomeSection).where(HomeSection.key == key)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("section_not_found"))
    return row


def _promo(session: SessionDep, code: str) -> PromoCode:
    row = session.exec(
        select(PromoCode).where(PromoCode.code == code.strip().upper())
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("promo_not_found"))
    return row


def _check_category(session: SessionDep, slug: str | None) -> None:
    """A rail pointing at a category that is not there shows nothing at all."""
    if slug is None:
        return
    if not session.exec(select(Category).where(Category.slug == slug)).first():
        raise HTTPException(status.HTTP_404_NOT_FOUND, i18n.label("category_not_found"))


def _banner_out(row: Banner) -> s.AdminBannerOut:
    return s.AdminBannerOut(
        id=row.id,
        kicker=row.kicker,
        title=row.title,
        subtitle=row.subtitle,
        cta=row.cta,
        # The stored path, not the served URL: this is the field an editor
        # types back in, and handing them a host they did not write would make
        # the next save wrong.
        image_url=row.image_url,
        gradient_from=row.gradient_from,
        gradient_to=row.gradient_to,
        target_type=row.target_type,
        target_value=row.target_value,
        sort=row.sort,
        active=row.active,
    )


def _section_out(row: HomeSection) -> s.AdminSectionOut:
    return s.AdminSectionOut(
        id=row.id,
        key=row.key,
        title=row.title,
        subtitle=row.subtitle,
        category_slug=row.category_slug,
        layout=row.layout,
        sort=row.sort,
        active=row.active,
    )


def _promo_out(row: PromoCode) -> s.AdminPromoOut:
    return s.AdminPromoOut(
        id=row.id,
        code=row.code,
        percent_off=row.percent_off,
        amount_off=row.amount_off,
        min_total=row.min_total,
        active=row.active,
    )
