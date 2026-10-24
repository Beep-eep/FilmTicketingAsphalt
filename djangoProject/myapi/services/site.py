"""Working out the public address of the site (for links in emails and Stripe redirects)."""
import os
from urllib.parse import urlsplit

from django.conf import settings
from django.http.request import split_domain_port, validate_host


def _allowed(origin):
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    domain, _port = split_domain_port(parts.netloc)
    return bool(domain) and validate_host(domain, settings.ALLOWED_HOSTS)


def site_url(request=None):
    """FRONTEND_URL if set; otherwise the address the visitor is using right now."""
    if settings.FRONTEND_URL:
        return settings.FRONTEND_URL
    if request is not None:
        origin = request.headers.get("Origin")
        if not origin:
            referer = request.headers.get("Referer", "")
            if referer:
                p = urlsplit(referer)
                origin = f"{p.scheme}://{p.netloc}"
        if origin and _allowed(origin):
            return origin.rstrip("/")
        return f"{request.scheme}://{request.get_host()}"
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        return f"https://{host}"
    return "http://localhost:5173"
