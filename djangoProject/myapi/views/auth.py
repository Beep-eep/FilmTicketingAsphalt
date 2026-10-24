from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView

from myapi.serializers import (EmailSerializer, PasswordResetConfirmSerializer, RegisterSerializer,
                               TokenPairInputSerializer, UserSerializer)
from myapi.services import emails
from myapi.services.site import site_url


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data}


def _user_from_uid(uid):
    try:
        return User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


class LoginSerializer(TokenObtainPairSerializer):
    """Sign in with a username *or* an email address."""

    def validate(self, attrs):
        login = (attrs.get(self.username_field) or "").strip()
        lookup = {"email__iexact": login} if "@" in login else {"username__iexact": login}
        match = User.objects.filter(**lookup).order_by("id").first()
        if match:
            attrs[self.username_field] = match.username
        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            if match and not match.is_active and match.check_password(attrs.get("password", "")):
                raise AuthenticationFailed(
                    "Confirm your email address first. We sent you a link when you signed up.",
                    code="email_not_verified")
            raise AuthenticationFailed("That username or email and password don't match.", code="invalid_login")
        data["user"] = UserSerializer(self.user).data
        return data


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_email"

    @extend_schema(request=RegisterSerializer, responses=dict)
    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        need_verify = settings.REQUIRE_EMAIL_VERIFICATION
        user = User.objects.create_user(username=d["username"], email=d["email"], password=d["password"],
                                        is_active=not need_verify)
        if need_verify:
            sent = emails.send_verification_email(user, site_url(request))
            return Response({"email_verification_required": True, "email_sent": sent, "email": user.email},
                            status=status.HTTP_201_CREATED)
        return Response({"email_verification_required": False, **_tokens_for(user)}, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=TokenPairInputSerializer, responses=dict)
    def post(self, request):
        s = TokenPairInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = _user_from_uid(s.validated_data["uid"])
        if user is None:
            raise ValidationError({"detail": "This confirmation link isn't valid."})
        if not emails.email_verification_token.check_token(user, s.validated_data["token"]):
            if user.is_active:
                return Response({"detail": "Your email is already confirmed. Sign in to continue.",
                                 "code": "already_verified"}, status=status.HTTP_409_CONFLICT)
            raise ValidationError({"detail": "This confirmation link has expired. Ask for a new one below."})
        user.is_active = True
        user.save(update_fields=["is_active"])
        return Response(_tokens_for(user))


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_email"

    @extend_schema(request=EmailSerializer, responses=dict)
    def post(self, request):
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=s.validated_data["email"], is_active=False).first()
        if user:
            emails.send_verification_email(user, site_url(request))
        # Same answer either way, so this can't be used to find out who has an account.
        return Response({"detail": "If that address is waiting for confirmation, a new link is on its way."})


class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_email"

    @extend_schema(request=EmailSerializer, responses=dict)
    def post(self, request):
        s = EmailSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=s.validated_data["email"], is_active=True).first()
        if user and user.has_usable_password():
            emails.send_password_reset_email(user, site_url(request))
        return Response({"detail": "If an account uses that address, we've emailed a reset link."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, responses=dict)
    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = _user_from_uid(s.validated_data["uid"])
        if user is None or not default_token_generator.check_token(user, s.validated_data["token"]):
            raise ValidationError({"detail": "This reset link has expired or was already used. Ask for a new one."})
        try:
            validate_password(s.validated_data["new_password"], user=user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)})
        user.set_password(s.validated_data["new_password"])
        user.save(update_fields=["password"])
        # Sign out every other device.
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)
        return Response({"detail": "Password changed. Sign in with your new password."})


class RefreshInputSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RefreshInputSerializer, responses=None)
    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)
