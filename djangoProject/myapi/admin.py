"""Staff back office at /admin/.

Create a login with `python manage.py createsuperuser`. From here staff can add
films (with cast), rooms and showtimes (seats are created automatically), look
up bookings by code or email, and refund or cancel them.
"""
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from myapi.models import Actor, Film, Order, Rating, ScreeningRoom, SeatStatus, TicketService, TimeSlot
from myapi.services import booking
from myapi.services.schedule import generate_schedule


class ActorInline(admin.TabularInline):
    model = Actor
    extra = 1
    fields = ["name", "order"]


class ShowtimeInline(admin.TabularInline):
    model = TimeSlot
    extra = 0
    fields = ["begin_time", "ScreeningRoom", "format", "ticketPrice"]
    ordering = ["begin_time"]
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).filter(begin_time__gte=timezone.now())


@admin.register(Film)
class FilmAdmin(admin.ModelAdmin):
    list_display = ["title", "title_zh", "year", "director", "runtime_minutes", "genres", "now_showing",
                    "upcoming_showtimes", "has_poster"]
    list_filter = ["now_showing", "language"]
    list_editable = ["now_showing"]
    search_fields = ["title", "title_zh", "director", "actors__name"]
    inlines = [ActorInline, ShowtimeInline]
    actions = ["schedule_week"]
    fieldsets = [
        (None, {"fields": ["title", "title_zh", "director", "release_date", "runtime_minutes", "genres",
                           "language", "now_showing", "overview"]}),
        ("Artwork and media", {"fields": ["poster_url", "backdrop_url", "local_poster", "accent_color",
                                          "trailer_youtube_key"]}),
        ("Data source", {"classes": ["collapse"], "fields": ["tmdb_id", "popularity"]}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _upcoming=Count("showtimes", filter=Q(showtimes__begin_time__gte=timezone.now())))

    @admin.display(ordering="release_date")
    def year(self, film):
        return film.release_date.year

    @admin.display(ordering="_upcoming", description="upcoming")
    def upcoming_showtimes(self, film):
        return film._upcoming

    @admin.display(boolean=True, description="poster")
    def has_poster(self, film):
        return bool(film.poster_url or film.local_poster)

    @admin.action(description="Fill the next 7 days with showtimes (all showing films)")
    def schedule_week(self, request, queryset):
        created = generate_schedule(days=7)
        self.message_user(request, f"Created {created} showtime(s).", messages.SUCCESS)


@admin.register(ScreeningRoom)
class ScreeningRoomAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "rows", "columns", "capacity", "premium_rows"]


@admin.register(TimeSlot)
class ShowtimeAdmin(admin.ModelAdmin):
    list_display = ["film", "begin_time", "ScreeningRoom", "format", "ticketPrice", "seats_sold"]
    list_filter = ["ScreeningRoom", "format", ("begin_time", admin.DateFieldListFilter)]
    search_fields = ["film__title", "film__title_zh"]
    autocomplete_fields = ["film"]
    # No date_hierarchy: on MySQL it needs time-zone tables that Homebrew's MySQL doesn't load.

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("film", "ScreeningRoom").annotate(
            _sold=Count("seats", filter=Q(seats__is_occupied=True)))

    @admin.display(ordering="_sold", description="seats taken")
    def seats_sold(self, ts):
        return f"{ts._sold} / {ts.ScreeningRoom.capacity}"


class TicketInline(admin.TabularInline):
    model = TicketService
    extra = 0
    can_delete = False
    fields = ["seat_label", "price", "status", "stripe_refund_id", "refunded_at"]
    readonly_fields = fields


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["code", "user", "email", "film", "showtime", "seats", "amount_total", "status_badge",
                    "payment_provider", "created_at"]
    list_filter = ["status", "payment_provider", ("created_at", admin.DateFieldListFilter)]
    search_fields = ["code", "user__username", "user__email", "timeslot__film__title", "stripe_session_id",
                     "stripe_payment_intent"]
    readonly_fields = ["code", "user", "timeslot", "status", "amount_total", "amount_refunded", "currency",
                       "payment_provider", "stripe_session_id", "stripe_payment_intent", "hold_expires_at",
                       "paid_at", "confirmation_email_sent", "site_url", "created_at", "updated_at",
                       "stripe_link"]
    fields = readonly_fields + ["note"]
    inlines = [TicketInline]
    actions = ["refund_orders", "cancel_orders"]

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related("user", "timeslot__film", "timeslot__ScreeningRoom")
                .prefetch_related("tickets"))

    def has_add_permission(self, request):
        return False

    def email(self, order):
        return order.user.email

    def film(self, order):
        return order.timeslot.film.title

    def showtime(self, order):
        return timezone.localtime(order.timeslot.begin_time).strftime("%b %d %H:%M")

    def seats(self, order):
        return ", ".join(t.seat_label for t in order.tickets.all() if t.status in TicketService.ACTIVE) or "—"

    @admin.display(description="status", ordering="status")
    def status_badge(self, order):
        colours = {"paid": "#2e7d32", "pending": "#b26a00", "refunded": "#555", "partially_refunded": "#555",
                   "cancelled": "#999", "expired": "#999"}
        return format_html('<b style="color:{}">{}</b>', colours.get(order.status, "#333"),
                           order.get_status_display())

    @admin.display(description="Stripe")
    def stripe_link(self, order):
        if not order.stripe_payment_intent or order.payment_provider != "stripe":
            return "—"
        return format_html('<a href="https://dashboard.stripe.com/payments/{}" target="_blank" rel="noopener">'
                           'Open payment in Stripe</a>', order.stripe_payment_intent)

    @admin.action(description="Refund all paid tickets (ignores the refund deadline)")
    def refund_orders(self, request, queryset):
        done = 0
        for order in queryset:
            try:
                booking.refund_tickets(order, by_staff=True)
                done += 1
            except booking.BookingError as exc:
                self.message_user(request, f"{order.code}: {exc.message}", messages.WARNING)
        if done:
            self.message_user(request, f"Refunded {done} booking(s).", messages.SUCCESS)

    @admin.action(description="Cancel unpaid bookings and free their seats")
    def cancel_orders(self, request, queryset):
        done = 0
        for order in queryset.filter(status=Order.PENDING):
            booking.cancel_order(order)
            done += 1
        self.message_user(request, f"Cancelled {done} booking(s).", messages.SUCCESS)


@admin.register(Rating)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["film", "user", "film_rating", "comment", "updated_at"]
    search_fields = ["film__title", "user__username", "comment"]
    list_filter = ["film_rating"]


@admin.register(SeatStatus)
class SeatAdmin(admin.ModelAdmin):
    list_display = ["timeslot", "seat_number", "is_occupied"]
    list_filter = ["is_occupied"]
    raw_id_fields = ["timeslot"]

    def has_module_permission(self, request):
        return False  # managed automatically; still reachable by URL for debugging
