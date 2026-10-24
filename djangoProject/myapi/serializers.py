from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils import timezone
from rest_framework import serializers

from myapi.models import Film, Order, Rating, ScreeningRoom, TicketService, TimeSlot
from myapi.services.booking import booking_open, refund_deadline


# --- Films -----------------------------------------------------------------------------------

class FilmSummarySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="ID", read_only=True)
    year = serializers.SerializerMethodField()
    genres = serializers.SerializerMethodField()

    class Meta:
        model = Film
        fields = ["id", "title", "title_zh", "year", "runtime_minutes", "genres", "language",
                  "poster_url", "local_poster", "accent_color"]

    def get_year(self, film) -> int:
        return film.release_date.year

    def get_genres(self, film) -> list[str]:
        return film.genre_list


class FilmListSerializer(FilmSummarySerializer):
    avg_rating = serializers.SerializerMethodField()
    rating_count = serializers.IntegerField(read_only=True, default=0)
    show_dates = serializers.SerializerMethodField()

    class Meta(FilmSummarySerializer.Meta):
        fields = FilmSummarySerializer.Meta.fields + [
            "director", "release_date", "backdrop_url", "overview", "now_showing",
            "avg_rating", "rating_count", "show_dates", "popularity", "tmdb_id"]

    def get_avg_rating(self, film) -> float | None:
        avg = getattr(film, "avg_rating", None)
        return round(float(avg), 1) if avg is not None else None

    def get_show_dates(self, film) -> list[str]:
        return self.context.get("show_dates", {}).get(film.ID, [])


class FilmDetailSerializer(FilmListSerializer):
    cast = serializers.SerializerMethodField()

    class Meta(FilmListSerializer.Meta):
        fields = FilmListSerializer.Meta.fields + ["cast", "trailer_youtube_key"]

    def get_cast(self, film) -> list[str]:
        return [a.name for a in film.actors.all()]


# --- Showtimes and seats ------------------------------------------------------------------------

class RoomSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="ID", read_only=True)

    class Meta:
        model = ScreeningRoom
        fields = ["id", "name", "kind", "rows", "columns", "aisle_after", "premium_rows", "premium_surcharge"]


class ShowtimeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="ID", read_only=True)
    price = serializers.DecimalField(source="ticketPrice", max_digits=10, decimal_places=2, read_only=True)
    end_time = serializers.DateTimeField(read_only=True)
    room = serializers.SerializerMethodField()
    seats_total = serializers.SerializerMethodField()
    seats_available = serializers.IntegerField(read_only=True, default=None)
    booking_open = serializers.SerializerMethodField()

    class Meta:
        model = TimeSlot
        fields = ["id", "begin_time", "end_time", "price", "format", "audio_language", "subtitles",
                  "room", "seats_total", "seats_available", "booking_open"]

    def get_room(self, ts) -> dict:
        r = ts.ScreeningRoom
        return {"id": r.ID, "name": r.name, "kind": r.kind}

    def get_seats_total(self, ts) -> int:
        return ts.ScreeningRoom.capacity

    def get_booking_open(self, ts) -> bool:
        return booking_open(ts)


# --- Reviews ------------------------------------------------------------------------------------

class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    score = serializers.DecimalField(source="film_rating", max_digits=3, decimal_places=1,
                                     min_value=1, max_value=10, coerce_to_string=False)

    class Meta:
        model = Rating
        fields = ["id", "username", "score", "comment", "created_at", "updated_at"]
        read_only_fields = ["id", "username", "created_at", "updated_at"]


# --- Orders -------------------------------------------------------------------------------------

class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketService
        fields = ["id", "seat_number", "seat_label", "price", "status", "refunded_at"]


class OrderSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)
    showtime = serializers.SerializerMethodField()
    can_pay = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_refund = serializers.SerializerMethodField()
    refund_deadline = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ["code", "status", "status_label", "amount_total", "amount_refunded", "currency",
                  "payment_provider", "hold_expires_at", "paid_at", "created_at", "note",
                  "can_pay", "can_cancel", "can_refund", "refund_deadline", "showtime", "tickets"]

    def get_showtime(self, order) -> dict:
        ts = order.timeslot
        return {
            "id": ts.ID,
            "begin_time": ts.begin_time,
            "end_time": ts.end_time,
            "format": ts.format,
            "room": ts.ScreeningRoom.name,
            "film": FilmSummarySerializer(ts.film).data,
        }

    def get_can_pay(self, order) -> bool:
        return bool(order.is_active_hold and booking_open(order.timeslot))

    def get_can_cancel(self, order) -> bool:
        return order.status == Order.PENDING

    def get_can_refund(self, order) -> bool:
        return (order.status in (Order.PAID, Order.PARTIALLY_REFUNDED)
                and timezone.now() < refund_deadline(order.timeslot))

    def get_refund_deadline(self, order) -> datetime:
        return refund_deadline(order.timeslot)


class CreateOrderSerializer(serializers.Serializer):
    showtime = serializers.IntegerField()
    seats = serializers.ListField(child=serializers.IntegerField(), allow_empty=False,
                                  max_length=settings.MAX_SEATS_PER_ORDER)


class RefundSerializer(serializers.Serializer):
    ticket_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


# --- Accounts -----------------------------------------------------------------------------------

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined", "is_staff"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150, validators=[UnicodeUsernameValidator()])
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is taken. Try another one.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account already uses this email. Sign in, or reset your password.")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs["email"])
        validate_password(attrs["password"], user=candidate)
        return attrs


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class TokenPairInputSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()


class PasswordResetConfirmSerializer(TokenPairInputSerializer):
    new_password = serializers.CharField(min_length=8, max_length=128, write_only=True)
