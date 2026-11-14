from django.urls import path

from .api import IssueNoteListView, TaskDetailView, TaskListView, TaskNoteListView

urlpatterns = [
    path("tasks/", TaskListView.as_view(), name="task-list"),
    path("tasks/<int:id>/", TaskDetailView.as_view(), name="task-detail"),
    path("tasks/<int:id>/notes/", TaskNoteListView.as_view(), name="task-notes"),
    path(
        "issues/<int:id>/internal-notes/", IssueNoteListView.as_view(), name="issue-internal-notes"
    ),
]
