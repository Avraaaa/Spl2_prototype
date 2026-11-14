from django.urls import path

from .api import CommentListView

urlpatterns = [path("issues/<int:id>/comments/", CommentListView.as_view(), name="issue-comments")]
