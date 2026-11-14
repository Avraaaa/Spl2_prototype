from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[type[Any]] = []

    @extend_schema(exclude=True)
    def get(self, request: Any) -> Response:
        return Response({"status": "ok", "service": "api", "stage": "skeleton"})
