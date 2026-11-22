"""Account write services. Mutations append AccountEvents; password storage is always hashed.
Plain credentials exist only in the one-time email body needed for delivery."""

import secrets
from collections.abc import Iterable
from datetime import timedelta
from hashlib import sha256

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.html import escape

from domains.tenants.models import Organization, OrganizationKind
from domains.tenants.selectors import portal_organization

from .models import Account, AccountEvent, Membership, PasswordResetToken
from .roles import BANK_ROLES, DATASOFT_ROLES, Role

LOGIN_RATE_PER_MINUTE: int = settings.LOGIN_RATE_PER_MINUTE
TEMPORARY_PASSWORD_TTL = timedelta(hours=settings.TEMPORARY_PASSWORD_TTL_HOURS)


def roles_of(user: User) -> list[str]:
    organization = portal_organization(user)
    if organization is None:
        return []
    allowed = DATASOFT_ROLES if organization.kind == OrganizationKind.DATASOFT else BANK_ROLES
    return sorted(
        m.role
        for m in user.memberships.all()
        if m.organization_id == organization.pk and m.role in allowed
    )


def is_datasoft_admin(user: User) -> bool:
    organization = portal_organization(user)
    return bool(
        organization is not None
        and organization.kind == OrganizationKind.DATASOFT
        and Membership.objects.filter(
            user=user, role=Role.DATASOFT_ADMIN, organization=organization
        ).exists()
    )


def _require_admin(actor: User) -> None:
    if not is_datasoft_admin(actor):
        raise PermissionDenied("Only a DataSoft Administrator may manage accounts.")


def _event(actor: User | None, subject: User, kind: str, **details: object) -> None:
    AccountEvent.objects.create(actor=actor, subject=subject, kind=kind, details=details)


def validate_roles(organization: Organization, roles: Iterable[str]) -> list[Role]:
    chosen = [Role(r) for r in roles]
    if not chosen or len(set(chosen)) != len(chosen):
        raise ValidationError("Provide at least one distinct role.")
    allowed = DATASOFT_ROLES if organization.kind == OrganizationKind.DATASOFT else BANK_ROLES
    if not set(chosen) <= allowed:
        raise ValidationError(
            f"Roles {sorted(chosen)} are not valid for a {organization.kind} organization."
        )
    if organization.kind == OrganizationKind.DATASOFT and len(chosen) != 1:
        raise ValidationError("DataSoft roles are mutually exclusive.")
    return chosen


def ensure_datasoft_organization() -> Organization:
    org, _ = Organization.objects.get_or_create(
        kind=OrganizationKind.DATASOFT, defaults={"name": "DataSoft", "code": "DATASOFT"}
    )
    return org


@transaction.atomic
def register_organization(
    actor: User, *, name: str, code: str, contact_email: str = ""
) -> Organization:
    _require_admin(actor)
    return Organization.objects.create(
        name=name.strip(),
        code=code.strip().upper(),
        kind=OrganizationKind.BANK,
        contact_email=contact_email.strip(),
        contact_email_placeholder=not bool(contact_email.strip()),
    )


def create_user_unchecked(
    *, organization: Organization, username: str, email: str, full_name: str, roles: Iterable[str]
) -> User:
    """Internal constructor used by authorized services, seed data and tests."""
    chosen = validate_roles(organization, roles)
    if not organization.is_active:
        raise ValidationError("Organization is inactive.")
    user = User.objects.create_user(username=username, email=email)
    user.set_unusable_password()
    user.save()
    Account.objects.create(user=user, organization=organization, full_name=full_name)
    Membership.objects.bulk_create(
        Membership(user=user, organization=organization, role=r) for r in chosen
    )
    return user


def _issue_temporary_password(user: User) -> str:
    temporary = secrets.token_urlsafe(12)
    user.set_password(temporary)  # salted hash; also invalidates existing sessions
    user.save(update_fields=["password"])
    account = user.account
    account.must_change_password = True
    account.temporary_password_expires_at = timezone.now() + TEMPORARY_PASSWORD_TTL
    account.save(update_fields=["must_change_password", "temporary_password_expires_at"])
    return temporary


def _email_account_message(user: User, subject: str, body: str, key: str) -> None:
    from domains.notifications.models import OutboxMessage

    OutboxMessage.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "channel": OutboxMessage.Channel.EMAIL,
            "recipient": user,
            "payload": {
                "subject": subject,
                "body": body,
                "html": f"<p>{escape(body).replace(chr(10), '<br>')}</p>",
                "to": user.email,
            },
            "next_attempt_at": timezone.now(),
        },
    )


def email_delivery_configured() -> bool:
    # This is intentionally independent of EMAIL_BACKEND: locmem and console are
    # useful test/development transports, but neither means account delivery is configured.
    return bool(settings.EMAIL_DELIVERY_CONFIGURED)


def _send_temporary_credential(user: User, temporary: str, *, key: str) -> None:
    from domains.notifications.models import OutboxMessage

    del temporary  # configured delivery uses a one-time setup link, never the password

    OutboxMessage.objects.filter(
        recipient=user,
        channel=OutboxMessage.Channel.EMAIL,
        status__in=[OutboxMessage.Status.PENDING, OutboxMessage.Status.FAILED],
        idempotency_key__in=[f"account-created:{user.pk}"],
    ).delete()
    OutboxMessage.objects.filter(
        recipient=user,
        channel=OutboxMessage.Channel.EMAIL,
        status__in=[OutboxMessage.Status.PENDING, OutboxMessage.Status.FAILED],
        idempotency_key__startswith=f"admin-credential-reset:{user.pk}:",
    ).delete()
    now = timezone.now()
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
    raw = secrets.token_urlsafe(32)
    token = PasswordResetToken.objects.create(
        user=user,
        token_hash=sha256(raw.encode()).hexdigest(),
        expires_at=now + timedelta(minutes=max(1, int(settings.PASSWORD_RESET_TTL_MINUTES))),
    )
    uid = f"{user.pk}.{token.pk}"
    link = f"{settings.PORTAL_BASE_URL}/reset-password?uid={uid}#token={raw}"
    body = (
        f"Hello {user.account.full_name},\n\n"
        f"Username: {user.username}\nSet your password using this one-time link:\n{link}\n\n"
        f"The link expires in {settings.PASSWORD_RESET_TTL_MINUTES} minutes."
    )
    _email_account_message(
        user,
        "Set up your DataSoft portal password",
        body,
        key,
    )


@transaction.atomic
def create_user(
    actor: User,
    *,
    organization: Organization,
    username: str,
    email: str,
    full_name: str,
    roles: Iterable[str],
) -> tuple[User, str]:
    """Returns the user and a one-time temporary password to hand over out of band.
    Security exception (invariant 11): production should use a one-time setup link."""
    _require_admin(actor)
    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError("Username already exists.")
    user = create_user_unchecked(
        organization=organization, username=username, email=email, full_name=full_name, roles=roles
    )
    temporary = _issue_temporary_password(user)
    if email_delivery_configured():
        _send_temporary_credential(user, temporary, key=f"account-created:{user.pk}")
    _event(
        actor,
        user,
        "USER_CREATED",
        organization=organization.code,
        contact_email=organization.contact_email,
        roles=roles_of(user),
    )
    return user, temporary


@transaction.atomic
def force_password_reset(actor: User, user: User) -> str:
    _require_admin(actor)
    temporary = _issue_temporary_password(user)
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    if email_delivery_configured():
        _send_temporary_credential(
            user, temporary, key=f"admin-credential-reset:{user.pk}:{secrets.token_hex(8)}"
        )
    _event(actor, user, "PASSWORD_RESET_FORCED")
    return temporary


@transaction.atomic
def deactivate_user(actor: User, user: User) -> User:
    _require_admin(actor)
    if actor.pk == user.pk:
        raise ValidationError("Administrators cannot deactivate themselves.")
    user.is_active = False  # ModelBackend then rejects the live session and new logins
    user.save(update_fields=["is_active"])
    _event(actor, user, "USER_DEACTIVATED", contact_email=user.account.organization.contact_email)
    return user


@transaction.atomic
def assign_roles(actor: User, user: User, roles: Iterable[str]) -> User:
    _require_admin(actor)
    organization = user.account.organization
    chosen = validate_roles(organization, roles)
    if actor.pk == user.pk and Role.DATASOFT_ADMIN not in chosen:
        raise ValidationError("Administrators cannot remove their own admin role.")
    Membership.objects.filter(user=user).delete()
    Membership.objects.bulk_create(
        Membership(user=user, organization=organization, role=r) for r in chosen
    )
    _event(
        actor,
        user,
        "ROLES_ASSIGNED",
        roles=sorted(chosen),
        contact_email=organization.contact_email,
    )
    return user


@transaction.atomic
def request_password_reset(email: str) -> None:
    """Queue a generic reset response; unknown addresses have no observable result."""
    user = User.objects.filter(email__iexact=email, is_active=True, account__isnull=False).first()
    if user is None:
        return
    now = timezone.now()
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
    raw = secrets.token_urlsafe(32)
    digest = sha256(raw.encode()).hexdigest()
    token = PasswordResetToken.objects.create(
        user=user,
        token_hash=digest,
        expires_at=now + timedelta(minutes=max(1, int(settings.PASSWORD_RESET_TTL_MINUTES))),
    )
    uid = f"{user.pk}.{token.pk}"
    link = f"{settings.PORTAL_BASE_URL}/reset-password?uid={uid}#token={raw}"
    # Preserve links used by the local console fallback. Once email delivery is
    # configured, the secret is only in the fragment and never reaches servers
    # through request URLs or referrers. The reset page migrates legacy query
    # tokens into the fragment and removes them from browser history.
    if not email_delivery_configured():
        link = f"{settings.PORTAL_BASE_URL}/reset-password?uid={uid}&token={raw}#token={raw}"
    _email_account_message(
        user,
        "Reset your DataSoft portal password",
        f"Use this one-time link within {settings.PASSWORD_RESET_TTL_MINUTES} minutes:\n{link}",
        f"password-reset:{token.pk}",
    )


@transaction.atomic
def complete_password_reset(*, uid: str, raw_token: str, password: str) -> None:
    try:
        user_id, token_id = (int(part) for part in uid.split(".", 1))
        token = (
            PasswordResetToken.objects.select_for_update()
            .select_related("user")
            .get(pk=token_id, user_id=user_id)
        )
    except (ValueError, PasswordResetToken.DoesNotExist) as exc:
        raise ValidationError("This reset link is invalid or expired.") from exc
    digest = sha256(raw_token.encode()).hexdigest()
    if (
        token.used_at is not None
        or token.expires_at <= timezone.now()
        or not constant_time_compare(token.token_hash, digest)
        or not token.user.is_active
    ):
        raise ValidationError("This reset link is invalid or expired.")
    validate_password(password, token.user)
    token.user.set_password(password)
    token.user.save(update_fields=["password"])
    account = token.user.account
    account.must_change_password = False
    account.temporary_password_expires_at = None
    account.save(update_fields=["must_change_password", "temporary_password_expires_at"])
    now = timezone.now()
    PasswordResetToken.objects.filter(user=token.user, used_at__isnull=True).update(used_at=now)
    _event(None, token.user, "PASSWORD_RESET_COMPLETED")


def temporary_credential_expired(user: User) -> bool:
    account = user.account
    return bool(
        account.must_change_password
        and account.temporary_password_expires_at is not None
        and account.temporary_password_expires_at <= timezone.now()
    )


@transaction.atomic
def change_password(user: User, *, current_password: str, new_password: str) -> None:
    if not user.check_password(current_password):
        raise ValidationError({"current_password": "Current password is incorrect."})
    if temporary_credential_expired(user):
        raise ValidationError(
            {"current_password": "Temporary password expired. Ask an administrator for a reset."}
        )
    validate_password(new_password, user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    account = user.account
    account.must_change_password = False
    account.temporary_password_expires_at = None
    account.save(update_fields=["must_change_password", "temporary_password_expires_at"])
    _event(user, user, "PASSWORD_CHANGED")


@transaction.atomic
def update_profile(user: User, *, full_name: str | None = None, email: str | None = None) -> User:
    """Change only the caller's basic profile and record actual old/new values."""
    locked = User.objects.select_for_update().get(pk=user.pk)
    if not locked.is_active:
        raise PermissionDenied("Inactive accounts cannot edit profiles.")
    account = Account.objects.select_for_update().get(user=locked)
    if account.must_change_password:
        raise PermissionDenied("Password change required.")
    changes: dict[str, dict[str, str]] = {}
    if full_name is not None and full_name != account.full_name:
        changes["full_name"] = {"old": account.full_name, "new": full_name}
        account.full_name = full_name
        account.save(update_fields=["full_name"])
    if email is not None and email != locked.email:
        changes["email"] = {"old": locked.email, "new": email}
        locked.email = email
        locked.save(update_fields=["email"])
    if changes:
        _event(locked, locked, "PROFILE_UPDATED", **changes)
    user.email = locked.email
    user.account.full_name = account.full_name
    return user


@transaction.atomic
def change_username(user: User, *, username: str, current_password: str) -> User:
    locked = User.objects.select_for_update().get(pk=user.pk)
    if not locked.is_active:
        raise PermissionDenied("Inactive accounts cannot change usernames.")
    if locked.account.must_change_password:
        raise PermissionDenied("Password change required.")
    if not locked.check_password(current_password):
        raise ValidationError({"current_password": "Current password is incorrect."})
    if User.objects.filter(username__iexact=username).exclude(pk=locked.pk).exists():
        raise ValidationError({"username": "Username already exists."})
    if username != locked.username:
        old = locked.username
        locked.username = username
        locked.save(update_fields=["username"])
        _event(locked, locked, "USERNAME_CHANGED", username={"old": old, "new": username})
    user.username = locked.username
    return user
