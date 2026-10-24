"""Generates showtimes (and their seats) so the demo cinema always has a programme.

Every room gets a day of back-to-back screenings between 11:00 and about
23:30 local time, with 20 minutes between films. Films rotate from day to day
so each one comes round several times a week. Generation is idempotent: a room
that already has showtimes on a day is left alone.
"""
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from myapi.models import Film, ScreeningRoom, TimeSlot

log = logging.getLogger(__name__)

FIRST_SHOW = time(11, 0)
LAST_START = time(22, 30)
TURNAROUND = timedelta(minutes=20)
MATINEE_BEFORE = time(16, 0)
MATINEE_DISCOUNT = Decimal("2.00")

BASE_PRICE = {"standard": Decimal("12.50"), "imax": Decimal("18.00"),
              "dolby": Decimal("16.00"), "studio": Decimal("11.00")}
FORMAT_FOR_ROOM = {"imax": "IMAX", "dolby": "Dolby"}
SPECTACLE = {"Sci-Fi", "Action", "Adventure"}
ENGLISH = "English"


def _round_up(dt, minutes=5):
    extra = (-dt.minute) % minutes
    return (dt + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def _candidates(room, films):
    if room.kind in ("imax", "dolby"):
        picked = [f for f in films if SPECTACLE & set(f.genre_list)]
        return picked or films
    if room.kind == "studio":
        picked = [f for f in films if f.language != ENGLISH or f.release_date.year < 1980]
        return picked or films
    return films


def schedule_day(room, day, films, tz, counts):
    """Create one day of showtimes for one room. Returns the number created.

    `counts` (film id -> screenings so far) is shared across rooms and days, so the
    least-shown film always gets the next slot and every film comes round regularly.
    """
    if not films:
        return 0
    start_of_day = datetime.combine(day, time(0, 0), tzinfo=tz)
    if TimeSlot.objects.filter(ScreeningRoom=room, begin_time__gte=start_of_day,
                               begin_time__lt=start_of_day + timedelta(days=1)).exists():
        return 0
    pool = _candidates(room, films)
    current = datetime.combine(day, FIRST_SHOW, tzinfo=tz)
    shown_here = set()
    created = []
    while current.time() <= LAST_START and current.date() == day and len(created) < 12:
        options = [f for f in pool if f.ID not in shown_here] or pool
        film = min(options, key=lambda f: (counts.get(f.ID, 0), (f.ID * 31 + day.toordinal() * 7 + room.ID * 13) % 101))
        counts[film.ID] = counts.get(film.ID, 0) + 1
        shown_here.add(film.ID)
        price = BASE_PRICE.get(room.kind, Decimal("12.50"))
        if room.kind in ("standard", "studio") and current.time() < MATINEE_BEFORE:
            price -= MATINEE_DISCOUNT
        created.append(TimeSlot(
            film=film,
            ScreeningRoom=room,
            begin_time=current,
            ticketPrice=price,
            format=FORMAT_FOR_ROOM.get(room.kind, "2D"),
            audio_language=film.language,
            subtitles="" if film.language == ENGLISH else "English",
        ))
        runtime = timedelta(minutes=film.runtime_minutes or 120)
        current = _round_up(current + runtime + TURNAROUND, 15)

    for slot in created:
        slot.save()  # the post_save signal in models.py creates the seats
    return len(created)


def generate_schedule(days=7, start=None):
    """Fill the next `days` days (starting today, cinema time) with showtimes."""
    tz = ZoneInfo(settings.TIME_ZONE)
    start = start or timezone.localtime(timezone.now(), tz).date()
    films = list(Film.objects.filter(now_showing=True).order_by("ID"))
    window_start = datetime.combine(start, time(0, 0), tzinfo=tz)
    counts = dict(TimeSlot.objects.filter(begin_time__gte=window_start, film__in=films)
                  .values_list("film_id").annotate(n=Count("ID")).values_list("film_id", "n"))
    rooms = list(ScreeningRoom.objects.order_by("ID"))
    total = 0
    for offset in range(days):
        day = start + timedelta(days=offset)
        for room in rooms:
            with transaction.atomic():
                # Lock the room row so two processes can't schedule the same day twice.
                locked = ScreeningRoom.objects.select_for_update().get(pk=room.pk)
                total += schedule_day(locked, day, films, tz, counts)
    if total:
        log.info("Scheduled %s new showtime(s)", total)
    return total


def ensure_schedule():
    """Called from the film list. Tops up the schedule at most every 10 minutes per process."""
    days = settings.AUTO_SCHEDULE_DAYS
    if days <= 0 or cache.get("schedule-checked"):
        return 0
    cache.set("schedule-checked", True, 600)
    if not ScreeningRoom.objects.exists() or not Film.objects.filter(now_showing=True).exists():
        return 0
    latest = TimeSlot.objects.aggregate(m=Max("begin_time"))["m"]
    if latest and latest > timezone.now() + timedelta(days=days - 1):
        return 0
    return generate_schedule(days=days)


def today_local():
    return timezone.localtime(timezone.now(), ZoneInfo(settings.TIME_ZONE)).date()


def as_local_date(value) -> date:
    return timezone.localtime(value, ZoneInfo(settings.TIME_ZONE)).date()
