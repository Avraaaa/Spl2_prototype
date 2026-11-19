"""Read-only tenant-scoped report queries."""

from datetime import date, timedelta

from django.db.models import Count, Q, QuerySet
from django.db.models.functions import TruncMonth
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
    def officer_name(issue: Issue) -> str:
        account = getattr(issue.created_by, "account", None)
        return (account.full_name if account else "") or issue.created_by.username

    return [
        {
            "id": issue.pk,
            "reference_id": issue.reference or "",
            "bank": issue.organization.name,
            "issue_officer": officer_name(issue),
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
    by_status = {
        row["status"]: row["count"]
        for row in rows.order_by().values("status").annotate(count=Count("pk"))
    }
    by_month = {
        timezone.localtime(row["month"]).strftime("%Y-%m"): row["count"]
        for row in rows.order_by()
        .annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("pk"))
    }
    by_bank = (
        {
            row["organization__name"]: row["count"]
            for row in rows.order_by().values("organization__name").annotate(count=Count("pk"))
        }
        if staff
        else {}
    )
    result = {
        "total": rows.count(),
        "by_status": by_status,
        "by_month": by_month,
        "reopened_count": rows.filter(events__kind="REOPENED").distinct().count(),
        "recurring_count": rows.filter(recurring_of__isnull=False).count(),
    }
    if staff:
        result["by_bank"] = by_bank
    return result


def dashboard_counts(user) -> dict:
    organization = portal_organization(user)
    staff = bool(organization and organization.kind == OrganizationKind.DATASOFT)
    issues = scoped_issues(user, include_drafts=True)
    counts = {status: 0 for status in IssueStatus.values}
    counts.update(
        {
            row["status"]: row["count"]
            for row in issues.order_by().values("status").annotate(count=Count("pk"))
        }
    )
    result = {"total": sum(counts.values()), "by_status": counts}
    if staff:
        result["pending_intake"] = counts[IssueStatus.SUBMITTED]
        result["recent_deliveries"] = issues.filter(
            actual_delivery_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        result["overdue"] = overdue_rows(issues).count()
        result["by_bank"] = {
            row["organization__name"]: row["count"]
            for row in issues.order_by().values("organization__name").annotate(count=Count("pk"))
        }
    return result
