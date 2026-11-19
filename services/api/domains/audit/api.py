from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.services import is_datasoft_admin
from domains.tenants.models import Organization, OrganizationKind

from .services import anchor_head, verify_chain


class AnchorResponse(serializers.Serializer):
    anchors = serializers.ListField(child=serializers.DictField())


class AuditVerifyView(APIView):
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
