"""The five accounts a person needs to click through all five interfaces.

    .venv/bin/python -m tools.dev_accounts            # what it would do
    .venv/bin/python -m tools.dev_accounts --apply    # do it

The seed writes two accounts: a customer and an admin. Every other panel needs
a role the seed does not create — the operator who moves an order, the
warehouse that counts goods in, the courier who carries them, the seller who
prices them — so three of the five interfaces had nobody to let in and the
only way to find out was to sign in and be refused.

``tools.make_staff`` makes one at a time and is the right tool when you know
which one you want. This makes the whole set, with fixed numbers, so a
walkthrough can name them and `docs/walkthrough.md` does.

Idempotent, and additive: it creates a ``users`` row or corrects the role on
one that exists, and touches nothing else. It never deletes, never reseeds and
never changes the customer or the admin the seed wrote.

**Development only.** These are known phone numbers on an OTP flow whose code
is fixed at 123456, which is a set of publicly known credentials for whatever
they are pointed at. It refuses to run unless ``MB_ENV`` is ``dev``.
"""

from __future__ import annotations

import sys

from sqlmodel import Session, select

from app.core.config import settings
from app.db import engine, require_current_schema
from app.models import Seller, User, UserRole

# Phone numbers in a block nothing else uses, so they are recognisable in a
# list and cannot collide with the seed's own two.
ACCOUNTS: tuple[tuple[str, UserRole, str, str | None], ...] = (
    ("+998900000002", UserRole.OPERATOR,  "Dilnoza Rasulova", None),
    ("+998900000003", UserRole.WAREHOUSE, "Sardor Ismoilov",  None),
    ("+998900000004", UserRole.COURIER,   "Jasur Karimov",    None),
    # A seller is two rows: the account that signs in, and the shop it acts
    # for. Linking is what makes the cabinet answer anything at all — a seller
    # account with no `sellers` row is refused by every seller endpoint,
    # deliberately, because the alternative is showing them everybody's data.
    ("+998900000005", UserRole.SELLER,    "Anvar Qodirov",    "Chorsu Bozori"),
)


def plan(session: Session) -> list[str]:
    """What would change, in words, without changing it."""
    out: list[str] = []
    for phone, role, name, shop in ACCOUNTS:
        user = session.exec(select(User).where(User.phone == phone)).first()
        if user is None:
            out.append(f"create {phone}  {role.value:<10} {name}")
        elif user.role is not role:
            out.append(f"change {phone}  {user.role.value} → {role.value}  {name}")
        else:
            out.append(f"  keep {phone}  {role.value:<10} {name}")

        if shop:
            seller = session.exec(select(Seller).where(Seller.name == shop)).first()
            if seller is None:
                out.append(f"       └─ create seller {shop!r} and link it")
            elif user is None or seller.user_id != user.id:
                out.append(f"       └─ link seller {shop!r} to this account")
            else:
                out.append(f"       └─ seller {shop!r} already linked")
    return out


def apply(session: Session) -> None:
    for phone, role, name, shop in ACCOUNTS:
        user = session.exec(select(User).where(User.phone == phone)).first()
        if user is None:
            user = User(phone=phone, full_name=name, role=role)
        else:
            user.role = role
            user.full_name = user.full_name or name
        session.add(user)
        session.commit()
        session.refresh(user)

        if not shop:
            continue
        seller = session.exec(select(Seller).where(Seller.name == shop)).first()
        if seller is None:
            seller = Seller(name=shop, phone=phone)
        seller.user_id = user.id
        if seller.linked_at is None:
            from app.models import utcnow

            seller.linked_at = utcnow()
        session.add(seller)
        session.commit()


def main() -> int:
    if not settings.is_dev:
        print(
            f"MB_ENV is {settings.env!r}, not 'dev'. These are fixed phone "
            "numbers on a\nfixed OTP code — publicly known credentials — so "
            "they are development only.",
            file=sys.stderr,
        )
        return 2

    require_current_schema()
    doing = "--apply" in sys.argv

    with Session(engine) as session:
        print(f"database: {settings.database_url}")
        print(f"mode:     {'APPLY' if doing else 'dry run (pass --apply)'}\n")
        for line in plan(session):
            print(f"  {line}")
        if doing:
            apply(session)
            print("\napplied. Signing in, on every interface:\n")
            print("  role        phone            where")
            print("  admin       +998900000001    backoffice")
            for phone, role, _name, shop in ACCOUNTS:
                where = {
                    UserRole.OPERATOR: "backoffice",
                    UserRole.WAREHOUSE: "backoffice",
                    UserRole.COURIER: "courier PWA",
                    UserRole.SELLER: "seller cabinet",
                }.get(role, "")
                tail = f"  ({shop})" if shop else ""
                print(f"  {role.value:<11} {phone}    {where}{tail}")
            print("  customer    +998901234567    Android / iOS app")
            print("\n  SMS code 123456 on all of them. The shopper's PIN is 1234.")
        else:
            print("\n  nothing written. Add --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
