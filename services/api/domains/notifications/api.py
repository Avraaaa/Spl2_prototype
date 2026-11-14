from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import portal_organization

from .models import Notification
from .serializers import NotificationSerializer, UnreadCountSerializer


def own_rows(request: Request):
    organization = portal_organization(request.user)
    rows = Notification.objects.filter(recipient=request.user)
    if organization is None:
        return rows.none()
    if organization.kind == OrganizationKind.BANK:
        return rows.filter(organization=organization)
    # Staff can read their personally addressed notifications across client issues.
    return rows


class NotificationListView(APIView):
    @extend_schema(responses=NotificationSerializer(many=True), tags=["notifications"])
    def get(self, request: Request) -> Response:
        return Response(NotificationSerializer(own_rows(request)[:100], many=True).data)


class UnreadCountView(APIView):
    @extend_schema(responses=UnreadCountSerializer, tags=["notifications"])
    def get(self, request: Request) -> Response:
        return Response({"count": own_rows(request).filter(read_at__isnull=True).count()})


class NotificationReadView(APIView):
    @extend_schema(request=None, responses=NotificationSerializer, tags=["notifications"])
    def post(self, request: Request, id: int) -> Response:
        notification = get_object_or_404(own_rows(request), pk=id)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllView(APIView):
    @extend_schema(request=None, responses=UnreadCountSerializer, tags=["notifications"])
    def post(self, request: Request) -> Response:
        own_rows(request).filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"count": 0})
