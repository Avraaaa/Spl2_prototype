from django.urls import path

from .api import IssueDetailView, IssueListView, IssueSubmitView

urlpatterns = [
    path("issues/", IssueListView.as_view(), name="issue-list"),
    path("issues/<int:id>/", IssueDetailView.as_view(), name="issue-detail"),
    path("issues/<int:id>/submit/", IssueSubmitView.as_view(), name="issue-submit"),
]
