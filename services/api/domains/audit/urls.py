from django.urls import path

from .api import AuditVerifyView

urlpatterns = [path("audit/verify/", AuditVerifyView.as_view(), name="audit-verify")]
