"""Seat holds, orders and refunds.

Rules
-----
* Picking seats creates a *pending* order that holds the seats for
  SEAT_HOLD_MINUTES. Starting payment extends the hold to match the payment
  page's own expiry (Stripe's minimum is 30 minutes).
* A seat is taken while it has an active ticket (held or paid). The
  `SeatStatus.is_occupied` flag mirrors that and is changed only here, inside
  transactions that lock the seat rows, so two people can never buy one seat.
* Expired holds are released lazily whenever seats or orders are looked at,
  so no background worker is needed (run `release_expired_holds` from a cron
  job if you want it to happen on a timer as well).
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from myapi.models import Order, SeatStatus, TicketService, TimeSlot, seat_label

log = logging.getLogger(__name__)

MAX_PENDING_ORDERS_PER_USER = 3


class BookingError(Exception):
    def __init__(self, message, code="booking_error", status=400, extra=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.extra = extra or {}


def booking_open(timeslot, now=None):
    now = now or timezone.now()
    return timeslot.begin_time + timedelta(minutes=settings.BOOKING_CUTOFF_MINUTES) > now


def refund_deadline(timeslot):
    return timeslot.begin_time - timedelta(minutes=settings.REFUND_CUTOFF_MINUTES)


def _free_seats(timeslot_id, seat_numbers):
    if seat_numbers:
        SeatStatus.objects.filter(timeslot_id=timeslot_id, seat_number__in=seat_numbers).update(is_occupied=False)


def release_order(order, order_status, ticket_status):
    """Give back the seats of a pending order. Call inside a transaction with the order locked."""
    held = list(order.tickets.filter(status=TicketService.HELD).values_list("seat_number", flat=True))
    _free_seats(order.timeslot_id, held)
    order.tickets.filter(status=TicketService.HELD).update(status=ticket_status, is_paid=False)
    order.status = order_status
    order.save(update_fields=["status", "updated_at"])


def release_expired_holds(timeslot_id=None, user=None):
    now = timezone.now()
    qs = Order.objects.filter(status=Order.PENDING, hold_expires_at__lt=now)
    if timeslot_id is not None:
        qs = qs.filter(timeslot_id=timeslot_id)
    if user is not None:
        qs = qs.filter(user=user)
    released = 0
    for order_id in list(qs.values_list("id", flat=True)[:500]):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(id=order_id)
            if order.status == Order.PENDING and order.hold_expires_at and order.hold_expires_at < now:
                release_order(order, Order.EXPIRED, TicketService.EXPIRED)
                released += 1
    if released:
        log.info("Released %s expired seat hold(s)", released)
    return released


def create_order(user, timeslot_id, seat_ids, site_url=""):
    """Hold the chosen seats and return a pending order."""
    seat_ids = sorted({int(s) for s in seat_ids})
    if not seat_ids:
        raise BookingError("Choose at least one seat.", "no_seats")
    if len(seat_ids) > settings.MAX_SEATS_PER_ORDER:
        raise BookingError(
            f"You can book up to {settings.MAX_SEATS_PER_ORDER} seats at a time.", "too_many_seats")

    release_expired_holds(timeslot_id=timeslot_id)
    now = timezone.now()
    replaced_sessions = []

    with transaction.atomic():
        try:
            timeslot = TimeSlot.objects.select_related("ScreeningRoom", "film").get(ID=timeslot_id)
        except TimeSlot.DoesNotExist:
            raise BookingError("That showtime doesn't exist.", "not_found", 404)
        if not booking_open(timeslot, now):
            raise BookingError("Booking has closed for this showtime.", "booking_closed")

        # Choosing seats again for the same showtime replaces the earlier hold.
        for previous in Order.objects.select_for_update().filter(
                user=user, timeslot=timeslot, status=Order.PENDING):
            release_order(previous, Order.CANCELLED, TicketService.CANCELLED)
            if previous.stripe_session_id:
                replaced_sessions.append(previous)

        other_pending = Order.objects.filter(
            user=user, status=Order.PENDING, hold_expires_at__gt=now).exclude(timeslot=timeslot).count()
        if other_pending >= MAX_PENDING_ORDERS_PER_USER:
            raise BookingError(
                "You have too many unpaid bookings. Pay for or cancel one in My tickets first.",
                "too_many_pending")

        seats = list(SeatStatus.objects.select_for_update()
                     .filter(timeslot=timeslot, ID__in=seat_ids).order_by("ID"))
        if len(seats) != len(seat_ids):
            raise BookingError("Some of those seats aren't part of this showtime.", "invalid_seats")
        columns = timeslot.ScreeningRoom.columns
        taken = [seat_label(s.seat_number, columns) for s in seats if s.is_occupied]
        if taken:
            raise BookingError(
                "Someone else just took " + ", ".join(taken) + ". Pick different seats.",
                "seats_taken", 409, {"seats": taken})

        order = Order.objects.create(
            user=user,
            timeslot=timeslot,
            currency=settings.CURRENCY,
            payment_provider=settings.PAYMENT_PROVIDER,
            hold_expires_at=now + timedelta(minutes=settings.SEAT_HOLD_MINUTES),
            site_url=site_url[:200],
        )
        tickets = [
            TicketService(
                order=order,
                timeslot=timeslot,
                user=user,
                seat_number=s.seat_number,
                seat_label=seat_label(s.seat_number, columns),
                price=timeslot.price_for_seat(s.seat_number),
                status=TicketService.HELD,
                is_paid=False,
            )
            for s in seats
        ]
        TicketService.objects.bulk_create(tickets)
        SeatStatus.objects.filter(ID__in=seat_ids).update(is_occupied=True)
        order.amount_total = sum((t.price for t in tickets), Decimal("0"))
        order.save(update_fields=["amount_total", "updated_at"])

    for previous in replaced_sessions:
        from myapi.services.payments import get_provider
        get_provider(previous.payment_provider).cancel_checkout(previous)
    return order


def cancel_order(order):
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.PENDING:
            raise BookingError("Only unpaid bookings can be cancelled. Paid tickets can be refunded.", "not_pending")
        release_order(order, Order.CANCELLED, TicketService.CANCELLED)
    if order.stripe_session_id:
        from myapi.services.payments import get_provider
        get_provider(order.payment_provider).cancel_checkout(order)
    return order


PAID_OK, PAID_ALREADY, PAID_CONFLICT = "paid", "already_paid", "conflict"


def mark_order_paid(order, payment_intent=""):
    """Turn a pending order into a paid one. Call inside a transaction with the order locked.

    Returns PAID_CONFLICT if the payment arrived after the hold ran out and
    someone else has taken one of the seats since; the caller must refund.
    """
    if order.status == Order.PAID:
        return PAID_ALREADY
    if order.status not in (Order.PENDING, Order.EXPIRED, Order.CANCELLED):
        return PAID_ALREADY

    tickets = list(order.tickets.all())
    if order.status != Order.PENDING:
        # The hold had lapsed. Take the seats back if they're still free.
        numbers = [t.seat_number for t in tickets]
        seats = list(SeatStatus.objects.select_for_update()
                     .filter(timeslot_id=order.timeslot_id, seat_number__in=numbers))
        if any(s.is_occupied for s in seats):
            return PAID_CONFLICT
        SeatStatus.objects.filter(timeslot_id=order.timeslot_id, seat_number__in=numbers).update(is_occupied=True)

    TicketService.objects.filter(order=order).update(status=TicketService.PAID, is_paid=True)
    order.status = Order.PAID
    order.paid_at = timezone.now()
    order.hold_expires_at = None
    if payment_intent:
        order.stripe_payment_intent = payment_intent
    order.save()

    from myapi.services import emails
    transaction.on_commit(lambda: emails.send_booking_confirmation(order.pk))
    return PAID_OK


def refund_tickets(order, ticket_ids=None, by_staff=False):
    """Refund some or all paid tickets of an order and free their seats."""
    from myapi.services.payments import get_provider, PaymentError

    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("timeslot").get(pk=order.pk)
        if order.status not in (Order.PAID, Order.PARTIALLY_REFUNDED):
            raise BookingError("Only paid tickets can be refunded.", "not_paid")
        if not by_staff and timezone.now() >= refund_deadline(order.timeslot):
            raise BookingError(
                f"Refunds close {settings.REFUND_CUTOFF_MINUTES} minutes before the showtime starts.",
                "refund_closed")
        tickets = order.tickets.select_for_update().filter(status=TicketService.PAID)
        if ticket_ids:
            tickets = tickets.filter(id__in=ticket_ids)
        tickets = list(tickets)
        if not tickets:
            raise BookingError("Those tickets are already refunded or don't exist.", "nothing_to_refund")

        amount = sum((t.price or Decimal("0") for t in tickets), Decimal("0"))
        ids = sorted(t.id for t in tickets)
        try:
            refund_id = get_provider(order.payment_provider).refund(
                order, amount, idempotency_key=f"refund-{order.code}-{'-'.join(map(str, ids))}")
        except PaymentError as exc:
            raise BookingError(str(exc), "refund_failed", 502)

        now = timezone.now()
        TicketService.objects.filter(id__in=ids).update(
            status=TicketService.REFUNDED, is_paid=False, stripe_refund_id=refund_id or "", refunded_at=now)
        _free_seats(order.timeslot_id, [t.seat_number for t in tickets])
        order.amount_refunded += amount
        still_paid = order.tickets.filter(status=TicketService.PAID).exists()
        order.status = Order.PARTIALLY_REFUNDED if still_paid else Order.REFUNDED
        order.save(update_fields=["amount_refunded", "status", "updated_at"])

        from myapi.services import emails
        transaction.on_commit(lambda: emails.send_refund_confirmation(order.pk, ids, amount))
    return order, amount
