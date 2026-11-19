"""JSON and CSV views share the exact same scoped selectors."""

import csv
from datetime import date

from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.issues.models import IssueStatus
from domains.tenants.models import Organization, OrganizationKind
from domains.tenants.selectors import portal_organization

from .selectors import dashboard_counts, detailed_rows, report_rows, summary_rows
from .serializers import (
    DashboardCountsSerializer,
    DetailedReportRowSerializer,
    ReportBankSerializer,
    SummaryReportSerializer,
)

PARAMETERS = [
    OpenApiParameter("start", OpenApiTypes.DATE),
    OpenApiParameter("end", OpenApiTypes.DATE),
    OpenApiParameter("status", str),
    OpenApiParameter("bank", int),
    OpenApiParameter("overdue", bool),
]
CSV_COLUMNS = [
    "reference_id",
    "bank",
    "issue_officer",
    "title",
    "issue_detail",
    "status",
    "creation_date",
    "submission_date",
    "tentative_delivery_date",
    "actual_delivery_date",
    "last_status_update_date",
    "closure_date",
]


def _filters(request: Request) -> dict:
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.query_params.get("start", f"{today.year}-01-01"))
        end = date.fromisoformat(request.query_params.get("end", f"{today.year}-12-31"))
    except ValueError as exc:
        raise ValidationError({"date": "Use YYYY-MM-DD."}) from exc
    if start > end:
        raise ValidationError({"date": "Start must be on or before end."})
    status = request.query_params.get("status", "")
    if status and status not in IssueStatus.values:
        raise ValidationError({"status": "Invalid status."})
    bank = None
    organization = portal_organization(request.user)
    if organization and organization.kind == OrganizationKind.DATASOFT:
        value = request.query_params.get("bank", "")
        if value:
            try:
                bank = int(value)
                if bank < 1:
                    raise ValueError
            except ValueError as exc:
                raise ValidationError({"bank": "Invalid bank."}) from exc
    overdue_value = request.query_params.get("overdue", "false").lower()
    if overdue_value not in ("true", "false"):
        raise ValidationError({"overdue": "Use true or false."})
    return {
        "start": start,
        "end": end,
        "status": status,
        "bank": bank,
        "overdue": overdue_value == "true",
    }


def _rows(request: Request):
    return report_rows(request.user, **_filters(request))


def _safe(value: object) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _csv(filename: str, headings: list[str], rows: list[list[object]]) -> HttpResponse:
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(headings)
    for row in rows:
        writer.writerow([_safe(value) for value in row])
    return response


class DetailedReportView(APIView):
    @extend_schema(
        parameters=PARAMETERS, responses=DetailedReportRowSerializer(many=True), tags=["reports"]
    )
    def get(self, request: Request) -> Response:
        return Response(detailed_rows(_rows(request)))


class SummaryReportView(APIView):
    @extend_schema(parameters=PARAMETERS, responses=SummaryReportSerializer, tags=["reports"])
    def get(self, request: Request) -> Response:
        organization = portal_organization(request.user)
        staff = bool(organization and organization.kind == OrganizationKind.DATASOFT)
        return Response(summary_rows(_rows(request), staff=staff))


class DetailedCsvView(APIView):
    @extend_schema(
        parameters=PARAMETERS, responses={(200, "text/csv"): OpenApiTypes.BINARY}, tags=["reports"]
    )
    def get(self, request: Request) -> HttpResponse:
        rows = detailed_rows(_rows(request))
        return _csv(
            "detailed-report.csv", CSV_COLUMNS, [[row[key] for key in CSV_COLUMNS] for row in rows]
        )


class SummaryCsvView(APIView):
    @extend_schema(
        parameters=PARAMETERS, responses={(200, "text/csv"): OpenApiTypes.BINARY}, tags=["reports"]
    )
    def get(self, request: Request) -> HttpResponse:
        organization = portal_organization(request.user)
        staff = bool(organization and organization.kind == OrganizationKind.DATASOFT)
        summary = summary_rows(_rows(request), staff=staff)
        records: list[list[object]] = [
            ["total", "all", summary["total"]],
            ["reopened", "all", summary["reopened_count"]],
            ["recurring", "all", summary["recurring_count"]],
        ]
        for group, field in (
            ("status", "by_status"),
            ("month", "by_month"),
            ("bank", "by_bank"),
        ):
            for label, count in summary.get(field, {}).items():
                records.append([group, label, count])
        return _csv("summary-report.csv", ["group", "label", "count"], records)


class DashboardCountsView(APIView):
    @extend_schema(responses=DashboardCountsSerializer, tags=["reports"])
    def get(self, request: Request) -> Response:
        return Response(dashboard_counts(request.user))


class ReportBanksView(APIView):
    @extend_schema(responses=ReportBankSerializer(many=True), tags=["reports"])
    def get(self, request: Request) -> Response:
        organization = portal_organization(request.user)
        if organization is None or organization.kind != OrganizationKind.DATASOFT:
            raise PermissionDenied("DataSoft staff role required.")
        banks = Organization.objects.filter(kind=OrganizationKind.BANK, is_active=True).order_by(
            "name"
        )
        return Response(ReportBankSerializer(banks, many=True).data)
