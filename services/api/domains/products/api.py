from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.api import ADMIN_PERMISSIONS
from domains.accounts.services import is_datasoft_admin
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import portal_organization

from .models import DeployedVersion, Module, Product, ResponseDuePeriod
from .serializers import (
    DeployedVersionSerializer,
    ModuleSerializer,
    ModuleWriteSerializer,
    ProductColorWriteSerializer,
    ProductSerializer,
    ProductWriteSerializer,
    ResponseDuePeriodsSerializer,
)


class ProductListView(APIView):
    @extend_schema(responses=ProductSerializer(many=True), tags=["products"])
    def get(self, request: Request) -> Response:
        products = Product.objects.filter(is_active=True).prefetch_related("modules")
        return Response(ProductSerializer(products, many=True).data)


class ProductAdminCreateView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(
        operation_id="admin_products_create",
        request=ProductWriteSerializer,
        responses={201: ProductSerializer},
        tags=["admin"],
    )
    def post(self, request: Request) -> Response:
        data = ProductWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                product = Product.objects.create(**data.validated_data)
        except IntegrityError as exc:
            raise ValidationError({"name": "Product already exists."}) from exc
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)


class ProductAdminDetailView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(
        operation_id="admin_products_update_color",
        request=ProductColorWriteSerializer,
        responses=ProductSerializer,
        tags=["admin"],
    )
    def patch(self, request: Request, product_id: int) -> Response:
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        product = get_object_or_404(Product, pk=product_id)
        data = ProductColorWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        for key, value in data.validated_data.items():
            setattr(product, key, value)
        product.save()
        return Response(ProductSerializer(product).data)


class ModuleAdminView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(request=ModuleWriteSerializer, responses={201: ModuleSerializer}, tags=["admin"])
    def post(self, request: Request, product_id: int) -> Response:
        product = get_object_or_404(Product, pk=product_id)
        data = ModuleWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                module = Module.objects.create(product=product, **data.validated_data)
        except IntegrityError as exc:
            raise ValidationError({"name": "Module already exists for this product."}) from exc
        return Response(ModuleSerializer(module).data, status=status.HTTP_201_CREATED)


class DeployedVersionView(APIView):
    def get_permissions(self):
        permissions = (
            ADMIN_PERMISSIONS if self.request.method == "POST" else self.permission_classes
        )
        return [permission() for permission in permissions]

    @extend_schema(responses=DeployedVersionSerializer(many=True), tags=["products"])
    def get(self, request: Request) -> Response:
        organization = portal_organization(request.user)
        rows = DeployedVersion.objects.select_related("organization", "product", "module")
        if organization is None:
            return Response([])
        if organization.kind == OrganizationKind.BANK:
            rows = rows.filter(organization=organization)
        return Response(DeployedVersionSerializer(rows, many=True).data)

    @extend_schema(
        request=DeployedVersionSerializer,
        responses={201: DeployedVersionSerializer},
        tags=["admin"],
    )
    def post(self, request: Request) -> Response:
        data = DeployedVersionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        row = data.save()
        return Response(DeployedVersionSerializer(row).data, status=status.HTTP_201_CREATED)


class ResponseDuePeriodsView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(responses=ResponseDuePeriodsSerializer, tags=["admin"])
    def get(self, request: Request) -> Response:
        configured = {row.priority: row.days for row in ResponseDuePeriod.objects.all()}
        return Response(
            {
                "periods": {
                    key: configured.get(key, days)
                    for key, days in {"LOW": 10, "MEDIUM": 5, "HIGH": 3, "CRITICAL": 1}.items()
                }
            }
        )

    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(
        request=ResponseDuePeriodsSerializer, responses=ResponseDuePeriodsSerializer, tags=["admin"]
    )
    def put(self, request: Request) -> Response:
        data = ResponseDuePeriodsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        for priority, days in data.validated_data["periods"].items():
            ResponseDuePeriod.objects.update_or_create(priority=priority, defaults={"days": days})
        return self.get(request)
