from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.services import is_datasoft_admin
from domains.tenants.selectors import portal_organization

from .services import verify_chain


class AuditVerifyView(APIView):
    @extend_schema(responses=dict, tags=["audit"])
    def get(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        organization = portal_organization(request.user)
        return Response(verify_chain(organization))
