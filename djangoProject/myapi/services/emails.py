"""Account and booking emails.

Which service sends them is decided in settings.py (console in development,
SMTP such as Gmail, or the Resend HTTPS API). Sending never crashes a request:
failures are logged and reported back as `False`.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator, default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from myapi.models import Order, TicketService
from myapi.services.site import site_url as default_site_url

log = logging.getLogger(__name__)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Like the password-reset token, but stops working once the account is active."""
    key_salt = "myapi.EmailVerificationTokenGenerator"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{user.is_active}{user.email}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()


def money(amount, currency):
    symbol = {"usd": "$", "eur": "€", "gbp": "£", "cny": "¥"}.get(currency, "")
    value = f"{Decimal(amount):,.2f}"
    return f"{symbol}{value}" if symbol else f"{value} {currency.upper()}"


def _send(to, subject, template, context):
    context = {"cinema_name": settings.CINEMA_NAME, **context}
    text = render_to_string(f"emails/{template}.txt", context)
    html = render_to_string(f"emails/{template}.html", context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to])
    message.attach_alternative(html, "text/html")
    try:
        message.send()
        return True
    except Exception:  # noqa: BLE001 — any mail failure must not break the request
        log.exception("Couldn't send '%s' email to %s", template, to)
        return False


def _uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))


def send_verification_email(user, base_url):
    link = f"{base_url}/verify-email?uid={_uid(user)}&token={email_verification_token.make_token(user)}"
    return _send(user.email, f"Confirm your email for {settings.CINEMA_NAME}", "verify_email",
                 {"user": user, "link": link})


def send_password_reset_email(user, base_url):
    link = f"{base_url}/reset-password?uid={_uid(user)}&token={default_token_generator.make_token(user)}"
    return _send(user.email, f"Reset your {settings.CINEMA_NAME} password", "password_reset",
                 {"user": user, "link": link})


def _order_context(order):
    ts = order.timeslot
    begin = timezone.localtime(ts.begin_time)
    base = order.site_url or default_site_url()
    return {
        "order": order,
        "film": ts.film,
        "room": ts.ScreeningRoom,
        "date": begin.strftime("%A, %B %d, %Y"),
        "time": begin.strftime("%I:%M %p").lstrip("0"),
        "tickets_link": f"{base}/tickets?order={order.code}",
    }


def send_booking_confirmation(order_id):
    order = Order.objects.select_related("timeslot__film", "timeslot__ScreeningRoom", "user").get(pk=order_id)
    if order.confirmation_email_sent or not order.user.email:
        return False
    tickets = list(order.tickets.filter(status=TicketService.PAID).order_by("seat_number"))
    ctx = _order_context(order)
    ctx.update({
        "seats": ", ".join(t.seat_label for t in tickets),
        "count": len(tickets),
        "total": money(order.amount_total, order.currency),
    })
    sent = _send(order.user.email, f"Your tickets for {order.timeslot.film.title}", "booking_confirmed", ctx)
    if sent:
        Order.objects.filter(pk=order.pk).update(confirmation_email_sent=True)
    return sent


def send_refund_confirmation(order_id, ticket_ids, amount):
    order = Order.objects.select_related("timeslot__film", "timeslot__ScreeningRoom", "user").get(pk=order_id)
    if not order.user.email:
        return False
    tickets = list(order.tickets.filter(id__in=ticket_ids).order_by("seat_number"))
    ctx = _order_context(order)
    ctx.update({
        "seats": ", ".join(t.seat_label for t in tickets),
        "count": len(tickets),
        "amount": money(amount, order.currency),
        "is_demo": order.payment_provider != "stripe",
    })
    return _send(order.user.email, f"Refund for {order.timeslot.film.title}", "refund_confirmed", ctx)
