"""Read-only tenant-scoped report queries."""

from datetime import date, timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from domains.issues.models import Issue, IssueStatus
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import authorized_rows, portal_organization


def is_overdue(issue: Issue) -> bool:
    return bool(
        issue.tentative_delivery_date
        and issue.tentative_delivery_date < timezone.localdate()
        and issue.actual_delivery_at is None
    )


def overdue_rows(rows: QuerySet[Issue]) -> QuerySet[Issue]:
    return rows.filter(
        tentative_delivery_date__lt=timezone.localdate(), actual_delivery_at__isnull=True
    )


def scoped_issues(user, *, include_drafts: bool = False) -> QuerySet[Issue]:
    rows = Issue.objects.select_related("organization", "created_by__account")
    rows = authorized_rows(user, rows, allow_datasoft=True)
    organization = portal_organization(user)
    if organization is None:
        return rows.none()
    if organization.kind == OrganizationKind.DATASOFT or not include_drafts:
        rows = rows.exclude(status=IssueStatus.DRAFT)
    else:
        rows = rows.filter(~Q(status=IssueStatus.DRAFT) | Q(created_by=user))
    return rows


def report_rows(
    user,
    *,
    start: date,
    end: date,
    status: str = "",
    bank: int | None = None,
    overdue: bool = False,
) -> QuerySet[Issue]:
    rows = scoped_issues(user).filter(created_at__date__gte=start, created_at__date__lte=end)
    organization = portal_organization(user)
    if bank is not None and organization and organization.kind == OrganizationKind.DATASOFT:
        rows = rows.filter(organization_id=bank)
    if status:
        rows = rows.filter(status=status)
    if overdue:
        rows = overdue_rows(rows)
    return rows.order_by("-created_at", "-pk")


def detailed_rows(rows: QuerySet[Issue]) -> list[dict]:
    return [
        {
            "id": issue.pk,
            "reference_id": issue.reference or "",
            "bank": issue.organization.name,
            "issue_officer": issue.created_by.account.full_name,
            "title": issue.title,
            "issue_detail": issue.description,
            "status": issue.status,
            "creation_date": timezone.localtime(issue.created_at).date().isoformat(),
            "submission_date": (
                timezone.localtime(issue.submitted_at).date().isoformat()
                if issue.submitted_at
                else None
            ),
            "tentative_delivery_date": (
                issue.tentative_delivery_date.isoformat()
                if issue.tentative_delivery_date
                else "later"
                if issue.tentative_delivery_later
                else None
            ),
            "actual_delivery_date": (
                timezone.localtime(issue.actual_delivery_at).date().isoformat()
                if issue.actual_delivery_at
                else None
            ),
            "last_status_update_date": (
                timezone.localtime(issue.last_status_at).date().isoformat()
                if issue.last_status_at
                else None
            ),
            "closure_date": (
                timezone.localtime(issue.closed_at).date().isoformat() if issue.closed_at else None
            ),
            "is_overdue": is_overdue(issue),
        }
        for issue in rows
    ]


def summary_rows(rows: QuerySet[Issue], *, staff: bool) -> dict:
    issues = list(rows)
    by_status: dict[str, int] = {}
    by_month: dict[str, int] = {}
    by_bank: dict[str, int] = {}
    for issue in issues:
        by_status[issue.status] = by_status.get(issue.status, 0) + 1
        month = timezone.localtime(issue.created_at).strftime("%Y-%m")
        by_month[month] = by_month.get(month, 0) + 1
        if staff:
            by_bank[issue.organization.name] = by_bank.get(issue.organization.name, 0) + 1
    ids = [issue.pk for issue in issues]
    reopened = Issue.objects.filter(pk__in=ids, events__kind="REOPENED").distinct().count()
    result = {
        "total": len(issues),
        "by_status": by_status,
        "by_month": by_month,
        "reopened_count": reopened,
        "recurring_count": sum(issue.recurring_of_id is not None for issue in issues),
    }
    if staff:
        result["by_bank"] = by_bank
    return result


def dashboard_counts(user) -> dict:
    organization = portal_organization(user)
    staff = bool(organization and organization.kind == OrganizationKind.DATASOFT)
    issues = scoped_issues(user, include_drafts=True)
    counts = {status: issues.filter(status=status).count() for status in IssueStatus.values}
    result = {"total": sum(counts.values()), "by_status": counts}
    if staff:
        result["pending_intake"] = counts[IssueStatus.SUBMITTED]
        result["recent_deliveries"] = issues.filter(
            actual_delivery_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        result["overdue"] = overdue_rows(issues).count()
        by_bank: dict[str, int] = {}
        for name in issues.values_list("organization__name", flat=True):
            by_bank[name] = by_bank.get(name, 0) + 1
        result["by_bank"] = by_bank
    return result
