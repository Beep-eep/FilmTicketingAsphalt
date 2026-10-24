from django.db.models import Exists, OuterRef
from django.utils import timezone

from myapi.models import Order, TimeSlot


def clear_unbooked_future_showtimes():
    """Delete upcoming showtimes nobody has booked, so the schedule can be rebuilt with new films."""
    booked = Order.objects.filter(timeslot=OuterRef("pk"))
    qs = TimeSlot.objects.filter(begin_time__gt=timezone.now()).annotate(has_orders=Exists(booked)).filter(has_orders=False)
    count = qs.count()
    qs.delete()
    return count
