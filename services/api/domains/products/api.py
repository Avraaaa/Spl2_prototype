from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.api import ADMIN_PERMISSIONS

from .models import Module, Product
from .serializers import (
    ModuleSerializer,
    ModuleWriteSerializer,
    ProductSerializer,
    ProductWriteSerializer,
)


class ProductListView(APIView):
    @extend_schema(responses=ProductSerializer(many=True), tags=["products"])
    def get(self, request: Request) -> Response:
        products = Product.objects.filter(is_active=True).prefetch_related("modules")
        return Response(ProductSerializer(products, many=True).data)


class ProductAdminView(APIView):
    permission_classes = ADMIN_PERMISSIONS

    @extend_schema(
        request=ProductWriteSerializer, responses={201: ProductSerializer}, tags=["admin"]
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
