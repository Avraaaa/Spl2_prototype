from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthSerializer(serializers.Serializer[dict[str, str]]):
    status = serializers.CharField()
    service = serializers.CharField()
    stage = serializers.CharField()


class HealthView(APIView):
    """Unauthenticated liveness probe. Intentionally in the contract so the generated
    TypeScript client can verify frontend-to-Django connectivity; exposes no data."""

    permission_classes = [AllowAny]
    authentication_classes: list[type[Any]] = []

    @extend_schema(responses=HealthSerializer, operation_id="health_retrieve", tags=["health"])
    def get(self, request: Any) -> Response:
        return Response({"status": "ok", "service": "api", "stage": "skeleton"})
