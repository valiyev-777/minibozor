from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import i18n
from app.core.config import settings
from app.db import require_current_schema
from app.images import MEDIA_DIR
from app.routers import (
    admin,
    auth,
    cards,
    cart,
    catalog,
    content,
    courier,
    delivery,
    favorites,
    home,
    media,
    merchandising,
    notifications,
    operations,
    orders,
    payouts,
    profile,
    reviews,
    search,
    showcase,
    staff,
    warehouse,
)

DESCRIPTION = """
API for the **Mini Bozor** marketplace apps (Android + iOS).

Endpoints are grouped the way the design is: each screen usually maps to one
request. Screen numbers from the design file are quoted in the summaries.
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Check the schema; do not change it.

    This used to call ``init_db`` — ``SQLModel.metadata.create_all`` — which
    creates a table that is missing and never alters one that exists. So it
    was reassuring and almost useless: it silently agreed with any database
    whose tables happened to have the right names, whatever columns they had.

    It now refuses to start unless the database is at the newest revision, and
    it still does not migrate. Why the check and the migration are two
    different commands is written out in ``app.db.require_current_schema``;
    the short version is that several processes booting at once would run the
    same DDL against each other, and nobody chose three in the morning as the
    moment to change the schema.

    Migrations are run on purpose:

        .venv/bin/alembic upgrade head
    """
    require_current_schema()
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
    staff.router,
    media.router,
    operations.router,
    merchandising.router,
    warehouse.router,
    admin.router,
    payouts.router,
    showcase.router,
    courier.router,
):
    app.include_router(router, prefix=API)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}
