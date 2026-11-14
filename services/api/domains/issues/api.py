from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import (
    authorized_rows,
    get_authorized_object_or_404,
    portal_organization,
)

from . import services
from .models import Issue, IssueStatus, Priority, RequestType
from .serializers import IssueSerializer, IssueWriteSerializer


def visible_rows(user):
    rows = Issue.objects.select_related("product", "module", "organization").prefetch_related(
        "events"
    )
    organization = portal_organization(user)
    if organization is None:
        return rows.none()
    scoped = authorized_rows(user, rows, allow_datasoft=True)
    if organization.kind == OrganizationKind.DATASOFT:
        return scoped.exclude(status=IssueStatus.DRAFT)
    return scoped.filter(Q(status=IssueStatus.SUBMITTED) | Q(created_by=user))


def writable_rows(user):
    """Resolve bank IDs before role checks; staff never resolve draft IDs."""
    return authorized_rows(user, Issue.objects.all())


def translate(exc: Exception) -> Exception:
    if isinstance(exc, DjangoPermissionDenied):
        return PermissionDenied(str(exc))
    if isinstance(exc, DjangoValidationError):
        return ValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
    return exc


class IssueListView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("status", str),
            OpenApiParameter("request_type", str),
            OpenApiParameter("priority", str),
            OpenApiParameter("search", str),
        ],
        responses=IssueSerializer(many=True),
        tags=["issues"],
    )
    def get(self, request: Request) -> Response:
        rows = visible_rows(request.user)
        for key, choices in (
            ("status", IssueStatus),
            ("request_type", RequestType),
            ("priority", Priority),
        ):
            value = request.query_params.get(key)
            if value:
                if value not in choices.values:
                    raise ValidationError({key: "Invalid filter."})
                rows = rows.filter(**{key: value})
        search = request.query_params.get("search", "").strip()
        if search:
            rows = rows.filter(Q(title__icontains=search) | Q(reference__icontains=search))
        return Response(IssueSerializer(rows[:200], many=True).data)

    @extend_schema(request=IssueWriteSerializer, responses={201: IssueSerializer}, tags=["issues"])
    def post(self, request: Request) -> Response:
        data = IssueWriteSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        try:
            issue = services.create_draft(request.user, data.validated_data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            raise translate(exc) from exc
        return Response(IssueSerializer(issue).data, status=status.HTTP_201_CREATED)


class IssueDetailView(APIView):
    @extend_schema(responses=IssueSerializer, tags=["issues"])
    def get(self, request: Request, id: int) -> Response:
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), id, allow_datasoft=True
        )
        return Response(IssueSerializer(issue).data)

    @extend_schema(request=IssueWriteSerializer, responses=IssueSerializer, tags=["issues"])
    def patch(self, request: Request, id: int) -> Response:
        issue = get_authorized_object_or_404(request.user, writable_rows(request.user), id)
        data = IssueWriteSerializer(data=request.data, context={"request": request, "issue": issue})
        data.is_valid(raise_exception=True)
        try:
            updated = services.edit_draft(request.user, issue, data.validated_data)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            raise translate(exc) from exc
        return Response(IssueSerializer(updated).data)

    @extend_schema(responses={204: None}, tags=["issues"])
    def delete(self, request: Request, id: int) -> Response:
        issue = get_authorized_object_or_404(request.user, writable_rows(request.user), id)
        try:
            services.delete_draft(request.user, issue)
        except DjangoPermissionDenied as exc:
            raise translate(exc) from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


class IssueSubmitView(APIView):
    @extend_schema(request=None, responses=IssueSerializer, tags=["issues"])
    def post(self, request: Request, id: int) -> Response:
        issue = get_authorized_object_or_404(request.user, writable_rows(request.user), id)
        try:
            submitted = services.submit(request.user, issue)
        except (DjangoPermissionDenied, DjangoValidationError) as exc:
            raise translate(exc) from exc
        return Response(IssueSerializer(submitted).data)
