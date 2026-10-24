"""
Django settings for the Asphalt Cinema ticketing project.

Every value that differs between your laptop and a public server is read from
environment variables (or from a `.env` file next to manage.py). With no `.env`
at all, the project runs exactly like before: DEBUG on, local MySQL database
`FilmTicketing` with user `test` / `123456`, emails printed in the terminal and
the demo payment provider.

See `.env.example` for every option.
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    value = os.environ.get(name)
    return default if value is None or value.strip() == "" else value.strip()


def env_bool(name, default=False):
    value = env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


ON_RENDER = "RENDER" in os.environ

# --- Core -------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", default=not ON_RENDER)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is off.")
    SECRET_KEY = "django-insecure-local-dev-only-0d9f3b6e2a7c4e1f8b5a"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", *env_list("DJANGO_ALLOWED_HOSTS")]
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
if DEBUG:
    # Temporary public links made with Cloudflare Quick Tunnels or ngrok.
    ALLOWED_HOSTS += [".trycloudflare.com", ".ngrok-free.app", ".ngrok-free.dev", ".ngrok.app"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "django_extensions",
    "myapi",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "djangoProject.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "djangoProject.wsgi.application"

# --- Database -----------------------------------------------------------------
# DATABASE_URL wins if it is set (e.g. postgres://... on Render/Neon, or
# sqlite:///db.sqlite3 for a zero-setup try-out). Otherwise the local MySQL
# database from the setup guide is used.

if env("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.parse(
            env("DATABASE_URL"),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", "FilmTicketing"),
            "USER": env("DB_USER", "test"),
            "PASSWORD": env("DB_PASSWORD", "123456"),
            "HOST": env("DB_HOST", "127.0.0.1"),
            "PORT": env("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Time and language ---------------------------------------------------------
# Datetimes are stored in UTC; showtimes are shown in the cinema's time zone.
# Note for MySQL: avoid `__date` lookups, which need MySQL's time-zone tables.

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("CINEMA_TIME_ZONE", "America/Los_Angeles")
USE_I18N = True
USE_TZ = True

# --- Static files and the built frontend ----------------------------------------
# `npm run build` writes the Vue app into djangoProject/spa/. Django then serves
# the whole site (pages + API) from one address, which is what makes a single
# public deployment possible.

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(exist_ok=True)  # WhiteNoise warns if it is missing
SPA_DIR = BASE_DIR / "spa"
STATICFILES_DIRS = [SPA_DIR] if SPA_DIR.exists() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
# Vite already puts a content hash in asset file names, so they can be cached forever.
WHITENOISE_IMMUTABLE_FILE_TEST = r"^.+[.-][0-9a-zA-Z_-]{8,}\.(?:js|css|woff2?|png|jpe?g|svg|webp)$"

# --- Security for public deployments ---------------------------------------------

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")
if DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://*.trycloudflare.com",
        "https://*.ngrok-free.app",
        "https://*.ngrok-free.dev",
    ]

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "0"))
    SECURE_CONTENT_TYPE_NOSNIFF = True

# The Vue dev server proxies /api to Django, so the browser never needs CORS in
# development. CORS is only for a frontend hosted on a different domain.
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")

# --- REST API -------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Limits per IP address for actions that send email or check passwords.
    "DEFAULT_THROTTLE_RATES": {
        "auth_email": env("AUTH_EMAIL_RATE", "60/hour" if DEBUG else "10/hour"),
        "login": env("LOGIN_RATE", "20/min"),
    },
    "EXCEPTION_HANDLER": "myapi.api_errors.exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Asphalt Cinema API",
    "DESCRIPTION": "Films, showtimes, seat booking, payments and accounts.",
    "VERSION": "2.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Cinema business rules ---------------------------------------------------------

CINEMA_NAME = env("CINEMA_NAME", "Asphalt Cinema")
CURRENCY = env("CURRENCY", "usd").lower()
MAX_SEATS_PER_ORDER = int(env("MAX_SEATS_PER_ORDER", "8"))
SEAT_HOLD_MINUTES = int(env("SEAT_HOLD_MINUTES", "10"))  # before checkout starts
REFUND_CUTOFF_MINUTES = int(env("REFUND_CUTOFF_MINUTES", "60"))  # before showtime
BOOKING_CUTOFF_MINUTES = int(env("BOOKING_CUTOFF_MINUTES", "0"))  # after start
# Keep the showtime schedule filled this many days ahead (0 turns it off).
AUTO_SCHEDULE_DAYS = int(env("AUTO_SCHEDULE_DAYS", "7"))

# Where links in emails and Stripe redirects point. When it isn't set, the
# address the visitor is actually using (localhost, a tunnel, Render) is used.
FRONTEND_URL = env("FRONTEND_URL", "").rstrip("/")

# --- Accounts and email -----------------------------------------------------------------

REQUIRE_EMAIL_VERIFICATION = env_bool("REQUIRE_EMAIL_VERIFICATION", True)
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24  # links in emails work for 24 hours

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", f"{CINEMA_NAME} <tickets@localhost>")
RESEND_API_KEY = env("RESEND_API_KEY")
if RESEND_API_KEY:
    # HTTPS API: works on hosts that block SMTP ports (e.g. Render's free tier).
    EMAIL_BACKEND = "myapi.email_backends.ResendEmailBackend"
elif env("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = int(env("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", EMAIL_PORT == 587)
    EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", EMAIL_PORT == 465)
    EMAIL_TIMEOUT = 15
else:
    # No email service configured: emails are printed in the runserver terminal.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- Payments ------------------------------------------------------------------------------
# With a Stripe secret key, checkout goes through Stripe's hosted payment page
# (test keys: test cards only; live keys: real money). Without one, a clearly
# labelled demo checkout is used so the site still works end to end.

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")
PAYMENT_PROVIDER = "stripe" if STRIPE_SECRET_KEY else "demo"
if PAYMENT_PROVIDER == "demo" and not DEBUG and not env_bool("ALLOW_DEMO_PAYMENTS", True):
    raise ImproperlyConfigured("Set STRIPE_SECRET_KEY or ALLOW_DEMO_PAYMENTS=true.")

# --- Movie data -------------------------------------------------------------------------------

TMDB_API_KEY = env("TMDB_API_KEY", "")  # v3 API key or v4 "API Read Access Token"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "myapi": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    },
}
