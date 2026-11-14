from django.urls import path

from .api import (
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
    UnreadCountView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path(
        "notifications/unread-count/", UnreadCountView.as_view(), name="notification-unread-count"
    ),
    path(
        "notifications/read-all/", NotificationReadAllView.as_view(), name="notification-read-all"
    ),
    path("notifications/<int:id>/read/", NotificationReadView.as_view(), name="notification-read"),
]
