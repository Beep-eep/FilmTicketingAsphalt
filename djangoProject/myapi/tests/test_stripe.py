"""Stripe integration tests with the Stripe client mocked out (no network)."""
from types import SimpleNamespace
from unittest import mock

import stripe
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from myapi.models import Order, SeatStatus
from myapi.services import payments
from myapi.tests.helpers import client_for, make_cinema, make_user, seat_ids


def fake_session(order, status="complete", payment_status="paid", **extra):
    data = dict(
        id="cs_test_123", url="https://checkout.stripe.com/c/pay/cs_test_123", status=status,
        payment_status=payment_status, amount_total=payments.to_minor_units(order.amount_total),
        currency=order.currency, metadata={"order_code": order.code}, client_reference_id=order.code,
        payment_intent="pi_test_456", expires_at=int(timezone.now().timestamp()) + 31 * 60,
    )
    data.update(extra)
    return stripe.checkout.Session.construct_from(data, "sk_test_dummy")  # behaves like a real API response


@override_settings(STRIPE_SECRET_KEY="sk_test_dummy", PAYMENT_PROVIDER="stripe", STRIPE_WEBHOOK_SECRET="whsec_x")
class StripeTests(TestCase):
    def setUp(self):
        self.film, self.room, self.show = make_cinema()
        self.user = make_user()
        self.c = client_for(self.user)
        r = self.c.post("/api/orders/", {"showtime": self.show.ID, "seats": seat_ids(self.show, [1, 16])},
                        format="json", HTTP_ORIGIN="https://abc.trycloudflare.com")
        self.order = Order.objects.get(code=r.data["code"])
        patcher = mock.patch("myapi.services.payments.stripe.StripeClient")
        self.StripeClient = patcher.start()
        self.addCleanup(patcher.stop)
        self.client_mock = self.StripeClient.return_value

    def test_checkout_session_parameters(self):
        self.client_mock.v1.checkout.sessions.create.return_value = fake_session(self.order, status="open")
        r = self.c.post(f"/api/orders/{self.order.code}/checkout/", {"locale": "zh"}, format="json",
                        HTTP_ORIGIN="https://abc.trycloudflare.com")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["checkout_url"], "https://checkout.stripe.com/c/pay/cs_test_123")
        params = self.client_mock.v1.checkout.sessions.create.call_args.kwargs["params"]
        self.assertEqual(params["mode"], "payment")
        self.assertEqual(params["success_url"],
                         "https://abc.trycloudflare.com/checkout/complete?session_id={CHECKOUT_SESSION_ID}")
        self.assertEqual(params["customer_email"], "alice@example.com")
        self.assertEqual(params["locale"], "zh")
        amounts = sorted((i["price_data"]["unit_amount"], i["quantity"]) for i in params["line_items"])
        self.assertEqual(amounts, [(1000, 1), (1300, 1)])
        self.assertGreaterEqual(params["expires_at"] - timezone.now().timestamp(), 30 * 60)
        self.order.refresh_from_db()
        self.assertEqual(self.order.stripe_session_id, "cs_test_123")
        self.assertGreater(self.order.hold_expires_at.timestamp(), params["expires_at"])

    def test_fulfil_is_idempotent_and_sends_one_email(self):
        self.client_mock.v1.checkout.sessions.retrieve.return_value = fake_session(self.order)
        with self.captureOnCommitCallbacks(execute=True):
            first = self.c.post("/api/payments/stripe/confirm/", {"session_id": "cs_test_123"}, format="json")
        with self.captureOnCommitCallbacks(execute=True):
            second = self.c.post("/api/payments/stripe/confirm/", {"session_id": "cs_test_123"}, format="json")
        self.assertEqual(first.data["status"], "paid")
        self.assertEqual(second.data["status"], "paid")
        self.order.refresh_from_db()
        self.assertEqual(self.order.stripe_payment_intent, "pi_test_456")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("abc.trycloudflare.com/tickets", mail.outbox[0].body)

    def test_unpaid_session_changes_nothing(self):
        self.client_mock.v1.checkout.sessions.retrieve.return_value = fake_session(
            self.order, status="open", payment_status="unpaid")
        r = self.c.post("/api/payments/stripe/confirm/", {"session_id": "cs_test_123"}, format="json")
        self.assertEqual(r.data["status"], "pending")

    def test_amount_mismatch_is_not_fulfilled(self):
        self.client_mock.v1.checkout.sessions.retrieve.return_value = fake_session(self.order, amount_total=1)
        r = self.c.post("/api/payments/stripe/confirm/", {"session_id": "cs_test_123"}, format="json")
        self.assertEqual(r.data["status"], "pending")

    def test_refund_calls_stripe_with_the_ticket_amount(self):
        self.client_mock.v1.checkout.sessions.retrieve.return_value = fake_session(self.order)
        self.c.post("/api/payments/stripe/confirm/", {"session_id": "cs_test_123"}, format="json")
        self.client_mock.v1.refunds.create.return_value = SimpleNamespace(id="re_789")
        ticket = self.order.tickets.get(seat_number=16)
        r = self.c.post(f"/api/orders/{self.order.code}/refund/", {"ticket_ids": [ticket.id]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        kwargs = self.client_mock.v1.refunds.create.call_args.kwargs
        self.assertEqual(kwargs["params"]["payment_intent"], "pi_test_456")
        self.assertEqual(kwargs["params"]["amount"], 1300)
        self.assertIn("idempotency_key", kwargs["options"])
        ticket.refresh_from_db()
        self.assertEqual(ticket.stripe_refund_id, "re_789")

    def test_webhook_requires_a_valid_signature(self):
        self.client_mock.construct_event.side_effect = ValueError("bad signature")
        r = self.client.post("/api/payments/stripe/webhook/", data=b"{}", content_type="application/json",
                             HTTP_STRIPE_SIGNATURE="t=1,v1=bad")
        self.assertEqual(r.status_code, 400)

    def test_webhook_completed_event_fulfils(self):
        session = fake_session(self.order)
        self.client_mock.construct_event.return_value = stripe.Event.construct_from(
            {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": session.to_dict()}}, "sk_test")
        self.client_mock.v1.checkout.sessions.retrieve.return_value = session
        r = self.client.post("/api/payments/stripe/webhook/", data=b"{}", content_type="application/json",
                             HTTP_STRIPE_SIGNATURE="t=1,v1=ok")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, "paid")

    def test_webhook_expired_event_releases_seats(self):
        Order.objects.filter(pk=self.order.pk).update(stripe_session_id="cs_test_123")
        session = fake_session(self.order, status="expired", payment_status="unpaid")
        self.client_mock.construct_event.return_value = stripe.Event.construct_from(
            {"id": "evt_2", "type": "checkout.session.expired", "data": {"object": session.to_dict()}}, "sk_test")
        self.client.post("/api/payments/stripe/webhook/", data=b"{}", content_type="application/json",
                         HTTP_STRIPE_SIGNATURE="t=1,v1=ok")
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, "expired")
        self.assertFalse(SeatStatus.objects.get(timeslot=self.show, seat_number=1).is_occupied)


@override_settings(STRIPE_SECRET_KEY="sk_test_dummy", PAYMENT_PROVIDER="stripe", STRIPE_WEBHOOK_SECRET="whsec_test_secret")
class StripeSignatureTests(TestCase):
    """Uses the real Stripe SDK signature check (no network needed) on a hand-signed event."""

    def setUp(self):
        self.film, self.room, self.show = make_cinema()
        self.user = make_user()
        c = client_for(self.user)
        r = c.post("/api/orders/", {"showtime": self.show.ID, "seats": seat_ids(self.show, [2])}, format="json")
        self.order = Order.objects.get(code=r.data["code"])
        Order.objects.filter(pk=self.order.pk).update(stripe_session_id="cs_test_sig")

    def post_event(self, payload, secret="whsec_test_secret"):
        import hashlib, hmac, json, time
        body = json.dumps(payload)
        ts = int(time.time())
        sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
        return self.client.post("/api/payments/stripe/webhook/", data=body, content_type="application/json",
                                HTTP_STRIPE_SIGNATURE=f"t={ts},v1={sig}")

    def event(self):
        return {"id": "evt_sig", "object": "event", "type": "checkout.session.expired",
                "data": {"object": {"id": "cs_test_sig", "object": "checkout.session",
                                    "metadata": {"order_code": self.order.code},
                                    "client_reference_id": self.order.code}}}

    def test_correctly_signed_event_is_accepted(self):
        response = self.post_event(self.event())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, "expired")

    def test_event_signed_with_another_secret_is_rejected(self):
        response = self.post_event(self.event(), secret="whsec_attacker")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, "pending")
