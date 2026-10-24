"""One error shape for the whole API: {"detail": "...", "code": "...", "fields": {...}}.

The frontend shows `detail` to the person, so every message is written to be read
by a customer: what went wrong and what to do next.
"""
import math

from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from myapi.services.booking import BookingError
from myapi.services.payments import PaymentError


def _first_message(data):
    if isinstance(data, list) and data:
        return _first_message(data[0])
    if isinstance(data, dict) and data:
        return _first_message(next(iter(data.values())))
    return str(data)


def exception_handler(exc, context):
    if isinstance(exc, BookingError):
        return Response({"detail": exc.message, "code": exc.code, **exc.extra}, status=exc.status)
    if isinstance(exc, PaymentError):
        return Response({"detail": str(exc), "code": "payment_error"}, status=status.HTTP_502_BAD_GATEWAY)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    if isinstance(exc, Throttled):
        minutes = max(1, math.ceil((exc.wait or 60) / 60))
        response.data = {"detail": f"Too many attempts from this network. Try again in {minutes} minute"
                                   f"{'s' if minutes != 1 else ''}.", "code": "throttled"}
        return response
    data = response.data
    if isinstance(data, dict) and "detail" in data:
        code = getattr(data["detail"], "code", None) or getattr(exc, "default_code", "error")
        response.data = {"detail": str(data["detail"]), "code": code}
    else:
        response.data = {"detail": _first_message(data), "code": "invalid", "fields": data}
    return response
