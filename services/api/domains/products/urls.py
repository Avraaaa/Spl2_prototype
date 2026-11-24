from django.urls import path

from .api import (
    DeployedVersionView,
    ModuleAdminView,
    ProductAdminCreateView,
    ProductAdminDetailView,
    ProductListView,
    ResponseDuePeriodsView,
)

urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("deployed-versions/", DeployedVersionView.as_view(), name="deployed-version-list-create"),
    path(
        "admin/response-due-periods/", ResponseDuePeriodsView.as_view(), name="response-due-periods"
    ),
    path("admin/products/", ProductAdminCreateView.as_view(), name="admin-product-create"),
    path(
        "admin/products/<int:product_id>/",
        ProductAdminDetailView.as_view(),
        name="admin-product-detail",
    ),
    path(
        "admin/products/<int:product_id>/modules/",
        ModuleAdminView.as_view(),
        name="admin-module-create",
    ),
]
