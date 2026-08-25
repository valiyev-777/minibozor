from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import i18n
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

@app.middleware("http")
async def language_middleware(request, call_next):
    """Pins the request to the language the app asked for.

    Set here rather than as a router dependency so it covers every endpoint,
    including ones added later, and so ``services.py`` can read it without
    taking a language argument in every function.
    """
    i18n.set_language(i18n.parse_accept_language(request.headers.get("accept-language")))
    response = await call_next(request)
    response.headers["Content-Language"] = i18n.current()
    # Caches must not serve a Russian body to an English client.
    response.headers["Vary"] = "Accept-Language"
    return response


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
