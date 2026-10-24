"""Payment providers.

* StripeProvider — Stripe Checkout (Stripe-hosted payment page). Used when
  STRIPE_SECRET_KEY is set. Test keys (sk_test_...) accept only test cards;
  live keys (sk_live_...) charge real cards once Stripe has activated the account.
* DemoProvider — no money moves. A page in this app simulates the result.
  Used when no Stripe key is set, so the site works out of the box.

Fulfilment follows Stripe's guidance: the same idempotent function runs from
the webhook *and* from the page the customer lands on after paying.
"""
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from myapi.models import Order
from myapi.services import booking

log = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


def to_minor_units(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _order_code_of(obj):
    """Read our booking code from a Stripe Checkout Session (StripeObject is not a dict in stripe-python 8+)."""
    metadata = getattr(obj, "metadata", None)
    if metadata is not None and not isinstance(metadata, dict):
        metadata = metadata.to_dict()
    return (metadata or {}).get("order_code") or getattr(obj, "client_reference_id", None)


def get_provider(name=None):
    name = name or settings.PAYMENT_PROVIDER
    if name == "stripe":
        return StripeProvider()
    if name == "legacy":
        return LegacyProvider()
    return DemoProvider()


class DemoProvider:
    name = "demo"

    def start_checkout(self, order, site_url, locale="auto"):
        return f"{site_url}/checkout/demo/{order.code}"

    def cancel_checkout(self, order):
        pass

    def refund(self, order, amount, idempotency_key):
        return f"demo_refund_{order.code}"

    def complete(self, order):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            result = booking.mark_order_paid(order, payment_intent=f"demo_{order.code}")
        if result == booking.PAID_CONFLICT:
            raise booking.BookingError(
                "Your hold ran out and someone else took one of the seats. Choose seats again.", "hold_lost", 409)
        return order


class LegacyProvider(DemoProvider):
    """Tickets bought before the payment upgrade: refunds just free the seat."""
    name = "legacy"


class StripeProvider:
    name = "stripe"

    def __init__(self):
        if not settings.STRIPE_SECRET_KEY:
            raise PaymentError("Stripe isn't configured (STRIPE_SECRET_KEY is empty).")
        self.client = stripe.StripeClient(settings.STRIPE_SECRET_KEY)

    # -- checkout -----------------------------------------------------------------------------

    def _line_items(self, order):
        film = order.timeslot.film
        when = timezone.localtime(order.timeslot.begin_time).strftime("%a %b %d, %I:%M %p")
        room = order.timeslot.ScreeningRoom.name
        groups = {}
        for t in order.tickets.filter(status="held").order_by("seat_number"):
            groups.setdefault(t.price, []).append(t.seat_label)
        items = []
        for price, labels in groups.items():
            items.append({
                "price_data": {
                    "currency": order.currency,
                    "unit_amount": to_minor_units(price),
                    "product_data": {
                        "name": f"{film.title} ticket",
                        "description": f"{when}, {room}. Seats {', '.join(labels)}",
                    },
                },
                "quantity": len(labels),
            })
        return items

    def start_checkout(self, order, site_url, locale="auto"):
        if order.stripe_session_id:
            try:
                existing = self.client.v1.checkout.sessions.retrieve(order.stripe_session_id)
                if existing.status == "open" and existing.expires_at > timezone.now().timestamp() + 120:
                    return existing.url
            except stripe.StripeError as exc:
                log.warning("Couldn't reuse Checkout Session %s: %s", order.stripe_session_id, exc)

        # Stripe requires expires_at to be 30 minutes to 24 hours away.
        expires = timezone.now() + timedelta(minutes=31)
        params = {
            "mode": "payment",
            "line_items": self._line_items(order),
            "success_url": f"{site_url}/checkout/complete?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{site_url}/tickets?cancelled={order.code}",
            "client_reference_id": order.code,
            "metadata": {"order_code": order.code, "user_id": str(order.user_id)},
            "payment_intent_data": {"metadata": {"order_code": order.code}},
            "expires_at": int(expires.timestamp()),
            "submit_type": "book",
            "locale": locale if locale in {"auto", "en", "zh"} else "auto",
        }
        if order.user.email:
            params["customer_email"] = order.user.email
        try:
            session = self.client.v1.checkout.sessions.create(
                params=params,
                options={"idempotency_key": f"checkout-{order.code}-{int(expires.timestamp()) // 60}"},
            )
        except stripe.StripeError as exc:
            log.exception("Stripe Checkout Session create failed for %s", order.code)
            raise PaymentError(f"Stripe couldn't start the payment: {exc.user_message or exc}") from exc

        session_expiry = datetime.fromtimestamp(session.expires_at, tz=dt_timezone.utc)
        Order.objects.filter(pk=order.pk).update(
            stripe_session_id=session.id,
            hold_expires_at=max(order.hold_expires_at or session_expiry, session_expiry + timedelta(minutes=1)),
        )
        return session.url

    def cancel_checkout(self, order):
        if not order.stripe_session_id:
            return
        try:
            session = self.client.v1.checkout.sessions.retrieve(order.stripe_session_id)
            if session.status == "open":
                self.client.v1.checkout.sessions.expire(order.stripe_session_id)
        except stripe.StripeError as exc:
            log.warning("Couldn't expire Checkout Session %s: %s", order.stripe_session_id, exc)

    # -- fulfilment -----------------------------------------------------------------------------

    def fulfill(self, session_id):
        """Safe to call any number of times, from the webhook or the landing page."""
        try:
            session = self.client.v1.checkout.sessions.retrieve(session_id)
        except stripe.StripeError as exc:
            raise PaymentError(f"Couldn't look up the payment: {exc.user_message or exc}") from exc

        code = _order_code_of(session)
        if not code:
            raise PaymentError("This payment isn't linked to a booking.")

        with transaction.atomic():
            order = Order.objects.select_for_update().select_related("timeslot").get(code=code)
            if session.payment_status not in ("paid", "no_payment_required"):
                return order
            if session.amount_total != to_minor_units(order.amount_total) or session.currency != order.currency:
                log.error("Amount mismatch for %s: Stripe %s %s vs order %s %s", code,
                          session.amount_total, session.currency, order.amount_total, order.currency)
                order.note = "Amount mismatch: check this payment in the Stripe Dashboard."
                order.save(update_fields=["note", "updated_at"])
                return order
            payment_intent = getattr(session, "payment_intent", None)
            if payment_intent is not None and not isinstance(payment_intent, str):
                payment_intent = payment_intent.id  # expanded PaymentIntent object
            payment_intent = payment_intent or ""
            order.stripe_session_id = session.id
            result = booking.mark_order_paid(order, payment_intent=payment_intent)
            if result == booking.PAID_CONFLICT:
                # Paid after the hold ran out and the seats were resold: give the money back.
                self.client.v1.refunds.create(
                    params={"payment_intent": payment_intent, "reason": "requested_by_customer",
                            "metadata": {"order_code": order.code}},
                    options={"idempotency_key": f"conflict-refund-{order.code}"},
                )
                order.status = Order.REFUNDED
                order.amount_refunded = order.amount_total
                order.stripe_payment_intent = payment_intent
                order.note = "Paid after the seat hold expired and the seats were taken. Refunded in full."
                order.save()
        return order

    def handle_event(self, event):
        kind = event.type
        obj = event.data.object
        if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            self.fulfill(obj.id)
        elif kind in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            code = _order_code_of(obj)
            with transaction.atomic():
                order = Order.objects.select_for_update().filter(code=code, stripe_session_id=obj.id).first()
                if order and order.status == Order.PENDING:
                    booking.release_order(order, Order.EXPIRED, "expired")

    def construct_event(self, payload, signature):
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise PaymentError("STRIPE_WEBHOOK_SECRET isn't set.")
        return self.client.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)

    # -- refunds ----------------------------------------------------------------------------------

    def refund(self, order, amount, idempotency_key):
        if not order.stripe_payment_intent:
            raise PaymentError("This order has no Stripe payment to refund.")
        try:
            refund = self.client.v1.refunds.create(
                params={
                    "payment_intent": order.stripe_payment_intent,
                    "amount": to_minor_units(amount),
                    "reason": "requested_by_customer",
                    "metadata": {"order_code": order.code},
                },
                options={"idempotency_key": idempotency_key},
            )
        except stripe.StripeError as exc:
            log.exception("Stripe refund failed for %s", order.code)
            raise PaymentError(f"Stripe couldn't refund the payment: {exc.user_message or exc}") from exc
        return refund.id
