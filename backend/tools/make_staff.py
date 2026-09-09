"""Give somebody a role, so a panel has anybody to let in.

    .venv/bin/python -m tools.make_staff +998900000002 warehouse "Dilnoza Rasulova"
    .venv/bin/python -m tools.make_staff --list

Staff sign in through the same OTP flow customers use — the role is the only
difference — so this creates or updates a ``users`` row and nothing else.
"""

from __future__ import annotations

import sys

from sqlmodel import Session, select

from app.db import engine, require_current_schema
from app.models import User, UserRole


def show(session: Session) -> None:
    rows = session.exec(select(User).where(User.role != UserRole.CUSTOMER)).all()
    if not rows:
        print("No staff yet.")
        return
    for user in sorted(rows, key=lambda u: u.role.value):
        print(f"{user.role.value:<10} {user.phone:<15} {user.full_name}")


def main() -> None:
    # Refuses on a database the models have moved past, rather than creating
    # tables to make itself work. Granting somebody the admin role against a
    # stale `users` table is how you end up with an account nobody can sign
    # in as.
    require_current_schema()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    with Session(engine) as session:
        if "--list" in sys.argv or not args:
            show(session)
            if not args:
                print("\nUsage: python -m tools.make_staff <phone> <role> [name]")
                print("Roles:", ", ".join(r.value for r in UserRole))
            return

        phone, role_name = args[0], args[1]
        full_name = args[2] if len(args) > 2 else ""
        try:
            role = UserRole(role_name)
        except ValueError:
            print(f"Unknown role {role_name!r}. One of:",
                  ", ".join(r.value for r in UserRole))
            raise SystemExit(1) from None

        user = session.exec(select(User).where(User.phone == phone)).first()
        if user is None:
            user = User(phone=phone, full_name=full_name, role=role)
        else:
            user.role = role
            if full_name:
                user.full_name = full_name
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"{user.phone} → {user.role.value}  ({user.full_name or 'nomsiz'})")

        print("Sign in with the SMS code — 123456 in dev.")


if __name__ == "__main__":
    main()
