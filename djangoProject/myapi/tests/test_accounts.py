import re

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from myapi.tests.helpers import make_user


def _link_params(body):
    uid = re.search(r"uid=([\w-]+)", body).group(1)
    token = re.search(r"token=([\w-]+)", body).group(1)
    return uid, token


@override_settings(REQUIRE_EMAIL_VERIFICATION=True)
class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()  # rate limits are stored in the cache
        self.client = APIClient()

    def register(self, **overrides):
        data = {"username": "newbie", "email": "New@Example.com", "password": "sturdy-pass-42", **overrides}
        return self.client.post("/api/auth/register/", data, format="json", HTTP_ORIGIN="http://localhost:5173")

    def test_register_sends_verification_email_and_account_starts_inactive(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["email_verification_required"])
        self.assertTrue(response.data["email_sent"])
        user = User.objects.get(username="newbie")
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://localhost:5173/verify-email?uid=", mail.outbox[0].body)
        self.assertNotIn("&amp;", mail.outbox[0].body)  # plain-text links must not be HTML-escaped
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")

    def test_login_before_verifying_explains_what_to_do(self):
        self.register()
        response = self.client.post("/api/auth/token/", {"username": "newbie", "password": "sturdy-pass-42"},
                                    format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "email_not_verified")

    def test_verification_link_activates_once_and_signs_in(self):
        self.register()
        uid, token = _link_params(mail.outbox[0].body)
        first = self.client.post("/api/auth/verify-email/", {"uid": uid, "token": token}, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertIn("access", first.data)
        self.assertTrue(User.objects.get(username="newbie").is_active)
        again = self.client.post("/api/auth/verify-email/", {"uid": uid, "token": token}, format="json")
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.data["code"], "already_verified")

    def test_duplicate_username_and_email_are_rejected_with_a_reason(self):
        make_user(username="Newbie", email="other@example.com")
        response = self.register()
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data["fields"])
        make_user(username="someone", email="new@example.com")
        response = self.register(username="fresh")
        self.assertIn("email", response.data["fields"])

    def test_weak_password_is_rejected(self):
        response = self.register(password="password")
        self.assertEqual(response.status_code, 400)

    def test_resend_does_not_reveal_whether_an_account_exists(self):
        self.register()
        known = self.client.post("/api/auth/resend-verification/", {"email": "new@example.com"}, format="json")
        unknown = self.client.post("/api/auth/resend-verification/", {"email": "nobody@example.com"}, format="json")
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 2)


@override_settings(REQUIRE_EMAIL_VERIFICATION=False)
class NoVerificationTests(TestCase):
    def test_register_signs_in_straight_away(self):
        response = APIClient().post("/api/auth/register/", {
            "username": "quick", "email": "quick@example.com", "password": "sturdy-pass-42"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIn("access", response.data)


class LoginAndPasswordTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user()
        self.client = APIClient()

    def test_login_with_email_or_username_any_case(self):
        for login in ("alice@example.com", "ALICE"):
            response = self.client.post("/api/auth/token/", {"username": login, "password": "correct-horse-9"},
                                        format="json")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["user"]["username"], "alice")

    def test_wrong_password(self):
        response = self.client.post("/api/auth/token/", {"username": "alice", "password": "nope"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "invalid_login")

    def test_password_reset_flow(self):
        self.client.post("/api/auth/password-reset/", {"email": "alice@example.com"}, format="json")
        self.assertEqual(len(mail.outbox), 1)
        uid, token = _link_params(mail.outbox[0].body)
        response = self.client.post("/api/auth/password-reset/confirm/",
                                    {"uid": uid, "token": token, "new_password": "brand-new-pass-77"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        reused = self.client.post("/api/auth/password-reset/confirm/",
                                  {"uid": uid, "token": token, "new_password": "another-pass-88"}, format="json")
        self.assertEqual(reused.status_code, 400)
        ok = self.client.post("/api/auth/token/", {"username": "alice", "password": "brand-new-pass-77"},
                              format="json")
        self.assertEqual(ok.status_code, 200)

    def test_refresh_and_logout_blacklists_the_refresh_token(self):
        tokens = self.client.post("/api/auth/token/", {"username": "alice", "password": "correct-horse-9"},
                                  format="json").data
        refreshed = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refreshed.status_code, 200)
        new_refresh = refreshed.data["refresh"]
        self.client.post("/api/auth/logout/", {"refresh": new_refresh}, format="json")
        after = self.client.post("/api/auth/token/refresh/", {"refresh": new_refresh}, format="json")
        self.assertEqual(after.status_code, 401)
