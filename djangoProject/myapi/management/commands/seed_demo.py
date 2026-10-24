"""Fill the database with the demo cinema: rooms, 40 films with cast, and a week of showtimes.

    python manage.py seed_demo            # add or update; keeps users and bookings
    python manage.py seed_demo --reset    # wipe films, showtimes and bookings first (keeps user accounts)
    python manage.py seed_demo --days 14  # schedule two weeks instead of one
    python manage.py seed_demo --if-empty # only on a brand-new database (used when deploying)
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from myapi.catalog_data import FILMS, ROOMS
from myapi.models import Actor, Film, Order, Rating, ScreeningRoom, TicketService, TimeSlot
from myapi.services.schedule import generate_schedule


class Command(BaseCommand):
    help = "Create demo rooms, films and showtimes."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete all films, rooms, showtimes, bookings and reviews first (users are kept).")
        parser.add_argument("--days", type=int, default=7, help="How many days of showtimes to create (default 7).")
        parser.add_argument("--if-empty", action="store_true",
                            help="Do nothing if there are already films (used by build.sh on every deploy).")

    def handle(self, *args, reset=False, days=7, if_empty=False, **options):
        if if_empty and Film.objects.exists():
            self.stdout.write("Films already exist; skipping the demo catalog.")
            return
        with transaction.atomic():
            if reset:
                TicketService.objects.all().delete()
                Order.objects.all().delete()
                TimeSlot.objects.all().delete()
                Rating.objects.all().delete()
                Film.objects.all().delete()
                ScreeningRoom.objects.all().delete()
                self.stdout.write("Removed old films, rooms, showtimes, bookings and reviews.")

            for r in ROOMS:
                ScreeningRoom.objects.update_or_create(
                    name=r["name"],
                    defaults=dict(kind=r["kind"], rows=r["rows"], columns=r["columns"],
                                  aisle_after=r["aisle_after"], premium_rows=r["premium_rows"],
                                  premium_surcharge=Decimal("3.00")),
                )

            created = updated = 0
            total = len(FILMS)
            for rank, f in enumerate(FILMS):
                released = date.fromisoformat(f["release_date"])
                film = Film.objects.filter(title=f["title"], release_date__year=released.year).first()
                fields = dict(
                    title_zh=f["title_zh"], director=f["director"], release_date=released,
                    runtime_minutes=f["runtime"], genres=f["genres"], language=f["language"],
                    overview=f["overview"], local_poster=f.get("local_poster", ""),
                    accent_color=f["accent"], now_showing=True,
                )
                if film is None:
                    film = Film(title=f["title"], popularity=total - rank, **fields)
                    created += 1
                else:
                    for key, value in fields.items():
                        setattr(film, key, value)
                    if not film.tmdb_id:
                        film.popularity = total - rank
                    updated += 1
                film.save()
                film.actors.all().delete()
                Actor.objects.bulk_create([Actor(film=film, name=n, order=i) for i, n in enumerate(f["cast"])])

        self.stdout.write(f"Films: {created} added, {updated} updated. Rooms: {len(ROOMS)}.")
        shows = generate_schedule(days=days)
        self.stdout.write(self.style.SUCCESS(f"Done. {shows} new showtime(s) for the next {days} day(s)."))
