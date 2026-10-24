from django.core.management.base import BaseCommand

from myapi.services.schedule import generate_schedule


class Command(BaseCommand):
    help = "Make sure every room has showtimes for the next N days (default 7). Safe to run repeatedly."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, days=7, **options):
        created = generate_schedule(days=days)
        self.stdout.write(self.style.SUCCESS(f"Created {created} showtime(s)."))
