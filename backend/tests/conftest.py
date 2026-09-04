from __future__ import annotations

import os

os.environ.setdefault("MB_DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("MB_ENV", "dev")

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine, init_db
from app.main import app
from app.models import User, UserRole
from app.seed import ADMIN_PHONE, reset, seed

API = "/api/v1"


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    init_db()
    with Session(engine) as session:
        reset(session)
        seed(session)


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
def operator(
    staff: Callable[[UserRole, str], dict[str, str]],
) -> dict[str, str]:
    """The role that answers returns, moderates reviews and moves orders."""
    return staff(UserRole.OPERATOR, "+998900009001")


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
