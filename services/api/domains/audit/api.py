import csv

from django.http import HttpResponse
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.permissions import (
    HasPortalAccount,
    IsDataSoftAdmin,
    PasswordChangeCompleted,
)
from domains.accounts.services import is_datasoft_admin
from domains.tenants.models import Organization, OrganizationKind

from .services import anchor_head, verify_chain

ADMIN_PERMISSIONS = [
    IsAuthenticated,
    HasPortalAccount,
    PasswordChangeCompleted,
    IsDataSoftAdmin,
]


class AuditRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    organization_code = serializers.CharField()
    organization_name = serializers.CharField()
    sequence = serializers.IntegerField()
    actor_username = serializers.CharField()
    action = serializers.CharField()
    payload = serializers.JSONField()
    previous_hash = serializers.CharField()
    record_hash = serializers.CharField()
    created_at = serializers.DateTimeField()


class ChainIntegritySerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    first_invalid_sequence = serializers.IntegerField(allow_null=True)


class OrganizationIntegritySerializer(ChainIntegritySerializer):
    code = serializers.CharField()
    name = serializers.CharField()


class AuditListResponse(serializers.Serializer):
    results = AuditRecordSerializer(many=True)
    integrity = ChainIntegritySerializer()
    organizations = OrganizationIntegritySerializer(many=True)


def _filtered_records(request):
    from .models import AuditRecord

    rows = AuditRecord.objects.select_related("organization", "actor").order_by(
        "-created_at", "-pk"
    )
    code = request.query_params.get("organization", "").strip()
    if code:
        rows = rows.filter(organization__code__iexact=code)
    action = request.query_params.get("action", "").strip()
    if action:
        rows = rows.filter(action__icontains=action)
    actor = request.query_params.get("actor", "").strip()
    if actor:
        rows = rows.filter(actor__username__icontains=actor)
    after = request.query_params.get("after")
    before = request.query_params.get("before")
    if after:
        after_date = parse_date(after)
        if after_date is None:
            raise ValidationError({"after": "Use an ISO date in YYYY-MM-DD format."})
        rows = rows.filter(created_at__date__gte=after_date)
    if before:
        before_date = parse_date(before)
        if before_date is None:
            raise ValidationError({"before": "Use an ISO date in YYYY-MM-DD format."})
        rows = rows.filter(created_at__date__lte=before_date)
    return rows


def _csv_cell(value):
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return f"'{text}"
    return text


class AuditRecordListView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(
        parameters=[
            OpenApiParameter("organization", str, description="Bank organization code"),
            OpenApiParameter("action", str),
            OpenApiParameter("actor", str),
            OpenApiParameter("after", str, description="Inclusive ISO date"),
            OpenApiParameter("before", str, description="Inclusive ISO date"),
        ],
        responses=AuditListResponse,
        tags=["audit"],
    )
    def get(self, request):
        organizations = list(
            Organization.objects.filter(kind=OrganizationKind.BANK, is_active=True)
        )
        selected_code = request.query_params.get("organization", "").strip()
        selected = next(
            (org for org in organizations if org.code.casefold() == selected_code.casefold()),
            None,
        )
        if selected_code and selected is None:
            return Response({"detail": "Unknown bank organization."}, status=400)
        results = {
            org.code: verify_chain(org) for org in ([selected] if selected else organizations)
        }
        records = _filtered_records(request)[:500]
        serialized_records = AuditRecordSerializer(
            [
                {
                    "id": row.pk,
                    "organization_code": row.organization.code,
                    "organization_name": row.organization.name,
                    "sequence": row.sequence,
                    "actor_username": row.actor.username,
                    "action": row.action,
                    "payload": row.payload,
                    "previous_hash": row.previous_hash,
                    "record_hash": row.record_hash,
                    "created_at": row.created_at,
                }
                for row in records
            ],
            many=True,
        ).data
        integrity = (
            results.get(selected.code)
            if selected
            else {
                "valid": all(item["valid"] for item in results.values()),
                "first_invalid_sequence": next(
                    (
                        item["first_invalid_sequence"]
                        for item in results.values()
                        if not item["valid"]
                    ),
                    None,
                ),
            }
        )
        return Response(
            {
                "results": serialized_records,
                "integrity": integrity,
                "organizations": [
                    {"code": org.code, "name": org.name, **verify_chain(org)}
                    for org in organizations
                ],
            }
        )


class AuditRecordDetailView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(
        operation_id="audit_record_retrieve",
        responses=AuditRecordSerializer,
        tags=["audit"],
    )
    def get(self, request, pk):
        from .models import AuditRecord

        try:
            row = AuditRecord.objects.select_related("organization", "actor").get(pk=pk)
        except AuditRecord.DoesNotExist:
            from django.http import Http404

            raise Http404 from None
        return Response(
            AuditRecordSerializer(
                {
                    "id": row.pk,
                    "organization_code": row.organization.code,
                    "organization_name": row.organization.name,
                    "sequence": row.sequence,
                    "actor_username": row.actor.username,
                    "action": row.action,
                    "payload": row.payload,
                    "previous_hash": row.previous_hash,
                    "record_hash": row.record_hash,
                    "created_at": row.created_at,
                }
            ).data
        )


class AuditRecordExportView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(
        parameters=[
            OpenApiParameter("organization", str),
            OpenApiParameter("action", str),
            OpenApiParameter("actor", str),
            OpenApiParameter("after", str),
            OpenApiParameter("before", str),
        ],
        responses={(200, "text/csv"): OpenApiTypes.BINARY},
        tags=["audit"],
    )
    def get(self, request):
        output = HttpResponse(content_type="text/csv; charset=utf-8")
        output["Content-Disposition"] = 'attachment; filename="audit-records.csv"'
        writer = csv.writer(output)
        writer.writerow(
            [
                "organization_code",
                "organization_name",
                "sequence",
                "created_at",
                "actor",
                "action",
                "payload",
                "previous_hash",
                "record_hash",
            ]
        )
        for row in _filtered_records(request):
            writer.writerow(
                [
                    _csv_cell(row.organization.code),
                    _csv_cell(row.organization.name),
                    row.sequence,
                    row.created_at.isoformat(),
                    _csv_cell(row.actor.username),
                    _csv_cell(row.action),
                    _csv_cell(row.payload),
                    row.previous_hash,
                    row.record_hash,
                ]
            )
        return output


class AnchorResponse(serializers.Serializer):
    anchors = serializers.ListField(child=serializers.DictField())


class AuditVerifyView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(responses=dict, tags=["audit"])
    def get(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        results = {
            organization.code: verify_chain(organization)
            for organization in Organization.objects.filter(
                kind=OrganizationKind.BANK, is_active=True
            )
        }
        return Response(
            {
                "valid": all(result["valid"] for result in results.values()),
                "organizations": results,
            }
        )


class AuditAnchorView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(request=None, responses=AnchorResponse, tags=["audit"])
    def post(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        anchors = []
        for organization in Organization.objects.filter(kind=OrganizationKind.BANK, is_active=True):
            try:
                anchor = anchor_head(organization=organization, actor=request.user)
            except ValueError:
                continue
            anchors.append(
                {
                    "organization": organization.pk,
                    "sequence": anchor.sequence,
                    "record_hash": anchor.record_hash,
                }
            )
        return Response({"anchors": anchors}, status=201)
