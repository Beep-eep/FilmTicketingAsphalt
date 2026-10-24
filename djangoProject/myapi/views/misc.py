from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from myapi.models import Film


def _email_delivery():
    backend = settings.EMAIL_BACKEND
    if "console" in backend:
        return "console"
    if "smtp" in backend:
        return "smtp"
    if "Resend" in backend:
        return "resend"
    return backend.rsplit(".", 1)[-1]


@extend_schema(responses=dict)
@api_view(["GET"])
@permission_classes([AllowAny])
def config(request):
    """Settings the frontend needs to know about."""
    key = settings.STRIPE_SECRET_KEY
    return Response({
        "cinema_name": settings.CINEMA_NAME,
        "currency": settings.CURRENCY,
        "time_zone": settings.TIME_ZONE,
        "payment_provider": settings.PAYMENT_PROVIDER,
        "stripe_mode": ("live" if key.startswith(("sk_live", "rk_live")) else "test") if key else None,
        "require_email_verification": settings.REQUIRE_EMAIL_VERIFICATION,
        "email_delivery": _email_delivery(),
        "max_seats_per_order": settings.MAX_SEATS_PER_ORDER,
        "seat_hold_minutes": settings.SEAT_HOLD_MINUTES,
        "refund_cutoff_minutes": settings.REFUND_CUTOFF_MINUTES,
        "uses_tmdb": Film.objects.filter(tmdb_id__isnull=False).exists(),
    })


@extend_schema(responses=dict)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception as exc:  # noqa: BLE001
        return Response({"status": "error", "database": str(exc)}, status=503)
    return Response({"status": "ok", "database": db})
