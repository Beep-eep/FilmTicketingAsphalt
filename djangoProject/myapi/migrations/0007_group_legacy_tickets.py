"""Give tickets bought before the upgrade an order, a price and a seat label.

* Paid tickets become one paid order per (user, showtime), marked as `legacy`
  payments (refunding them just frees the seat).
* Unpaid reservations from the old "book now, pay later" button are cancelled
  and their seats freed, because the new flow holds seats only while paying.
"""
from decimal import Decimal

from django.db import migrations
from django.utils import timezone

ROW_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _label(seat_number, columns):
    row_index = (seat_number - 1) // columns
    letter = ROW_LETTERS[row_index] if row_index < len(ROW_LETTERS) else f"R{row_index + 1}-"
    return f"{letter}{(seat_number - 1) % columns + 1}"


def forwards(apps, schema_editor):
    Ticket = apps.get_model("myapi", "TicketService")
    Order = apps.get_model("myapi", "Order")
    SeatStatus = apps.get_model("myapi", "SeatStatus")
    now = timezone.now()

    groups = {}
    for t in Ticket.objects.filter(order__isnull=True).select_related("timeslot__ScreeningRoom"):
        groups.setdefault((t.user_id, t.timeslot_id, t.is_paid), []).append(t)

    for (user_id, timeslot_id, is_paid), tickets in groups.items():
        timeslot = tickets[0].timeslot
        columns = timeslot.ScreeningRoom.columns or 1
        price = timeslot.ticketPrice or Decimal("0")
        order = Order.objects.create(
            user_id=user_id,
            timeslot_id=timeslot_id,
            status="paid" if is_paid else "cancelled",
            amount_total=price * len(tickets),
            payment_provider="legacy",
            paid_at=now if is_paid else None,
            note="Booked before the payment upgrade" if is_paid else "Unpaid reservation from before the upgrade",
        )
        for t in tickets:
            t.order = order
            t.price = price
            t.seat_label = _label(t.seat_number, columns)
            t.status = "paid" if is_paid else "cancelled"
            t.save(update_fields=["order", "price", "seat_label", "status"])
        if not is_paid:
            SeatStatus.objects.filter(
                timeslot_id=timeslot_id, seat_number__in=[t.seat_number for t in tickets]
            ).update(is_occupied=False)


class Migration(migrations.Migration):

    dependencies = [
        ("myapi", "0006_upgrade_v2"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
