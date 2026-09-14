"""Give somebody a role, so a panel has anybody to let in.

    .venv/bin/python -m tools.make_staff +998900000002 warehouse "Dilnoza Rasulova"
    .venv/bin/python -m tools.make_staff --list

Staff sign in through the same OTP flow customers use — the role is the only
difference — so this creates or updates a ``users`` row and nothing else.

The admin panel can now appoint people too, and this goes through the same
``roles.appoint`` it does. It used to write the row itself and no audit line
with it, so whether the shop could say who made somebody a courier depended on
which of the two doors the owner had used that day — and the shell was the
only door there was for the first year, which is to say for most of the staff.
The one difference the log keeps is the actor: nobody is signed in at a shell,
so the row names the system rather than a person.
"""

from __future__ import annotations

import sys

from pydantic import ValidationError
from sqlmodel import Session, select

from app import roles
from app.db import engine, require_current_schema
from app.models import User, UserRole
from app.schemas import PhoneIn


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

        # The same normalisation the sign-in flow applies, so `901234567`
        # here and `+998901234567` at the OTP screen are one account rather
        # than two, the second of which is the one they can sign in to.
        try:
            phone = PhoneIn(phone=phone).phone
        except ValidationError:
            print(f"{phone!r} is not an Uzbek mobile number.")
            raise SystemExit(1) from None

        user, created = roles.appoint(
            session,
            actor=None,
            phone=phone,
            role=role,
            full_name=full_name,
            note="make_staff",
        )
        session.commit()
        session.refresh(user)
        made = "new" if created else "updated"
        print(f"{user.phone} → {user.role.value}  ({user.full_name or 'nomsiz'}, {made})")

        print("Sign in with the SMS code — 123456 in dev.")


if __name__ == "__main__":
    main()
