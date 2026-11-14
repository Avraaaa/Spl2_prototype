from typing import Any

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import QuerySet
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from domains.tenants.models import Organization

from . import services
from .permissions import HasPortalAccount, IsDataSoftAdmin, PasswordChangeCompleted
from .serializers import (
    ChangePasswordSerializer,
    ChangeUsernameSerializer,
    ErrorSerializer,
    LoginSerializer,
    OrganizationSerializer,
    PortalUserSerializer,
    ProfileUpdateSerializer,
    RolesSerializer,
    TemporaryCredentialSerializer,
    UserCreateSerializer,
)

INVALID = {"detail": "Invalid username or password.", "code": "invalid_credentials"}
# Explicit lists replace DRF defaults, so the first-login gate must be repeated here.
ADMIN_PERMISSIONS = [IsAuthenticated, HasPortalAccount, PasswordChangeCompleted, IsDataSoftAdmin]
PROFILE_PERMISSIONS = [IsAuthenticated, HasPortalAccount, PasswordChangeCompleted]


def _translate(exc: Exception) -> Exception:
    if isinstance(exc, DjangoPermissionDenied):
        return PermissionDenied(str(exc))
    if isinstance(exc, DjangoValidationError):
        return ValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
    return exc


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={204: None}, tags=["auth"])
    def get(self, request: Request) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={200: PortalUserSerializer, 401: ErrorSerializer},
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=data.validated_data["username"],
            password=data.validated_data["password"],
        )
        if user is None or not hasattr(user, "account"):
            return Response(INVALID, status=status.HTTP_401_UNAUTHORIZED)
        if services.temporary_credential_expired(user):
            return Response(
                {
                    "detail": "Temporary password expired. Ask an administrator for a reset.",
                    "code": "temporary_credential_expired",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request._request, user)
        return Response(PortalUserSerializer(user).data)


class LogoutView(APIView):
    """Idempotent: anonymous callers get 204. SessionAuthentication still enforces CSRF for
    authenticated sessions, so a 403 here always means the session is still active."""

    permission_classes = [AllowAny]

    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [HasPortalAccount]

    @extend_schema(responses=PortalUserSerializer, tags=["auth"])
    def get(self, request: Request) -> Response:
        # Organization is always derived from the session user; headers/query are ignored.
        return Response(PortalUserSerializer(request.user).data)

    @extend_schema(request=ProfileUpdateSerializer, responses=PortalUserSerializer, tags=["auth"])
    def patch(self, request: Request) -> Response:
        data = ProfileUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        allowed = {"full_name", "email"}
        unknown = set(request.data) - allowed
        if unknown:
            raise ValidationError({key: "This field cannot be changed here." for key in unknown})
        try:
            user = services.update_profile(request.user, **data.validated_data)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            raise _translate(exc) from exc
        return Response(PortalUserSerializer(user).data)

    def get_permissions(self) -> list[Any]:
        if self.request.method == "PATCH":
            return [permission() for permission in PROFILE_PERMISSIONS]
        return super().get_permissions()


class ChangeUsernameView(APIView):
    permission_classes = PROFILE_PERMISSIONS
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_check"

    @extend_schema(request=ChangeUsernameSerializer, responses=PortalUserSerializer, tags=["auth"])
    def post(self, request: Request) -> Response:
        data = ChangeUsernameSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        unknown = set(request.data) - {"username", "current_password"}
        if unknown:
            raise ValidationError({key: "This field cannot be changed here." for key in unknown})
        try:
            user = services.change_username(request.user, **data.validated_data)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            raise _translate(exc) from exc
        except IntegrityError as exc:
            # A concurrent rename can pass the precheck; the unique index remains authoritative.
            raise ValidationError({"username": "Username already exists."}) from exc
        return Response(PortalUserSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [HasPortalAccount]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_check"

    @extend_schema(request=ChangePasswordSerializer, responses=PortalUserSerializer, tags=["auth"])
    def post(self, request: Request) -> Response:
        data = ChangePasswordSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.change_password(request.user, **data.validated_data)
        except DjangoValidationError as exc:
            raise _translate(exc) from exc
        update_session_auth_hash(request._request, request.user)
        return Response(PortalUserSerializer(request.user).data)


class OrganizationAdminViewSet(mixins.ListModelMixin, viewsets.GenericViewSet[Organization]):
    permission_classes = ADMIN_PERMISSIONS
    serializer_class = OrganizationSerializer
    queryset = Organization.objects.all()

    @extend_schema(
        request=OrganizationSerializer, responses={201: OrganizationSerializer}, tags=["admin"]
    )
    def create(self, request: Request) -> Response:
        data = OrganizationSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        org = services.register_organization(request.user, **data.validated_data)
        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["admin"])
class UserAdminViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet[User]
):
    permission_classes = ADMIN_PERMISSIONS
    serializer_class = PortalUserSerializer

    def get_queryset(self) -> QuerySet[User]:
        qs = (
            User.objects.filter(account__isnull=False)
            .select_related("account__organization")
            .prefetch_related("memberships")
            .order_by("account__organization__name", "username")
        )
        org = self.request.query_params.get("organization")
        return qs.filter(account__organization_id=org) if org and org.isdigit() else qs

    @extend_schema(parameters=[OpenApiParameter("organization", int, required=False)])
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(request=UserCreateSerializer, responses={201: TemporaryCredentialSerializer})
    def create(self, request: Request) -> Response:
        data = UserCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            user, temporary = services.create_user(request.user, **data.validated_data)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            raise _translate(exc) from exc
        body = {"user": PortalUserSerializer(user).data, "temporary_password": temporary}
        return Response(body, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=PortalUserSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request: Request, pk: str | None = None) -> Response:
        try:
            user = services.deactivate_user(request.user, self.get_object())
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            raise _translate(exc) from exc
        return Response(PortalUserSerializer(user).data)

    @extend_schema(request=None, responses=TemporaryCredentialSerializer)
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request: Request, pk: str | None = None) -> Response:
        user = self.get_object()
        try:
            temporary = services.force_password_reset(request.user, user)
        except DjangoPermissionDenied as exc:
            raise _translate(exc) from exc
        return Response({"user": PortalUserSerializer(user).data, "temporary_password": temporary})

    @extend_schema(request=RolesSerializer, responses=PortalUserSerializer)
    @action(detail=True, methods=["put"])
    def roles(self, request: Request, pk: str | None = None) -> Response:
        data = RolesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            user = services.assign_roles(
                request.user, self.get_object(), data.validated_data["roles"]
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            raise _translate(exc) from exc
        user.refresh_from_db()
        return Response(PortalUserSerializer(user).data)
