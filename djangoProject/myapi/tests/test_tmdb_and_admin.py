from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from myapi.models import Film, TimeSlot

CONFIG = {"images": {"secure_base_url": "https://image.tmdb.org/t/p/",
                     "poster_sizes": ["w92", "w500", "original"],
                     "backdrop_sizes": ["w300", "w780", "w1280", "original"]}}
DETAILS = {
    "id": 603, "title": "The Matrix", "release_date": "1999-03-30", "runtime": 136,
    "genres": [{"id": 28, "name": "Action"}, {"id": 878, "name": "Science Fiction"}],
    "overview": "TMDB overview", "poster_path": "/p.jpg", "backdrop_path": "/b.jpg", "popularity": 77.5,
    "original_language": "en", "spoken_languages": [{"english_name": "English", "iso_639_1": "en", "name": "English"}],
    "credits": {"cast": [{"name": "Keanu Reeves", "order": 0}, {"name": "Carrie-Anne Moss", "order": 2},
                         {"name": "Laurence Fishburne", "order": 1}],
                "crew": [{"job": "Director", "name": "Lana Wachowski"}, {"job": "Director", "name": "Lilly Wachowski"},
                         {"job": "Producer", "name": "Joel Silver"}]},
    "videos": {"results": [{"site": "YouTube", "type": "Teaser", "key": "teaser1", "official": True},
                           {"site": "YouTube", "type": "Trailer", "key": "trailer1", "official": True}]},
}


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


def fake_get(url, params=None, timeout=None):
    if url.endswith("/configuration"):
        return FakeResponse(CONFIG)
    if url.endswith("/search/movie"):
        return FakeResponse({"results": [{"id": 603, "title": "The Matrix", "release_date": "1999-03-30"}]})
    if url.endswith("/movie/now_playing"):
        return FakeResponse({"page": 1, "total_pages": 1, "results": [{"id": 603, "release_date": "1999-03-30"}]})
    if url.endswith("/movie/603") and params.get("language") == "zh-CN":
        return FakeResponse({"title": "黑客帝国"})
    if url.endswith("/movie/603"):
        return FakeResponse(DETAILS)
    raise AssertionError(url)


@override_settings(TMDB_API_KEY="abc123")
class TmdbImportTests(TestCase):
    def run_cmd(self, *args):
        out = StringIO()
        with mock.patch("requests.Session.get", side_effect=fake_get):
            call_command("import_tmdb", *args, stdout=out)
        return out.getvalue()

    def test_enrich_adds_artwork_to_existing_film(self):
        film = Film.objects.create(title="The Matrix", director="The Wachowskis", release_date="1999-03-31")
        self.run_cmd("--enrich")
        film.refresh_from_db()
        self.assertEqual(film.tmdb_id, 603)
        self.assertEqual(film.poster_url, "https://image.tmdb.org/t/p/w500/p.jpg")
        self.assertEqual(film.backdrop_url, "https://image.tmdb.org/t/p/w1280/b.jpg")
        self.assertEqual(film.trailer_youtube_key, "trailer1")
        self.assertEqual(film.director, "The Wachowskis")  # our own data is kept

    def test_now_playing_import(self):
        self.run_cmd("--now-playing", "1")
        film = Film.objects.get(tmdb_id=603)
        self.assertEqual(film.title_zh, "黑客帝国")
        self.assertEqual(film.director, "Lana Wachowski, Lilly Wachowski")
        self.assertEqual(film.genres, "Action,Sci-Fi")
        self.assertEqual(list(film.actors.values_list("name", flat=True)),
                         ["Keanu Reeves", "Laurence Fishburne", "Carrie-Anne Moss"])
        self.assertTrue(film.now_showing)

    def test_bearer_token_is_sent_as_header(self):
        from myapi.management.commands.import_tmdb import TMDB
        t = TMDB("eyJhbGciOi.fake.token")
        self.assertEqual(t.session.headers["Authorization"], "Bearer eyJhbGciOi.fake.token")
        self.assertEqual(t.params, {})


class SeedAndAdminTests(TestCase):
    def test_seed_demo_twice_and_admin_pages_load(self):
        call_command("seed_demo", "--days", "2", stdout=StringIO())
        call_command("seed_demo", "--days", "2", stdout=StringIO())
        self.assertEqual(Film.objects.count(), 40)
        self.assertGreater(TimeSlot.objects.count(), 20)
        admin = User.objects.create_superuser("boss", "boss@example.com", "admin-pass-123")
        self.client.force_login(admin)
        for url in ("/admin/", "/admin/myapi/film/", "/admin/myapi/timeslot/", "/admin/myapi/order/",
                    f"/admin/myapi/film/{Film.objects.first().ID}/change/", "/api/docs/", "/api/schema/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
