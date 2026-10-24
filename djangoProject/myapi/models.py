import secrets
import string
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

# Table and column names from the original project (e.g. `ID`, `ScreeningRoom`,
# `ticketPrice`, `rating`, `TicketService`) are kept on purpose, so an existing
# database upgrades with `python manage.py migrate` instead of being rebuilt.

ROW_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O: they look like 1 and 0 on a ticket


def seat_label(seat_number, columns):
    """Seat 1 is the front-left seat. Returns e.g. 'C7'."""
    row_index = (seat_number - 1) // columns
    col = (seat_number - 1) % columns + 1
    letter = ROW_LETTERS[row_index] if row_index < len(ROW_LETTERS) else f"R{row_index + 1}-"
    return f"{letter}{col}"


class Film(models.Model):
    ID = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200, verbose_name="title")
    title_zh = models.CharField(max_length=200, blank=True, verbose_name="Chinese title")
    director = models.CharField(max_length=200, verbose_name="director")
    release_date = models.DateField(verbose_name="release date")
    now_showing = models.BooleanField(default=True)
    overview = models.TextField(blank=True)
    runtime_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    genres = models.CharField(max_length=200, blank=True, help_text="Comma-separated, e.g. Action,Sci-Fi")
    language = models.CharField(max_length=100, blank=True)
    poster_url = models.URLField(max_length=500, blank=True)
    backdrop_url = models.URLField(max_length=500, blank=True)
    local_poster = models.CharField(
        max_length=50, blank=True,
        help_text="Name of a poster bundled with the frontend (frontend/src/assets/posters/<name>.jpg)",
    )
    trailer_youtube_key = models.CharField(max_length=32, blank=True)
    accent_color = models.CharField(max_length=7, blank=True, help_text="Hex colour for generated poster art")
    tmdb_id = models.IntegerField(null=True, blank=True, unique=True)
    popularity = models.FloatField(default=0)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-popularity", "title"]

    def __str__(self):
        return f"{self.title} ({self.release_date.year})"

    @property
    def genre_list(self):
        return [g.strip() for g in self.genres.split(",") if g.strip()]


class Actor(models.Model):
    film = models.ForeignKey(Film, on_delete=models.CASCADE, related_name="actors")
    name = models.CharField(max_length=120)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class ScreeningRoom(models.Model):
    KIND_CHOICES = [
        ("standard", "Standard"),
        ("imax", "IMAX"),
        ("dolby", "Dolby Cinema"),
        ("studio", "Studio"),
    ]
    ID = models.AutoField(primary_key=True)
    name = models.CharField(max_length=60, verbose_name="screening room name")
    rows = models.PositiveSmallIntegerField()
    columns = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="standard")
    aisle_after = models.PositiveSmallIntegerField(
        default=0, help_text="Leave a walkway after this column (0 = no aisle)")
    premium_rows = models.CharField(
        max_length=50, blank=True, help_text="Row numbers with premium seats, e.g. 5,6 (row 1 is the front)")
    premium_surcharge = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("3.00"))

    def __str__(self):
        return self.name

    @property
    def capacity(self):
        return self.rows * self.columns

    @property
    def premium_row_set(self):
        return {int(r) for r in self.premium_rows.split(",") if r.strip().isdigit()}

    def is_premium(self, seat_number):
        return ((seat_number - 1) // self.columns + 1) in self.premium_row_set


class TimeSlot(models.Model):
    """A showtime: one film in one room at one time."""
    FORMAT_CHOICES = [("2D", "2D"), ("3D", "3D"), ("IMAX", "IMAX"), ("Dolby", "Dolby Cinema")]
    ID = models.AutoField(primary_key=True)
    film = models.ForeignKey(Film, on_delete=models.CASCADE, related_name="showtimes")
    ScreeningRoom = models.ForeignKey(ScreeningRoom, on_delete=models.CASCADE, related_name="showtimes")
    begin_time = models.DateTimeField(verbose_name="screening time", db_index=True)
    ticketPrice = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("12.50"))
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default="2D")
    audio_language = models.CharField(max_length=60, blank=True)
    subtitles = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["begin_time"]
        verbose_name = "showtime"

    def __str__(self):
        local = timezone.localtime(self.begin_time)
        return f"{self.film.title} — {local:%a %b %d %H:%M} — {self.ScreeningRoom.name}"

    def price_for_seat(self, seat_number):
        price = self.ticketPrice
        if self.ScreeningRoom.is_premium(seat_number):
            price += self.ScreeningRoom.premium_surcharge
        return price

    @property
    def end_time(self):
        minutes = self.film.runtime_minutes or 120
        return self.begin_time + timedelta(minutes=minutes)


class SeatStatus(models.Model):
    ID = models.AutoField(primary_key=True)
    seat_number = models.IntegerField()
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name="seats")
    is_occupied = models.BooleanField(default=False)

    class Meta:
        unique_together = (("seat_number", "timeslot"),)
        indexes = [models.Index(fields=["timeslot", "seat_number"])]
        verbose_name = "seat"


def _order_code():
    alphabet = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1")
    return "AC-" + "".join(secrets.choice(alphabet) for _ in range(6))


class Order(models.Model):
    """One checkout: some seats for one showtime, paid together."""
    PENDING, PAID, CANCELLED, EXPIRED = "pending", "paid", "cancelled", "expired"
    REFUNDED, PARTIALLY_REFUNDED = "refunded", "partially_refunded"
    STATUS_CHOICES = [
        (PENDING, "Waiting for payment"),
        (PAID, "Paid"),
        (PARTIALLY_REFUNDED, "Partly refunded"),
        (REFUNDED, "Refunded"),
        (CANCELLED, "Cancelled"),
        (EXPIRED, "Expired"),
    ]
    code = models.CharField(max_length=16, unique=True, default=_order_code, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    amount_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    amount_refunded = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="usd")
    payment_provider = models.CharField(max_length=10, default="demo")
    stripe_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    confirmation_email_sent = models.BooleanField(default=False)
    site_url = models.CharField(max_length=200, blank=True, help_text="Address the customer booked from; used for links in emails")
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} ({self.get_status_display()})"

    @property
    def is_active_hold(self):
        return self.status == self.PENDING and self.hold_expires_at and self.hold_expires_at > timezone.now()


class TicketService(models.Model):
    """A ticket for one seat. (Table name kept from the original project.)"""
    HELD, PAID, REFUNDED, CANCELLED, EXPIRED = "held", "paid", "refunded", "cancelled", "expired"
    STATUS_CHOICES = [
        (HELD, "Held"), (PAID, "Paid"), (REFUNDED, "Refunded"),
        (CANCELLED, "Cancelled"), (EXPIRED, "Expired"),
    ]
    ACTIVE = (HELD, PAID)

    timeslot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name="tickets")
    seat_number = models.IntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tickets")
    is_paid = models.BooleanField(default=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tickets", null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PAID)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    seat_label = models.CharField(max_length=8, blank=True)
    stripe_refund_id = models.CharField(max_length=255, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        indexes = [models.Index(fields=["user"])]
        verbose_name = "ticket"

    def __str__(self):
        return f"{self.seat_label or self.seat_number} — {self.timeslot}"


class rating(models.Model):
    """A user's score (1–10) and optional short review of a film."""
    film = models.ForeignKey(Film, on_delete=models.CASCADE, related_name="ratings")
    film_rating = models.DecimalField(max_digits=3, decimal_places=1)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    comment = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("film", "user"),)
        ordering = ["-updated_at"]
        verbose_name = "review"

    def __str__(self):
        return f"{self.user} → {self.film}: {self.film_rating}"


Rating = rating  # readable alias; the table name stays myapi_rating


@receiver(signal=pre_delete, sender=TicketService)
def change_seat_status_to_unoccupied(sender, instance, **kwargs):
    """Deleting an active ticket (e.g. in the admin) frees its seat."""
    if instance.status in TicketService.ACTIVE:
        SeatStatus.objects.filter(
            timeslot_id=instance.timeslot_id, seat_number=instance.seat_number
        ).update(is_occupied=False)


@receiver(signal=post_save, sender=TimeSlot)
def create_seats_for_new_showtime(sender, instance, created, raw=False, **kwargs):
    """Every new showtime (admin, scheduler or seed) gets one seat row per seat in its room."""
    if not created or raw or instance.seats.exists():
        return
    SeatStatus.objects.bulk_create(
        [SeatStatus(timeslot=instance, seat_number=n) for n in range(1, instance.ScreeningRoom.capacity + 1)],
        batch_size=1000,
    )
