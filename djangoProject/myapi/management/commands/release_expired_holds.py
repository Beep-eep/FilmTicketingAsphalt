from django.core.management.base import BaseCommand

from myapi.services.booking import release_expired_holds


class Command(BaseCommand):
    help = "Free seats held by unpaid bookings whose hold has run out. (The site also does this on its own.)"

    def handle(self, *args, **options):
        released = release_expired_holds()
        self.stdout.write(self.style.SUCCESS(f"Released {released} expired hold(s)."))
