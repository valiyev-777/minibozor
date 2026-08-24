from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app import schemas as s
from app.deps import SessionDep
from app.models import FaqItem, LegalDoc

router = APIRouter(tags=["content"])

LANGUAGES = [
    {"code": "uz", "label": "O'zbekcha", "native": "Lotin yozuvi"},
    {"code": "ru", "label": "Русский", "native": "Russian"},
    {"code": "en", "label": "English", "native": "United States"},
]

SUPPORT = {
    "phone": "1150",
    "telegram": "https://t.me/minibozor_support",
    "email": "yordam@minibozor.uz",
    "hours": "Har kuni 08:00–22:00",
}


@router.get("/help/faq", response_model=list[s.FaqOut], summary="Screen 45 — help centre")
def faq(session: SessionDep) -> list[s.FaqOut]:
    rows = session.exec(select(FaqItem).order_by(col(FaqItem.sort))).all()
    return [s.FaqOut(id=f.id, question=f.question, answer=f.answer) for f in rows]


@router.get("/help/support", response_model=dict[str, str])
def support() -> dict[str, str]:
    return SUPPORT


@router.get("/legal", response_model=list[s.LegalDocOut], summary="Screen 46 — terms and privacy")
def legal_docs(session: SessionDep) -> list[s.LegalDocOut]:
    rows = session.exec(select(LegalDoc).order_by(col(LegalDoc.sort))).all()
    return [
        s.LegalDocOut(slug=d.slug, icon=d.icon, title=d.title, meta=d.meta) for d in rows
    ]


@router.get("/legal/{slug}", response_model=s.LegalDocFullOut)
def legal_doc(slug: str, session: SessionDep) -> s.LegalDocFullOut:
    doc = session.exec(select(LegalDoc).where(LegalDoc.slug == slug)).first()
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hujjat topilmadi")
    return s.LegalDocFullOut(
        slug=doc.slug, icon=doc.icon, title=doc.title, meta=doc.meta, body=doc.body
    )


@router.get("/languages", response_model=list[dict[str, str]], summary="Screen 39 — languages")
def languages() -> list[dict[str, str]]:
    return LANGUAGES
