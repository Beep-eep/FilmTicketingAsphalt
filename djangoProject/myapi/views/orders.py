import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from myapi.models import Order
from myapi.serializers import CreateOrderSerializer, OrderSerializer, RefundSerializer
from myapi.services import booking
from myapi.services.payments import DemoProvider, PaymentError, StripeProvider, get_provider
from myapi.services.site import site_url

log = logging.getLogger(__name__)


def _orders_for(user):
    return (Order.objects.filter(user=user)
            .select_related("timeslot__film", "timeslot__ScreeningRoom")
            .prefetch_related("tickets"))


def _own_order(request, code):
    return get_object_or_404(_orders_for(request.user), code=code)


@extend_schema(methods=["GET"], responses=OrderSerializer(many=True))
@extend_schema(methods=["POST"], request=CreateOrderSerializer, responses=OrderSerializer)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def orders(request):
    """GET: my bookings. POST: hold seats for a showtime."""
    if request.method == "GET":
        booking.release_expired_holds(user=request.user)
        return Response(OrderSerializer(_orders_for(request.user), many=True).data)

    s = CreateOrderSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    order = booking.create_order(request.user, s.validated_data["showtime"], s.validated_data["seats"],
                                 site_url=site_url(request))
    return Response(OrderSerializer(_own_order(request, order.code)).data, status=201)


@extend_schema(responses=OrderSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail(request, code):
    booking.release_expired_holds(user=request.user)
    return Response(OrderSerializer(_own_order(request, code)).data)


@extend_schema(request=None, responses=dict)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_checkout(request, code):
    """Start paying: returns the address of the payment page."""
    booking.release_expired_holds(user=request.user)
    order = _own_order(request, code)
    if not order.is_active_hold:
        raise booking.BookingError("This booking has expired. Choose your seats again.", "hold_expired", 409)
    if not booking.booking_open(order.timeslot):
        raise booking.BookingError("Booking has closed for this showtime.", "booking_closed")
    provider = get_provider(order.payment_provider)
    url = provider.start_checkout(order, site_url(request), locale=request.data.get("locale", "auto"))
    return Response({"checkout_url": url, "provider": provider.name})


@extend_schema(request=None, responses=OrderSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_cancel(request, code):
    order = booking.cancel_order(_own_order(request, code))
    return Response(OrderSerializer(_own_order(request, order.code)).data)


@extend_schema(request=RefundSerializer, responses=dict)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def order_refund(request, code):
    s = RefundSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    order, amount = booking.refund_tickets(_own_order(request, code), s.validated_data.get("ticket_ids"))
    return Response({"refunded": str(amount), "order": OrderSerializer(_own_order(request, order.code)).data})


# --- Payment results ---------------------------------------------------------------------------

@extend_schema(request=dict, responses=OrderSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stripe_confirm(request):
    """Called by the page Stripe sends the customer back to. Fulfils immediately if paid."""
    session_id = (request.data.get("session_id") or "").strip()
    if not session_id.startswith("cs_"):
        raise booking.BookingError("That payment reference isn't valid.", "invalid_session")
    order = StripeProvider().fulfill(session_id)
    if order.user_id != request.user.id:
        raise booking.BookingError("This payment belongs to a different account.", "forbidden", 403)
    return Response(OrderSerializer(_own_order(request, order.code)).data)


@extend_schema(request=dict, responses=OrderSerializer)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def demo_payment(request, code):
    """Demo provider only: simulate the result of a payment."""
    order = _own_order(request, code)
    if order.payment_provider != "demo":
        raise booking.BookingError("This booking uses real payments.", "not_demo")
    if request.data.get("outcome") == "decline":
        raise booking.BookingError("The demo card was declined. Nothing was charged; try again.", "declined", 402)
    if order.status == Order.PENDING and not order.is_active_hold:
        booking.release_expired_holds(user=request.user)
        raise booking.BookingError("This booking has expired. Choose your seats again.", "hold_expired", 409)
    DemoProvider().complete(order)
    return Response(OrderSerializer(_own_order(request, code)).data)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Stripe → server notifications. Verified with STRIPE_WEBHOOK_SECRET."""
    if settings.PAYMENT_PROVIDER != "stripe":
        return HttpResponse(status=404)
    provider = StripeProvider()
    try:
        event = provider.construct_event(request.body, request.headers.get("Stripe-Signature"))
    except (ValueError, PaymentError) as exc:
        log.warning("Rejected Stripe webhook: %s", exc)
        return HttpResponse(status=400)
    except Exception as exc:  # stripe.SignatureVerificationError
        log.warning("Rejected Stripe webhook signature: %s", exc)
        return HttpResponse(status=400)
    try:
        provider.handle_event(event)
    except Order.DoesNotExist:
        log.warning("Stripe event %s refers to an unknown booking", event.id)
    return HttpResponse(status=200)
