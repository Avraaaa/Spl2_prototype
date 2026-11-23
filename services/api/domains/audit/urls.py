from django.urls import path

from .api import (
    AuditAnchorView,
    AuditRecordDetailView,
    AuditRecordExportView,
    AuditRecordListView,
    AuditVerifyView,
)

urlpatterns = [
    path("audit/records/", AuditRecordListView.as_view(), name="audit-records"),
    path("audit/records/<int:pk>/", AuditRecordDetailView.as_view(), name="audit-record-detail"),
    path("audit/records/export/", AuditRecordExportView.as_view(), name="audit-records-export"),
    path("audit/verify/", AuditVerifyView.as_view(), name="audit-verify"),
    path("audit/anchor/", AuditAnchorView.as_view(), name="audit-anchor"),
]
