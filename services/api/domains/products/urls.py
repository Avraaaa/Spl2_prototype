from django.urls import path

from .api import ModuleAdminView, ProductAdminView, ProductListView

urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("admin/products/", ProductAdminView.as_view(), name="admin-product-create"),
    path(
        "admin/products/<int:product_id>/modules/",
        ModuleAdminView.as_view(),
        name="admin-module-create",
    ),
]
