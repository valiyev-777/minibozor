from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

_connect_args: dict = {}
_kwargs: dict = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    if ":memory:" in settings.database_url:
        _kwargs["poolclass"] = StaticPool

engine = create_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
    **_kwargs,
)


def init_db() -> None:
    # Import for the side effect of registering every table on SQLModel.metadata.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
