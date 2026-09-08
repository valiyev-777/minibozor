from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import i18n
from app.core.config import settings
from app.db import engine, head_revision, require_current_schema
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
    listings,
    media,
    merchandising,
    notifications,
    operations,
    orders,
    payouts,
    profile,
    search,
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
    notifications.router,
    profile.router,
    content.router,
    staff.router,
    media.router,
    operations.router,
    merchandising.router,
    listings.router,
    warehouse.router,
    admin.router,
    payouts.router,
    courier.router,
):
    app.include_router(router, prefix=API)


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict:
    """Is this process able to do its job — not merely running.

    It used to answer ``{"status": "ok"}`` from a function that touched
    nothing, which is the health check that lies. A process whose database has
    gone away, or whose credentials have expired, or which is pointed at a
    schema it does not expect, answers that identically to a healthy one; the
    only thing it proves is that uvicorn accepted the socket, and the socket
    was never in doubt.

    So it asks the database two cheap questions:

    * ``SELECT 1`` — the connection is real and the server answers. This also
      exercises the pool's ``pool_pre_ping``, so a stale socket is discovered
      here rather than by the next customer.
    * the stamped Alembic revision — one row from a one-row table. Startup
      refuses to run unless this matches, but a migration applied underneath a
      running process would not be noticed by anything else, and a service
      serving a schema it does not expect is worth knowing about before the
      first 500.

    **503 when either fails**, because the caller is a script or a load
    balancer that reads the status code and nothing else. A body that says
    "degraded" behind a 200 is a body nobody reads. `dev.sh status` and
    `docker`-style health checks both work off the code alone.

    Deliberately not: row counts, table lists, or anything that grows with the
    catalogue. This is polled, and a health check that gets slower as the shop
    gets bigger becomes the thing that takes the shop down.
    """
    detail: dict = {
        "reachable": False,
        "dialect": engine.dialect.name,
        "revision": None,
        "expected": None,
        "at_head": False,
    }
    started = time.perf_counter()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
            detail["reachable"] = True
            row = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchone()
            detail["revision"] = row[0] if row else None
    except Exception as error:
        # The class, not the message: a connection error's text can carry the
        # host, the user and occasionally the password.
        detail["error"] = type(error).__name__
    detail["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)

    try:
        detail["expected"] = head_revision()
    except Exception as error:                              # pragma: no cover
        detail["error"] = type(error).__name__
    detail["at_head"] = bool(
        detail["revision"] and detail["revision"] == detail["expected"]
    )

    healthy = detail["reachable"] and detail["at_head"]
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "unhealthy",
        "env": settings.env,
        "database": detail,
    }
