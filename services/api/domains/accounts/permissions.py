from typing import Any

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .services import is_datasoft_admin


class PasswordChangeCompleted(BasePermission):
    """Global gate: after a temporary-credential login only the auth endpoints that
    explicitly opt out of this class (me, change-password, logout) are reachable."""

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        account = getattr(user, "account", None) if user and user.is_authenticated else None
        if account is not None and account.must_change_password:
            raise PermissionDenied(
                {"detail": "Password change required.", "code": "password_change_required"}
            )
        return True


class HasPortalAccount(BasePermission):
    """Authenticated Django users without an Account (e.g. bare superusers) get no API access."""

    def has_permission(self, request: Any, view: Any) -> bool:
        return bool(
            request.user and request.user.is_authenticated and hasattr(request.user, "account")
        )


class IsDataSoftAdmin(BasePermission):
    def has_permission(self, request: Any, view: Any) -> bool:
        return is_datasoft_admin(request.user)
