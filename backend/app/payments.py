"""Taking money for an order.

**This module is the whole of the payment provider.** Nothing else in the app
knows how a card is charged: routers ask [charge] for a decision and act on
what comes back. Click, Payme or Stripe replaces this file and nothing else —
which is the only reason it is worth having a file for something that, today,
decides the answer from four digits.

What exists today is a *test* processor, and it says so out loud: it refuses to
run outside development. A shop that cannot take money and pretends it can is
worse than a shop that says it cannot, because the first one ships and the
second one does not — so `charge` raises in production rather than approving
anything, and the order is never created.

**The test cards.** The processor has no PAN to look at — by the time a charge
happens the number is long gone and all that is left is the token and the four
digits a person reads off their own card — so the outcome is chosen by those
four digits, the way every sandbox in the trade does it:

| last four | what happens |
|---|---|
| `0000` | the bank declines it |
| `0001` | not enough money on the card |
| `0002` | the card has expired |
| anything else | paid |

So `8600 0000 0000 0000` is a card that never works and `8600 1234 5678 9012`
is a card that always does. Both pass Luhn on the handset, which is the point:
the failures have to be reachable from the app's own form.

**A real provider changes the shape of this, not just its contents.** Click and
Payme confirm asynchronously — an invoice is created, the customer authorises
it in their bank's app, and a callback arrives some seconds later. When that
lands, `charge` grows a "pending" outcome and the order gets a state to sit in
while it waits. It does not have one now because nothing here is ever pending,
and inventing the state before the provider exists would be inventing which
of the several possible shapes it takes.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.core.config import settings
from app.models import PaymentCard

#: What the app sends instead of a real token until an SDK is wired up. The
#: Android form builds it in ``AddCardViewModel``; both sides name it here so
#: the pair is findable from either end.
DEV_TOKEN_PREFIX = "dev_tok_"


@dataclass(frozen=True)
class Charge:
    """The processor's answer, in the two facts a caller needs.

    ``reason`` is an i18n label key rather than a sentence: the customer reads
    this in their own language and the router is not the place to pick it.
    """

    ok: bool
    reference: str = ""
    reason: str = ""


#: The four digits that make the test processor fail, and how.
DECLINES: dict[str, str] = {
    "0000": "card_declined",
    "0001": "card_no_funds",
    "0002": "card_expired",
}


class PaymentsNotConfigured(RuntimeError):
    """No processor is wired up, and this is not a development machine."""


def charge(card: PaymentCard, amount: int) -> Charge:
    """Take [amount] tiyin-free so'm off [card], or say why not.

    Called once, inside the transaction that creates the order, and the order
    is only written if this returns ``ok``. That ordering is deliberate: an
    order that exists before the money does is an order somebody has to go
    back and cancel, and on a shop this size that somebody is the owner.
    """
    if not settings.is_dev:
        raise PaymentsNotConfigured(
            "No payment processor is configured. Wire up Click, Payme or "
            "Stripe in app/payments.py before taking card orders in "
            f"MB_ENV={settings.env}."
        )
    if not card.processor_token:
        return Charge(ok=False, reason="card_unusable")
    if amount <= 0:
        return Charge(ok=False, reason="payment_failed")

    failure = DECLINES.get(card.last4)
    if failure is not None:
        return Charge(ok=False, reason=failure)
    return Charge(ok=True, reference=f"{DEV_TOKEN_PREFIX}chg_{uuid4().hex[:16]}")
