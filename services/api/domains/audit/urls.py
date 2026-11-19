from django.urls import path

from .api import AuditAnchorView, AuditVerifyView

urlpatterns = [
    path("audit/verify/", AuditVerifyView.as_view(), name="audit-verify"),
    path("audit/anchor/", AuditAnchorView.as_view(), name="audit-anchor"),
]
