"""Tenant-scoped read policy for models with an organization relation.

Callers supply a server-owned queryset. Staff access across banks must be
requested explicitly for each approved use; the default is no rows for staff.
"""

from django.contrib.auth.models import User
from django.db.models import Model, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404

from domains.accounts.roles import BANK_ROLES, DATASOFT_ROLES

from .models import Organization, OrganizationKind


def portal_organization(user: User) -> Organization | None:
    """Return the account's active organization only with a matching valid role."""
    if not user.is_authenticated or not user.is_active:
        return None
    account = getattr(user, "account", None)
    if account is None:
        return None
    organization = account.organization
    if not organization.is_active:
        return None
    if organization.kind not in (OrganizationKind.DATASOFT, OrganizationKind.BANK):
        return None
    allowed_roles = DATASOFT_ROLES if organization.kind == OrganizationKind.DATASOFT else BANK_ROLES
    if not user.memberships.filter(organization=organization, role__in=allowed_roles).exists():
        return None
    return organization


def authorized_rows[M: Model](
    user: User,
    rows: QuerySet[M],
    *,
    organization_field: str = "organization",
    allow_datasoft: bool = False,
) -> QuerySet[M]:
    """Scope rows to the authenticated bank; staff need an explicit policy flag.

    ``organization_field`` is a server-chosen ORM field (``pk`` for Organization).
    Never pass a header, query parameter, or body value into this policy.
    """
    organization = portal_organization(user)
    if organization is None:
        return rows.none()
    if organization.kind == OrganizationKind.DATASOFT:
        return rows if allow_datasoft else rows.none()
    return rows.filter(**{organization_field: organization.pk})


def get_authorized_object_or_404[M: Model](
    user: User,
    rows: QuerySet[M],
    pk: int,
    *,
    organization_field: str = "organization",
    allow_datasoft: bool = False,
) -> M:
    """Resolve an object through the row policy so foreign IDs look absent."""
    scoped = authorized_rows(
        user, rows, organization_field=organization_field, allow_datasoft=allow_datasoft
    )
    try:
        return get_object_or_404(scoped, pk=pk)
    except (TypeError, ValueError) as exc:
        raise Http404 from exc
