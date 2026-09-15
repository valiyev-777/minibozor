from __future__ import annotations

import os
import pathlib

# The database the suite runs against, **set** rather than defaulted.
#
# `setdefault` was a hole with a shop's catalogue at the bottom of it. It does
# nothing when the variable is already there, and in the api container it
# always is — compose sets `MB_DATABASE_URL=sqlite:///./minibozor.db`, which is
# the development database. So `docker exec minibozor_api pytest` ran the whole
# suite against the live one, and the fixture below **deletes the file it is
# given** before rebuilding it from `create_all` and the seed. One command, and
# the catalogue, the orders, the staff and every audit row were replaced by
# fixtures, with the running server left reading a deleted inode and answering
# `database disk image is malformed`.
#
# So the suite names its own database and overwrites whatever it was handed.
# Pointing it somewhere else — Postgres, a file in /tmp — is `MB_TEST_DATABASE_URL`,
# a variable nothing else in the system reads and which therefore cannot
# already be set by the thing you are testing.
os.environ["MB_DATABASE_URL"] = os.environ.get(
    "MB_TEST_DATABASE_URL", "sqlite:///./test.db"
)
os.environ["MB_ENV"] = "dev"

# And the belt to that pair of braces. The name is the application's own
# default, so it is the one database on the machine that is certainly somebody's
# work rather than a fixture — and this file's whole job is to delete what it is
# pointed at.
if "minibozor.db" in os.environ["MB_DATABASE_URL"]:
    raise RuntimeError(
        "The suite deletes the database it is given, and MB_TEST_DATABASE_URL "
        "points at minibozor.db — the development database. Refusing to run."
    )

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine, init_db, stamp_head
from app.main import app
from app.models import User, UserRole
from app.seed import ADMIN_PHONE, reset, seed

API = "/api/v1"


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Built by ``create_all``, then stamped at head.

    ``create_all`` rather than ``alembic upgrade head`` because this runs once
    per suite and issues one CREATE TABLE per table instead of replaying the
    migration history — the suite is slow enough already. That is only
    defensible because ``test_schema.py`` holds the two builders to producing
    the identical schema, so what the tests run against is what a migrated
    database is. Without that test this shortcut would be the exact hole the
    migration system was installed to close.

    Stamped because the application refuses to start against a database with
    no version row, and ``TestClient(app)`` runs the real lifespan. The stamp
    is not a way round the check: this database genuinely holds what the
    baseline builds, and the test next door is what says so.

    **The file is deleted first.** ``create_all`` creates a table that is
    missing and never alters one that exists, so a column added to a table
    already in ``test.db`` simply never appeared — and the suite then failed
    with ``no such column`` a hundred times over, from a stale file rather
    than from anything in the change. Starting from nothing is a second of
    CREATE TABLEs and removes the whole class of confusion.
    """
    url = os.environ["MB_DATABASE_URL"]
    if url.startswith("sqlite:///"):
        stale = pathlib.Path(url.removeprefix("sqlite:///"))
        stale.unlink(missing_ok=True)

    init_db()
    stamp_head()
    with Session(engine) as session:
        reset(session)
        seed(session)


COURIER_PHONE = "+998900009009"


@pytest.fixture(scope="session", autouse=True)
def a_courier(database: None) -> None:
    """One courier the whole suite can hand an order to.

    An order may not be shipped with nobody named on it — a shipped order with
    no courier is on nobody's round, reads as "on its way" to the customer and
    the office, and is invisible to every courier. That rule means every test
    that ships something needs a courier to exist, and creating one per test
    would be a fixture in fifty signatures.

    Its own number, not one a test might also pick, so a test asserting one
    courier's round cannot collide with this one.
    """
    with Session(engine) as session:
        if session.exec(select(User).where(User.phone == COURIER_PHONE)).first():
            return
        session.add(
            User(phone=COURIER_PHONE, full_name="Kuryer (test)", role=UserRole.COURIER)
        )
        session.commit()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sign_in(client: TestClient) -> Callable[[str], dict[str, str]]:
    """Auth headers for a phone number, through the ordinary OTP flow.

    Staff use this too — there is one way in, and the role is the only thing
    that differs afterwards.
    """

    def go(phone: str) -> dict[str, str]:
        requested = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
        tokens = client.post(
            f"{API}/auth/otp/verify", json={"phone": phone, "code": requested["dev_code"]}
        ).json()
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    return go


@pytest.fixture
def auth(sign_in: Callable[[str], dict[str, str]]) -> dict[str, str]:
    return sign_in("+998901234567")


@pytest.fixture
def admin(sign_in: Callable[[str], dict[str, str]]) -> dict[str, str]:
    """The admin the seed writes, signed in like anybody else."""
    return sign_in(ADMIN_PHONE)


@pytest.fixture
def warehouse(
    staff: Callable[[UserRole, str], dict[str, str]],
) -> dict[str, str]:
    """The bench: receiving, putaway, picking, counts."""
    return staff(UserRole.WAREHOUSE, "+998900009002")


@pytest.fixture
def staff(
    sign_in: Callable[[str], dict[str, str]],
) -> Callable[[UserRole, str], dict[str, str]]:
    """Auth headers for a new user holding ``role``.

    Signing a fresh number in creates a customer, as it should; the role is
    then set the way an admin would set it, which is the only step that turns
    somebody into staff.
    """

    def go(role: UserRole, phone: str) -> dict[str, str]:
        headers = sign_in(phone)
        with Session(engine) as session:
            user = session.exec(select(User).where(User.phone == phone)).one()
            user.role = role
            session.add(user)
            session.commit()
        return headers

    return go
