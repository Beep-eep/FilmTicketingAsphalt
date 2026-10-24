from datetime import timedelta

from django.db.models import Avg, Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from myapi.models import Actor, Film, Rating, SeatStatus, TicketService, TimeSlot, seat_label
from myapi.serializers import (FilmDetailSerializer, FilmListSerializer, FilmSummarySerializer,
                               ReviewSerializer, RoomSerializer, ShowtimeSerializer)
from myapi.services.booking import booking_open, release_expired_holds
from myapi.services.schedule import as_local_date, ensure_schedule

SHOW_WINDOW_DAYS = 8


def _with_ratings(qs):
    ratings = Rating.objects.filter(film=OuterRef("pk")).values("film")
    return qs.annotate(
        avg_rating=Subquery(ratings.annotate(a=Avg("film_rating")).values("a")[:1]),
        rating_count=Coalesce(
            Subquery(ratings.annotate(c=Count("id")).values("c")[:1], output_field=IntegerField()),
            Value(0),
        ),
    )


def _show_dates(film_ids):
    now = timezone.now()
    rows = (TimeSlot.objects
            .filter(film_id__in=film_ids, begin_time__gte=now, begin_time__lt=now + timedelta(days=SHOW_WINDOW_DAYS))
            .values_list("film_id", "begin_time"))
    dates = {}
    for film_id, begin in rows:
        dates.setdefault(film_id, set()).add(as_local_date(begin).isoformat())
    return {k: sorted(v) for k, v in dates.items()}


@extend_schema(parameters=[
    OpenApiParameter("status", str, description="now (default), soon or all"),
    OpenApiParameter("search", str, description="Title (English or Chinese), director or cast"),
    OpenApiParameter("genre", str),
], responses=FilmListSerializer(many=True))
@api_view(["GET"])
@permission_classes([AllowAny])
def film_list(request):
    ensure_schedule()
    qs = Film.objects.all()
    status = request.query_params.get("status", "now")
    if status == "now":
        qs = qs.filter(now_showing=True)
    elif status == "soon":
        qs = qs.filter(now_showing=False, release_date__gt=timezone.localdate())
    search = request.query_params.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(title_zh__icontains=search) | Q(director__icontains=search)
            | Q(ID__in=Actor.objects.filter(name__icontains=search).values("film_id"))
        )
    genre = request.query_params.get("genre", "").strip()
    if genre:
        qs = qs.filter(genres__icontains=genre)
    films = list(_with_ratings(qs)[:300])
    ctx = {"show_dates": _show_dates([f.ID for f in films])}
    return Response(FilmListSerializer(films, many=True, context=ctx).data)


@extend_schema(responses=FilmDetailSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def film_detail(request, film_id):
    film = get_object_or_404(_with_ratings(Film.objects.prefetch_related("actors")), ID=film_id)
    ctx = {"show_dates": _show_dates([film.ID])}
    return Response(FilmDetailSerializer(film, context=ctx).data)


@extend_schema(responses=ShowtimeSerializer(many=True))
@api_view(["GET"])
@permission_classes([AllowAny])
def film_showtimes(request, film_id):
    film = get_object_or_404(Film, ID=film_id)
    release_expired_holds()
    now = timezone.now()
    qs = (TimeSlot.objects
          .filter(film=film, begin_time__gte=now - timedelta(minutes=30),
                  begin_time__lt=now + timedelta(days=SHOW_WINDOW_DAYS))
          .select_related("ScreeningRoom", "film")
          .annotate(seats_available=Count("seats", filter=Q(seats__is_occupied=False)))
          .order_by("begin_time"))
    return Response(ShowtimeSerializer(qs, many=True).data)


@extend_schema(methods=["GET"], responses=ReviewSerializer(many=True))
@extend_schema(methods=["POST"], request=ReviewSerializer, responses=ReviewSerializer)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedOrReadOnly])
def film_reviews(request, film_id):
    film = get_object_or_404(Film, ID=film_id)
    if request.method == "GET":
        reviews = Rating.objects.filter(film=film).select_related("user")[:50]
        mine = None
        if request.user.is_authenticated:
            own = Rating.objects.filter(film=film, user=request.user).first()
            mine = ReviewSerializer(own).data if own else None
        return Response({"results": ReviewSerializer(reviews, many=True).data, "mine": mine})

    serializer = ReviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    review, created = Rating.objects.update_or_create(
        film=film, user=request.user,
        defaults={"film_rating": serializer.validated_data["film_rating"],
                  "comment": serializer.validated_data.get("comment", "").strip()},
    )
    return Response(ReviewSerializer(review).data, status=201 if created else 200)


@extend_schema(responses=dict)
@api_view(["GET"])
@permission_classes([AllowAny])
def showtime_detail(request, showtime_id):
    """Everything the seat map needs: the showtime, the room layout and every seat's state."""
    release_expired_holds(timeslot_id=showtime_id)
    ts = get_object_or_404(TimeSlot.objects.select_related("film", "ScreeningRoom"), ID=showtime_id)
    room = ts.ScreeningRoom
    mine_paid, mine_held, my_order = set(), set(), None
    if request.user.is_authenticated:
        for number, status, code in (TicketService.objects
                                     .filter(timeslot=ts, user=request.user, status__in=TicketService.ACTIVE)
                                     .values_list("seat_number", "status", "order__code")):
            (mine_paid if status == TicketService.PAID else mine_held).add(number)
            if status == TicketService.HELD:
                my_order = code

    seats = []
    for seat_id, number, occupied in (SeatStatus.objects.filter(timeslot=ts)
                                      .order_by("seat_number").values_list("ID", "seat_number", "is_occupied")):
        if number in mine_paid:
            state = "mine"
        elif number in mine_held:
            state = "held"
        else:
            state = "taken" if occupied else "available"
        row = (number - 1) // room.columns + 1
        col = (number - 1) % room.columns + 1
        seats.append({
            "id": seat_id, "number": number, "row": row, "col": col,
            "label": seat_label(number, room.columns),
            "premium": row in room.premium_row_set,
            "price": str(ts.price_for_seat(number)),
            "status": state,
        })
    return Response({
        "id": ts.ID,
        "begin_time": ts.begin_time,
        "end_time": ts.end_time,
        "format": ts.format,
        "audio_language": ts.audio_language,
        "subtitles": ts.subtitles,
        "price": str(ts.ticketPrice),
        "booking_open": booking_open(ts),
        "film": FilmSummarySerializer(ts.film).data,
        "room": RoomSerializer(room).data,
        "seats": seats,
        "my_pending_order": my_order,
    })
