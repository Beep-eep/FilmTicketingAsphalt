"""Top-level routes.

/api/...       JSON API used by the Vue app (docs at /api/docs/)
/admin/        Django admin for staff: films, showtimes, bookings, refunds
everything else  the Vue app itself, once it has been built with `npm run build`
"""
from functools import lru_cache

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.decorators.http import require_GET
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = f"{settings.CINEMA_NAME} admin"
admin.site.site_title = f"{settings.CINEMA_NAME} admin"
admin.site.index_title = "Films, showtimes and bookings"

NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Frontend not built</title>
<body style="font:16px/1.5 system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>The API is running</h1>
<p>The website itself is served by Vite while you develop. Open
<a href="http://localhost:5173">http://localhost:5173</a> (run <code>npm run dev</code> in the
<code>frontend</code> folder first).</p>
<p>To serve everything from this address instead, run <code>npm run build</code> in the
<code>frontend</code> folder, then restart this server.</p>
<p>Useful links: <a href="/api/docs/">API docs</a> · <a href="/admin/">Admin</a></p>
</body>"""


@lru_cache(maxsize=1)
def _index_html():
    index = settings.SPA_DIR / "index.html"
    return index.read_text(encoding="utf-8") if index.exists() else None


@require_GET
def spa(request, *args, **kwargs):
    html = _index_html() if not settings.DEBUG else (
        (settings.SPA_DIR / "index.html").read_text(encoding="utf-8")
        if (settings.SPA_DIR / "index.html").exists() else None)
    if html is None:
        return HttpResponse(NOT_BUILT)
    response = HttpResponse(html)
    response["Cache-Control"] = "no-cache"
    return response


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("api/", include("myapi.urls")),
    re_path(r"^(?!api/|admin/|static/).*$", spa, name="spa"),
]
