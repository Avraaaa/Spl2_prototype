from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from core.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/", include("domains.accounts.urls")),
    path("api/", include("domains.comments.urls")),
    path("api/", include("domains.tasks.urls")),
    path("api/", include("domains.attachments.urls")),
    path("api/", include("domains.products.urls")),
    path("api/", include("domains.issues.urls")),
    path("api/", include("domains.audit.urls")),
    path("api/", include("domains.notifications.urls")),
    path("api/", include("domains.reports.urls")),
    path("api/", include("domains.search.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
]
