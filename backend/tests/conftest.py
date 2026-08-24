from __future__ import annotations

import os

os.environ.setdefault("MB_DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("MB_ENV", "dev")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine, init_db
from app.main import app
from app.seed import reset, seed

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
def auth(client: TestClient) -> dict[str, str]:
    phone = "+998901234567"
    requested = client.post(f"{API}/auth/otp/request", json={"phone": phone}).json()
    tokens = client.post(
        f"{API}/auth/otp/verify", json={"phone": phone, "code": requested["dev_code"]}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}
