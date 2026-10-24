from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from myapi.models import Film, ScreeningRoom, TimeSlot


def make_cinema(hours_ahead=48):
    film = Film.objects.create(title="Test Film", director="Someone", release_date="2001-01-01",
                               runtime_minutes=100, genres="Drama", language="English")
    room = ScreeningRoom.objects.create(name="Hall T", rows=4, columns=5, premium_rows="4",
                                        premium_surcharge=Decimal("3.00"))
    show = TimeSlot.objects.create(film=film, ScreeningRoom=room,
                                   begin_time=timezone.now() + timedelta(hours=hours_ahead),
                                   ticketPrice=Decimal("10.00"))
    return film, room, show


def make_user(username="alice", email="alice@example.com", password="correct-horse-9", active=True):
    return User.objects.create_user(username=username, email=email, password=password, is_active=active)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def seat_ids(show, numbers):
    return list(show.seats.filter(seat_number__in=numbers).order_by("seat_number").values_list("ID", flat=True))
