from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from myapi.views import auth, catalog, misc, orders

urlpatterns = [
    path("config/", misc.config, name="config"),
    path("health/", misc.health, name="health"),

    path("films/", catalog.film_list, name="film-list"),
    path("films/<int:film_id>/", catalog.film_detail, name="film-detail"),
    path("films/<int:film_id>/showtimes/", catalog.film_showtimes, name="film-showtimes"),
    path("films/<int:film_id>/reviews/", catalog.film_reviews, name="film-reviews"),
    path("showtimes/<int:showtime_id>/", catalog.showtime_detail, name="showtime-detail"),

    path("auth/register/", auth.RegisterView.as_view(), name="register"),
    path("auth/verify-email/", auth.VerifyEmailView.as_view(), name="verify-email"),
    path("auth/resend-verification/", auth.ResendVerificationView.as_view(), name="resend-verification"),
    path("auth/token/", auth.LoginView.as_view(), name="token"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", auth.LogoutView.as_view(), name="logout"),
    path("auth/me/", auth.MeView.as_view(), name="me"),
    path("auth/password-reset/", auth.PasswordResetView.as_view(), name="password-reset"),
    path("auth/password-reset/confirm/", auth.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),

    path("orders/", orders.orders, name="orders"),
    path("orders/<str:code>/", orders.order_detail, name="order-detail"),
    path("orders/<str:code>/checkout/", orders.order_checkout, name="order-checkout"),
    path("orders/<str:code>/cancel/", orders.order_cancel, name="order-cancel"),
    path("orders/<str:code>/refund/", orders.order_refund, name="order-refund"),

    path("payments/stripe/confirm/", orders.stripe_confirm, name="stripe-confirm"),
    path("payments/stripe/webhook/", orders.stripe_webhook, name="stripe-webhook"),
    path("payments/demo/<str:code>/", orders.demo_payment, name="demo-payment"),
]
