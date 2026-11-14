from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import api

router = SimpleRouter(trailing_slash=True)
router.register("admin/organizations", api.OrganizationAdminViewSet, basename="admin-organization")
router.register("admin/users", api.UserAdminViewSet, basename="admin-user")

urlpatterns = [
    path("auth/csrf/", api.CsrfView.as_view(), name="auth-csrf"),
    path("auth/login/", api.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", api.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", api.MeView.as_view(), name="auth-me"),
    path("auth/change-password/", api.ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/change-username/", api.ChangeUsernameView.as_view(), name="auth-change-username"),
    path("", include(router.urls)),
]
