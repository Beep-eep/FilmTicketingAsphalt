# Asphalt Cinema — film ticketing

A cinema ticketing website: browse 40 films, pick a date and showtime, choose seats on a live seat map, pay, and get tickets with a QR code by email. Vue 3 + Vite frontend, Django 5.2 + Django REST Framework backend, MySQL locally and PostgreSQL when deployed.

一个影院售票网站：浏览影片 → 选日期和场次 → 在实时座位图上选座 → 支付 → 收到带二维码的电子票和确认邮件。前端 Vue 3 + Vite，后端 Django 5.2 + DRF；本地使用 MySQL，部署后使用 PostgreSQL。

Background: this began as a second-year (大二) course project with login, registration, seat selection, booking and refunds. This version keeps that idea and database, and rebuilds the interface, payments, email and deployment.

## What it does

| Area | Features |
|---|---|
| Browsing | Marquee-style hero, 40-film catalog (with Chinese titles), date strip, genre filters, sorting, search by title, Chinese title, director or cast, English/中文 toggle |
| Film page | Synopsis, cast, runtime, showtimes grouped by room for each day, seats-left bars, trailer (when imported from TMDB), 1–10 ratings with reviews |
| Seats | Interactive map with rows, aisle, premium rows, hover prices, keyboard arrows, zoom, "best available" picker, live refresh every 20 s |
| Payments | Stripe Checkout (test or live keys) with webhook + landing-page fulfilment, partial refunds per seat; a labelled demo mode when no key is set |
| Accounts | Sign up with email confirmation, sign in with username or email, password reset by email, JWT tokens with refresh and logout |
| Tickets | Upcoming / past tabs, QR code per booking, pay-later countdown, cancel, refund |
| Staff | Django admin: films with cast, rooms, showtimes (seats are created automatically), bookings searchable by code/email, bulk refunds |
| API | Clean JSON API under `/api/`, interactive docs at `/api/docs/` |

## Run it on your computer

You already have Python 3.14, Node 24 and MySQL 8.4 with the `FilmTicketing` database from the first setup. Your existing database is upgraded in place.

**Terminal 1 — backend** (from the `djangoProject` folder):
```bash
python3.14 -m venv .venv                 # only the first time in this folder
source .venv/bin/activate                # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate                 # upgrades your existing tables
python manage.py seed_demo --reset       # 40 films, 8 rooms, a week of showtimes (keeps user accounts)
python manage.py createsuperuser         # optional: login for /admin/
python manage.py runserver
```

**Terminal 2 — frontend** (from the `frontend` folder):
```bash
npm install
npm run dev
```

Open **http://localhost:5173**. With no further setup, payments run in **demo mode** and emails (sign-up confirmation, tickets, refunds) are **printed in Terminal 1**: copy the confirmation link from there.

Showtimes top themselves up automatically for the next 7 days, so the site never runs out of screenings.

### Optional settings (`djangoProject/.env`)

Copy `djangoProject/.env.example` to `djangoProject/.env` and fill in what you need. Restart `runserver` after editing it.

**Real payments with Stripe (test mode)**
1. Create a free Stripe account, open the dashboard in test mode/sandbox and copy the secret key (`sk_test_...`).
2. Put `STRIPE_SECRET_KEY=sk_test_...` in `.env`.
3. So Stripe can tell your computer about payments, install the Stripe CLI (`npm install -g @stripe/cli`), run `stripe login`, then keep this running in a third terminal:
   ```bash
   stripe listen --forward-to localhost:8000/api/payments/stripe/webhook/
   ```
   It prints `whsec_...`; put that in `.env` as `STRIPE_WEBHOOK_SECRET`.
4. Pay with test card **4242 4242 4242 4242**, any future expiry date, any CVC. No real money moves with `sk_test_` keys. Live keys (`sk_live_`) charge real cards and only work after Stripe activates your account.

The site also confirms the payment when Stripe sends the customer back, so a missed webhook doesn't lose a booking.

**Real emails**
- *Gmail:* turn on 2-Step Verification, create an App Password at https://myaccount.google.com/apppasswords, then set `EMAIL_HOST=smtp.gmail.com`, `EMAIL_PORT=587`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (the 16-character app password) and `DEFAULT_FROM_EMAIL`.
- *Resend (HTTPS API):* set `RESEND_API_KEY` and `DEFAULT_FROM_EMAIL`. Use this on hosts that block SMTP (see below). Until you verify a domain in Resend, it only delivers to your own Resend account's address.

**Real posters, trailers and current films (TMDB)**
Get a free API key at https://www.themoviedb.org/settings/api, put it in `.env` as `TMDB_API_KEY`, then:
```bash
python manage.py import_tmdb --enrich                       # posters, backdrops, trailers for the 40 built-in films
python manage.py import_tmdb --now-playing 2 --reschedule   # add what's in US cinemas now, rebuild unbooked showtimes
```
TMDB is free for non-commercial use with attribution; the site footer shows the required notice automatically once TMDB data is used.

## Make it public

### Option A — a temporary public link from your Mac (2 minutes, for demos)

Because the site and its API share one address, you only need to expose port 5173.

```bash
brew install cloudflared          # once
npm run tunnel                    # in the frontend folder, while runserver and npm run dev are running
```
It prints an address like `https://something-random.trycloudflare.com`. Anyone can open it while your Mac is on and the three terminals are running. The address changes every time, and Cloudflare describes Quick Tunnels as being for testing, with no uptime guarantee. Stripe redirects and email links automatically use the tunnel address.

ngrok works too (`ngrok http 5173`), but its free plan shows visitors a warning page first.

### Option B — a permanent free deployment (Render + Neon)

The repository is ready for [Render](https://render.com)'s free tier: `render.yaml` describes the service and `build.sh` builds everything into **one web service** (Django serves the API, the admin and the built Vue site).

1. **Push this project to GitHub** (VS Code → Source Control → Publish/Push).
2. **Database:** create a free PostgreSQL project at https://neon.com and copy its connection string (`postgresql://...`). Neon's free plan doesn't expire. Render also has free Postgres, but it expires 30 days after creation.
3. **Render:** sign in, go to the **Blueprints** page, create a **New Blueprint Instance** from your repository, and fill in the values it asks for:
   - `DATABASE_URL` — the Neon connection string
   - `DJANGO_SUPERUSER_USERNAME`, `_EMAIL`, `_PASSWORD` — your admin login, created on the first deploy
   - Stripe, Resend and TMDB keys — optional; leave empty for demo payments and console emails
4. Click **Apply**. The first build takes a few minutes, then the site is live at `https://asphalt-cinema-xxxx.onrender.com`.
5. **Stripe webhook for the live site:** in the Stripe dashboard open **Workbench → Webhooks → Create an event destination**, choose **Your account** and **Snapshot** payloads, select `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.expired` and `checkout.session.async_payment_failed`, and use `https://YOUR-SITE.onrender.com/api/payments/stripe/webhook/` as the endpoint URL. Copy its `whsec_...` signing secret into Render as `STRIPE_WEBHOOK_SECRET`.

Things to know about Render's free tier:
- The service sleeps after 15 minutes without visitors; the next visit takes about a minute to wake it.
- Outbound SMTP ports (25, 465, 587) are blocked, so Gmail SMTP won't work there. Use `RESEND_API_KEY` instead.
- There's no shell on free services, which is why `build.sh` runs migrations, loads the demo catalog on an empty database and creates the admin user.

## Admin and API

- **Admin:** `/admin/` (create a login with `python manage.py createsuperuser`). Adding a showtime creates its seats automatically. Bookings can be searched by code, username or email and refunded in bulk.
- **API docs:** `/api/docs/` (Swagger UI) and `/api/schema/` (OpenAPI).

## Tests

```bash
cd djangoProject
DATABASE_URL=sqlite:///test.sqlite3 python manage.py test myapi
# Windows PowerShell: $env:DATABASE_URL="sqlite:///test.sqlite3"; python manage.py test myapi
```
40 tests cover sign-up and email confirmation, login, password reset, seat holds and double-booking, refunds, Stripe checkout/fulfilment/webhooks (Stripe's network calls mocked, signatures verified with the real library), TMDB import (recorded responses), the demo seed and admin pages. SQLite is used because the MySQL `test` user can't create the test database.

## Project layout

```
djangoProject/
  djangoProject/settings.py   all settings, read from environment variables / .env
  myapi/models.py             films, rooms, showtimes, seats, orders, tickets, reviews
  myapi/services/             booking rules, payments (Stripe + demo), emails, scheduling
  myapi/views/                API endpoints (catalog, auth, orders/payments, config)
  myapi/admin.py              staff back office
  myapi/management/commands/  seed_demo, import_tmdb, schedule_showtimes, release_expired_holds
  myapi/templates/emails/     HTML + text emails
frontend/
  src/views/                  pages (home, film, seats, checkout, tickets, sign-in...)
  src/components/             seat map, marquee board, ticket stub, poster art...
  src/i18n/                   English and Chinese text
render.yaml, build.sh         deployment
```

## Upgrade notes

Your database keeps working: migrations 0006–0007 add the new columns and turn existing paid tickets into bookings. Unpaid reservations from the old "book now, pay later" button are cancelled, because seats are now held only while paying.

Security fixes compared with the first version: the API no longer trusts a `user_id` sent by the browser, so people can't book, view, cancel or "pay" for other people's tickets, and paying now requires an actual payment.
