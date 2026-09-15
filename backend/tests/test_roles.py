"""The seller role is gone, and the doors it guarded answer accordingly.

`UserRole.SELLER` named a person this shop does not have: there is one shop,
and whoever photographs the goods is the person who sells them. These tests
hold the deletion at each layer it lived in — the enum, the seed and the
guards — so it cannot drift back through any one of them alone.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import seed
from app.db import engine
from app.models import STAFF_ROLES, User, UserRole

API = "/api/v1"


def test_the_enum_has_no_seller() -> None:
    assert not hasattr(UserRole, "SELLER")
    assert "seller" not in {role.value for role in UserRole}
    assert frozenset(
        {UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.COURIER}
    ) == STAFF_ROLES


def test_the_seed_writes_no_seller() -> None:
    # The module cannot even name the account any more...
    assert not hasattr(seed, "SELLER_PHONE")
    # ...and the seeded database holds nobody the enum cannot read back. On
    # SQLite a role column is plain text, so a stale 'SELLER' row would sit
    # there silently until its owner signed in as a 500 — this says it does
    # not.
    with Session(engine) as session:
        roles = {user.role for user in session.exec(select(User)).all()}
    assert roles <= set(UserRole)


def test_catalog_writes_refuse_the_bench_and_accept_the_owner(
    client: TestClient,
    admin: dict[str, str],
    warehouse: dict[str, str],
) -> None:
    """`CatalogWriter` is the admin's alone now.

    Writing a category was the seller's door. The bench keeps *reading* the
    vocabulary it files goods under — that is `CatalogReader`, asserted last —
    but what the shop window says is the owner's to write.
    """
    body = {"slug": "rollar-sinovi", "name": "Rollar sinovi"}
    refused = client.post(f"{API}/admin/categories", json=body, headers=warehouse)
    assert refused.status_code == 403, refused.text

    written = client.post(f"{API}/admin/categories", json=body, headers=admin)
    assert written.status_code == 201, written.text

    read = client.get(f"{API}/admin/categories", headers=warehouse)
    assert read.status_code == 200, read.text
    assert "rollar-sinovi" in {row["slug"] for row in read.json()}
