"""Import real films and posters from The Movie Database (TMDB).

You need a free TMDB account and API key (https://www.themoviedb.org/settings/api).
Either the v3 "API Key" or the "API Read Access Token" works. Put it in .env as
TMDB_API_KEY=... or pass --api-key.

    python manage.py import_tmdb --enrich                 # real posters, backdrops, trailers for the built-in films
    python manage.py import_tmdb --now-playing 2          # add 2 pages (~40 films) of what's in US cinemas now
    python manage.py import_tmdb --upcoming 1             # add "coming soon" films
    python manage.py import_tmdb --now-playing 1 --reschedule   # ...and rebuild the unbooked showtime schedule

TMDB's API is free for non-commercial use with attribution; the site footer
shows the required notice automatically once any film comes from TMDB.
"""
import hashlib
import time
from datetime import date

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from myapi.models import Actor, Film
from myapi.services.schedule import generate_schedule
from myapi.services.schedule_reset import clear_unbooked_future_showtimes

API = "https://api.themoviedb.org/3"
GENRE_NAMES = {"Science Fiction": "Sci-Fi", "TV Movie": "TV Movie"}
ACCENTS = ["#1f6f4a", "#22324f", "#b5462a", "#8a3b24", "#2f4858", "#5b1f1f", "#3d6b57", "#8c2433",
           "#2f6db5", "#a5452c", "#c75b1e", "#55606b", "#1e4a6b", "#b8862e", "#3a5fa8", "#7b4fa0"]


class TMDB:
    def __init__(self, key):
        self.session = requests.Session()
        self.params = {}
        if key.startswith("eyJ"):  # v4 "API Read Access Token" (a JWT)
            self.session.headers["Authorization"] = f"Bearer {key}"
        else:  # v3 API key
            self.params["api_key"] = key
        self.session.headers["Accept"] = "application/json"
        self._images = None

    def get(self, path, **params):
        for attempt in range(4):
            response = self.session.get(f"{API}{path}", params={**self.params, **params}, timeout=20)
            if response.status_code == 429:
                time.sleep(int(response.headers.get("Retry-After", "2")) + attempt)
                continue
            if response.status_code == 401:
                raise CommandError("TMDB rejected the API key (401). Check TMDB_API_KEY.")
            response.raise_for_status()
            return response.json()
        raise CommandError("TMDB kept rate-limiting the requests (429). Try again in a minute.")

    def image(self, file_path, kind):
        if not file_path:
            return ""
        if self._images is None:
            self._images = self.get("/configuration")["images"]
        sizes = self._images.get("poster_sizes" if kind == "poster" else "backdrop_sizes", [])
        wanted = "w500" if kind == "poster" else "w1280"
        size = wanted if wanted in sizes else (sizes[-1] if sizes else "original")
        return f"{self._images.get('secure_base_url', 'https://image.tmdb.org/t/p/')}{size}{file_path}"

    def details(self, tmdb_id):
        return self.get(f"/movie/{tmdb_id}", language="en-US", append_to_response="credits,videos")


def _trailer_key(details):
    videos = [v for v in details.get("videos", {}).get("results", []) if v.get("site") == "YouTube"]
    videos.sort(key=lambda v: (v.get("type") != "Trailer", not v.get("official", False)))
    return videos[0]["key"] if videos else ""


def _director(details):
    names = [c["name"] for c in details.get("credits", {}).get("crew", []) if c.get("job") == "Director"]
    return ", ".join(dict.fromkeys(names)) or "Unknown"


def _language(details):
    spoken = details.get("spoken_languages") or []
    original = details.get("original_language")
    for lang in spoken:
        if lang.get("iso_639_1") == original and lang.get("english_name"):
            return lang["english_name"]
    return spoken[0].get("english_name", "") if spoken else (original or "")


def _accent(tmdb_id):
    return ACCENTS[int(hashlib.md5(str(tmdb_id).encode()).hexdigest(), 16) % len(ACCENTS)]


class Command(BaseCommand):
    help = "Import films, posters and trailers from TMDB."

    def add_arguments(self, parser):
        parser.add_argument("--api-key", default="", help="TMDB v3 API key or v4 read access token")
        parser.add_argument("--enrich", action="store_true", help="Add posters/backdrops/trailers to existing films")
        parser.add_argument("--now-playing", type=int, default=0, metavar="PAGES")
        parser.add_argument("--upcoming", type=int, default=0, metavar="PAGES")
        parser.add_argument("--region", default="US", help="Country for release lists (default US)")
        parser.add_argument("--reschedule", action="store_true",
                            help="Rebuild upcoming showtimes nobody has booked so new films get screenings")

    def handle(self, *args, **opts):
        key = opts["api_key"] or settings.TMDB_API_KEY
        if not key:
            raise CommandError("No TMDB key. Add TMDB_API_KEY=... to djangoProject/.env or pass --api-key.")
        if not (opts["enrich"] or opts["now_playing"] or opts["upcoming"]):
            raise CommandError("Say what to do: --enrich, --now-playing PAGES and/or --upcoming PAGES.")
        tmdb = TMDB(key)

        if opts["enrich"]:
            self.enrich(tmdb)
        if opts["now_playing"]:
            self.import_list(tmdb, "/movie/now_playing", opts["now_playing"], opts["region"], showing=True)
        if opts["upcoming"]:
            self.import_list(tmdb, "/movie/upcoming", opts["upcoming"], opts["region"], showing=False)
        if opts["reschedule"]:
            removed = clear_unbooked_future_showtimes()
            created = generate_schedule(days=settings.AUTO_SCHEDULE_DAYS or 7)
            self.stdout.write(f"Schedule rebuilt: removed {removed}, created {created} showtime(s).")
        self.stdout.write(self.style.SUCCESS("Done. Remember the TMDB attribution if you publish the site."))

    # --- add artwork to films we already have -----------------------------------------------------

    def enrich(self, tmdb):
        done = missed = 0
        for film in Film.objects.all():
            if film.tmdb_id:
                details = tmdb.details(film.tmdb_id)
            else:
                year = film.release_date.year
                results = tmdb.get("/search/movie", query=film.title, year=year, language="en-US").get("results", [])
                results = results or tmdb.get("/search/movie", query=film.title, language="en-US").get("results", [])
                match = next((r for r in results if (r.get("release_date") or "")[:4] in {str(year), str(year - 1), str(year + 1)}), None)
                if not match:
                    missed += 1
                    self.stdout.write(self.style.WARNING(f"  no TMDB match for {film}"))
                    continue
                if Film.objects.filter(tmdb_id=match["id"]).exclude(pk=film.pk).exists():
                    continue
                details = tmdb.details(match["id"])
            film.tmdb_id = details["id"]
            film.poster_url = tmdb.image(details.get("poster_path"), "poster") or film.poster_url
            film.backdrop_url = tmdb.image(details.get("backdrop_path"), "backdrop") or film.backdrop_url
            film.trailer_youtube_key = _trailer_key(details) or film.trailer_youtube_key
            film.save()
            done += 1
            self.stdout.write(f"  {film.title}: poster {'yes' if film.poster_url else 'no'}, "
                              f"trailer {'yes' if film.trailer_youtube_key else 'no'}")
        self.stdout.write(f"Enriched {done} film(s); {missed} without a match.")

    # --- import new films from a TMDB list ---------------------------------------------------------

    def import_list(self, tmdb, path, pages, region, showing):
        added = updated = 0
        today = timezone.localdate()
        for page in range(1, pages + 1):
            data = tmdb.get(path, language="en-US", page=page, region=region)
            for item in data.get("results", []):
                if not item.get("release_date"):
                    continue
                details = tmdb.details(item["id"])
                zh = tmdb.get(f"/movie/{item['id']}", language="zh-CN").get("title", "")
                released = date.fromisoformat(details["release_date"])
                with transaction.atomic():
                    film, created = Film.objects.get_or_create(
                        tmdb_id=details["id"],
                        defaults={"title": details["title"][:200], "director": "", "release_date": released})
                    film.title = details["title"][:200]
                    film.title_zh = zh[:200] if zh and zh != details["title"] else film.title_zh
                    film.director = _director(details)[:200]
                    film.release_date = released
                    film.runtime_minutes = details.get("runtime") or None
                    film.genres = ",".join(GENRE_NAMES.get(g["name"], g["name"]) for g in details.get("genres", []))[:200]
                    film.language = _language(details)[:100]
                    film.overview = details.get("overview", "")
                    film.poster_url = tmdb.image(details.get("poster_path"), "poster")
                    film.backdrop_url = tmdb.image(details.get("backdrop_path"), "backdrop")
                    film.trailer_youtube_key = _trailer_key(details)
                    film.popularity = float(details.get("popularity") or 0)
                    film.accent_color = film.accent_color or _accent(details["id"])
                    film.now_showing = showing or released <= today
                    film.save()
                    cast = sorted(details.get("credits", {}).get("cast", []), key=lambda c: c.get("order", 99))[:5]
                    film.actors.all().delete()
                    Actor.objects.bulk_create([Actor(film=film, name=c["name"][:120], order=i) for i, c in enumerate(cast)])
                added += created
                updated += not created
                self.stdout.write(f"  {'added' if created else 'updated'} {film}")
            if page >= data.get("total_pages", 1):
                break
        self.stdout.write(f"{path}: {added} added, {updated} updated.")
