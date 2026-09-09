"""Russian and English for the rows the seed writes.

Written as data rather than as extra columns on every model: see
``app.models.Translation`` for why.

It used to carry the whole demo catalogue — titles, descriptions, banners,
spec keys, four hundred lines of it — and went when the catalogue did. What is
left is the two reason lists, which are seeded because no screen writes them
and which the apps render in whichever language the phone asked for. Anything
an admin types in afterwards is translated through ``/staff`` alongside the
row itself.

Anything missing here simply stays Uzbek; nothing breaks.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import (
    CancelReason,
    ReturnReason,
    Translation,
)

LANGS = ("ru", "en")

CANCEL_REASONS: dict[str, tuple[str, str]] = {
    "Fikrimdan qaytdim": ("Передумал(а)", "I changed my mind"),
    "Boshqa joydan arzon topdim": ("Нашёл(ла) дешевле в другом месте",
                                   "I found it cheaper elsewhere"),
    "Yetkazish vaqti to'g'ri kelmadi": ("Не подошло время доставки",
                                        "The delivery time didn't suit me"),
    "Xato tovar tanlagan edim": ("Выбрал(а) не тот товар", "I picked the wrong item"),
    "Boshqa sabab": ("Другая причина", "Another reason"),
}

RETURN_REASONS: dict[str, tuple[str, str]] = {
    "O'lcham to'g'ri kelmadi": ("Не подошёл размер", "The size didn't fit"),
    "Sifati kutganimdek emas": ("Качество не такое, как ожидал(а)",
                                "The quality wasn't what I expected"),
    "Rasmga mos kelmadi": ("Не соответствует фото", "It doesn't match the photo"),
    "Nuqsonli yoki shikastlangan": ("Бракованный или повреждённый",
                                    "Faulty or damaged"),
    "Boshqa tovar keldi": ("Пришёл другой товар", "The wrong item arrived"),
}


def _add(rows: list[Translation], entity: str, entity_id: int | None,
         field: str, values: tuple[str, str] | None) -> None:
    if entity_id is None or values is None:
        return
    for lang, value in zip(LANGS, values, strict=True):
        if value:
            rows.append(Translation(entity=entity, entity_id=entity_id,
                                    field=field, lang=lang, value=value))


def seed_translations(session: Session) -> int:
    """Replaces every translation row. Safe to re-run."""
    for existing in session.exec(select(Translation)).all():
        session.delete(existing)
    session.commit()

    rows: list[Translation] = []

    for reason in session.exec(select(CancelReason)).all():
        _add(rows, "cancel_reason", reason.id, "label", CANCEL_REASONS.get(reason.label))

    for reason in session.exec(select(ReturnReason)).all():
        _add(rows, "return_reason", reason.id, "label", RETURN_REASONS.get(reason.label))

    session.add_all(rows)
    session.commit()
    return len(rows)
