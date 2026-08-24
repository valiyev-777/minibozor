from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db import init_db
from app.routers import (
    auth,
    cards,
    cart,
    catalog,
    content,
    delivery,
    favorites,
    home,
    notifications,
    orders,
    profile,
    reviews,
    search,
)

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"

DESCRIPTION = """
API for the **Mini Bozor** marketplace apps (Android + iOS).

Endpoints are grouped the way the design is: each screen usually maps to one
request. Screen numbers from the design file are quoted in the summaries.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Mini Bozor API",
    version="0.1.0",
    description=DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

API = "/api/v1"
for router in (
    auth.router,
    home.router,
    catalog.router,
    search.router,
    cart.router,
    favorites.router,
    delivery.router,
    cards.router,
    orders.router,
    reviews.router,
    notifications.router,
    profile.router,
    content.router,
):
    app.include_router(router, prefix=API)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}
