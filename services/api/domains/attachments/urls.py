from django.urls import path

from .api import AttachmentDownloadView, IssueAttachmentListView

urlpatterns = [
    path(
        "issues/<int:id>/attachments/", IssueAttachmentListView.as_view(), name="issue-attachments"
    ),
    path(
        "attachments/<int:id>/download/",
        AttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
]
