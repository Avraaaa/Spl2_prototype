import re

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import F, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.models import Membership
from domains.accounts.roles import DATASOFT_ROLES
from domains.accounts.services import is_datasoft_admin
from domains.audit.services import append_record
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import (
    authorized_rows,
    get_authorized_object_or_404,
    portal_organization,
)

from . import services, workflow
from .models import (
    Issue,
    IssueEvent,
    IssueOriginalText,
    IssueStatus,
    MaskingPattern,
    Priority,
    RequestType,
    WorkflowSettings,
)
from .serializers import (
    AcceptSerializer,
    AssignSerializer,
    DateRevisionSerializer,
    DeliverySerializer,
    IssueDraftEditSerializer,
    IssueEventSerializer,
    IssueSerializer,
    IssueWriteSerializer,
    MaskPreviewResponseSerializer,
    MaskPreviewSerializer,
    ReasonSerializer,
    TransitionVersionSerializer,
    WorkflowAssigneeSerializer,
    WorkflowSettingsSerializer,
)


class MaskPreviewView(APIView):
    @extend_schema(
        request=MaskPreviewSerializer,
        responses=MaskPreviewResponseSerializer,
        tags=["privacy"],
    )
    def post(self, request: Request) -> Response:
        data = MaskPreviewSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        masked_fields: dict[str, str] = {}
        detected: set[str] = set()
        for key, value in data.validated_data["fields"].items():
            if key not in services.MASKABLE_FIELDS:
                raise ValidationError({"fields": {key: "This field cannot be previewed."}})
            masked, kinds = services.mask_sensitive_with_detections(value)
            masked_fields[key] = masked
            detected.update(kinds)
        return Response(
            {
                "masked_fields": masked_fields,
                "detected_types": sorted(detected),
            }
        )


class MaskingPatternSerializer(serializers.ModelSerializer):
    MAX_ACTIVE_PATTERNS = 20
    MAX_PATTERN_LENGTH = 200

    class Meta:
        model = MaskingPattern
        fields = ("id", "name", "pattern", "replacement", "is_active", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_pattern(self, value):
        if len(value) > self.MAX_PATTERN_LENGTH:
            raise serializers.ValidationError("Pattern must be 200 characters or fewer.")
        if re.search(r"\([^)]*(?:[+*]|\{\d+(?:,\d*)?\})[^)]*\)[+*{]", value):
            raise serializers.ValidationError("Nested quantifiers are not allowed.")
        try:
            re.compile(value)
        except re.error as exc:
            raise serializers.ValidationError(
                "Pattern must be a valid regular expression."
            ) from exc
        return value

    def validate(self, attrs):
        is_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        becoming_active = is_active and (self.instance is None or not self.instance.is_active)
        if (
            becoming_active
            and MaskingPattern.objects.filter(is_active=True).count() >= self.MAX_ACTIVE_PATTERNS
        ):
            raise serializers.ValidationError(
                {"is_active": "At most 20 custom patterns may be active."}
            )
        return attrs


class MaskingPatternsView(APIView):
    @extend_schema(responses=MaskingPatternSerializer(many=True), tags=["privacy"])
    def get(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft Administrator role required.")
        return Response(MaskingPatternSerializer(MaskingPattern.objects.all(), many=True).data)

    @extend_schema(
        request=MaskingPatternSerializer,
        responses={201: MaskingPatternSerializer},
        tags=["privacy"],
    )
    def post(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft Administrator role required.")
        data = MaskingPatternSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        pattern = data.save()
        return Response(MaskingPatternSerializer(pattern).data, status=status.HTTP_201_CREATED)


class MaskingPatternDetailView(APIView):
    @extend_schema(
        request=MaskingPatternSerializer, responses=MaskingPatternSerializer, tags=["privacy"]
    )
    def patch(self, request, id):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft Administrator role required.")
        pattern = MaskingPattern.objects.filter(pk=id).first()
        if pattern is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = MaskingPatternSerializer(pattern, data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        pattern = data.save()
        return Response(MaskingPatternSerializer(pattern).data)


class IssueOriginalResponse(serializers.Serializer):
    title = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)


class IssueOriginalView(APIView):
    @extend_schema(responses=IssueOriginalResponse, tags=["privacy"])
    def get(self, request: Request, id: int) -> Response:
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), id, allow_datasoft=True
        )
        if not (
            is_datasoft_admin(request.user)
            or request.user.has_perm("issues.view_unmasked_original")
        ):
            raise PermissionDenied("Original text permission required.")
        append_record(
            organization=issue.organization,
            actor=request.user,
            action="ISSUE_ORIGINAL_VIEWED",
            payload={
                "issue_id": issue.pk,
                "reference": issue.reference,
                "request_method": request.method,
                "request_path": request.path,
            },
        )
        original = IssueOriginalText.objects.filter(issue=issue).first()
        return Response(
            {
                "title": original.title if original else issue.title,
                "description": original.description if original else issue.description,
            }
        )


def visible_rows(user):
    rows = Issue.objects.select_related(
        "product",
        "module",
        "organization",
        "assignee__account",
        "created_by__account",
        "related_request",
        "recurring_of",
    ).prefetch_related("events__actor__account")
    organization = portal_organization(user)
    if organization is None:
        return rows.none()
    scoped = authorized_rows(user, rows, allow_datasoft=True)
    if organization.kind == OrganizationKind.DATASOFT:
        return scoped.exclude(status=IssueStatus.DRAFT)
    return scoped.filter(~Q(status=IssueStatus.DRAFT) | Q(created_by=user))


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
            OpenApiParameter("organization", int),
            OpenApiParameter("assignee", str),
            OpenApiParameter("overdue", bool),
            OpenApiParameter("ordering", str),
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
        # Narrowing filters apply after tenant scoping, so they can never widen access.
        bank = request.query_params.get("organization")
        if bank:
            if not bank.isdigit():
                raise ValidationError({"organization": "Invalid filter."})
            rows = rows.filter(organization_id=int(bank))
        assignee = request.query_params.get("assignee")
        if assignee:
            if assignee != "me":
                raise ValidationError({"assignee": "Invalid filter."})
            rows = rows.filter(assignee=request.user)
        if request.query_params.get("overdue", "").lower() in ("1", "true"):
            rows = rows.filter(
                tentative_delivery_date__lt=timezone.localdate(),
                actual_delivery_at__isnull=True,
            )
        ordering = request.query_params.get("ordering")
        if ordering:
            if ordering != "oldest":
                raise ValidationError({"ordering": "Invalid ordering."})
            rows = rows.order_by(F("submitted_at").asc(nulls_last=True), "id")
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
        return Response(IssueSerializer(issue, context={"request": request}).data)

    @extend_schema(request=IssueDraftEditSerializer, responses=IssueSerializer, tags=["issues"])
    def patch(self, request: Request, id: int) -> Response:
        issue = get_authorized_object_or_404(request.user, writable_rows(request.user), id)
        data = IssueDraftEditSerializer(
            data=request.data, context={"request": request, "issue": issue}
        )
        data.is_valid(raise_exception=True)
        try:
            updated = services.edit_draft(request.user, issue, data.validated_data)
        except workflow.VersionConflict as exc:
            raise Conflict(str(exc)) from exc
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


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This request was changed by someone else — reload."
    default_code = "version_conflict"


def transition(request: Request, id: int, serializer_type, service) -> Response:
    # Resolve tenant scope before input validation so another bank's ID always stays a 404.
    get_authorized_object_or_404(request.user, visible_rows(request.user), id, allow_datasoft=True)
    data = serializer_type(data=request.data)
    data.is_valid(raise_exception=True)
    try:
        issue = service(request.user, id, **data.validated_data)
    except workflow.VersionConflict as exc:
        raise Conflict(str(exc)) from exc
    except (DjangoPermissionDenied, DjangoValidationError) as exc:
        raise translate(exc) from exc
    return Response(IssueSerializer(issue).data)


class IssueAcceptView(APIView):
    @extend_schema(request=AcceptSerializer, responses=IssueSerializer, tags=["workflow"])
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, AcceptSerializer, workflow.accept)


class IssueRejectView(APIView):
    @extend_schema(request=ReasonSerializer, responses=IssueSerializer, tags=["workflow"])
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, ReasonSerializer, workflow.reject)


class IssueDateRevisionView(APIView):
    @extend_schema(request=DateRevisionSerializer, responses=IssueSerializer, tags=["workflow"])
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, DateRevisionSerializer, workflow.revise_date)


class IssueAssignView(APIView):
    @extend_schema(request=AssignSerializer, responses=IssueSerializer, tags=["workflow"])
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, AssignSerializer, workflow.assign)


class IssueStartView(APIView):
    @extend_schema(
        request=TransitionVersionSerializer, responses=IssueSerializer, tags=["workflow"]
    )
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, TransitionVersionSerializer, workflow.start)


class IssueDeliverView(APIView):
    @extend_schema(request=DeliverySerializer, responses=IssueSerializer, tags=["workflow"])
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, DeliverySerializer, workflow.deliver)


class IssueVerifyView(APIView):
    @extend_schema(
        request=TransitionVersionSerializer, responses=IssueSerializer, tags=["workflow"]
    )
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, TransitionVersionSerializer, workflow.verify)


class IssueFailVerificationView(APIView):
    @extend_schema(request=ReasonSerializer, responses=IssueSerializer, tags=["workflow"])
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, ReasonSerializer, workflow.fail_verification)


class IssueCloseView(APIView):
    @extend_schema(
        request=TransitionVersionSerializer, responses=IssueSerializer, tags=["workflow"]
    )
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, TransitionVersionSerializer, workflow.close)


class IssueReopenView(APIView):
    @extend_schema(request=ReasonSerializer, responses=IssueSerializer, tags=["workflow"])
    def post(self, request: Request, id: int) -> Response:
        return transition(request, id, ReasonSerializer, workflow.reopen)


class IssueEventDetailView(APIView):
    @extend_schema(responses=IssueEventSerializer, tags=["workflow"])
    def get(self, request: Request, id: int, event_id: int) -> Response:
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), id, allow_datasoft=True
        )
        event = get_authorized_object_or_404(
            request.user,
            IssueEvent.objects.filter(issue=issue),
            event_id,
            organization_field="issue__organization",
            allow_datasoft=True,
        )
        return Response(IssueEventSerializer(event).data)


class WorkflowSettingsView(APIView):
    @extend_schema(responses=WorkflowSettingsSerializer, tags=["workflow"])
    def get(self, request: Request) -> Response:
        setting, _ = WorkflowSettings.objects.get_or_create(pk=1)
        return Response(WorkflowSettingsSerializer(setting).data)

    @extend_schema(
        request=WorkflowSettingsSerializer, responses=WorkflowSettingsSerializer, tags=["workflow"]
    )
    def patch(self, request: Request) -> Response:
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("Only a DataSoft Administrator may change workflow settings.")
        data = WorkflowSettingsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        setting, _ = WorkflowSettings.objects.get_or_create(pk=1)
        setting.reopen_days = data.validated_data["reopen_days"]
        setting.save(update_fields=["reopen_days"])
        return Response(WorkflowSettingsSerializer(setting).data)


class WorkflowAssigneesView(APIView):
    @extend_schema(responses=WorkflowAssigneeSerializer(many=True), tags=["workflow"])
    def get(self, request: Request) -> Response:
        organization = portal_organization(request.user)
        if (
            organization is None
            or organization.kind != OrganizationKind.DATASOFT
            or not Membership.objects.filter(
                user=request.user, organization=organization, role__in=DATASOFT_ROLES
            ).exists()
        ):
            raise PermissionDenied("DataSoft staff role required.")
        users = (
            User.objects.filter(
                is_active=True,
                account__organization=organization,
                memberships__organization=organization,
                memberships__role__in=DATASOFT_ROLES,
            )
            .distinct()
            .order_by("account__full_name", "id")
        )
        return Response(WorkflowAssigneeSerializer(users, many=True).data)
