from django.urls import path

from .api import (
    DashboardCountsView,
    DetailedCsvView,
    DetailedReportView,
    ReportBanksView,
    SummaryCsvView,
    SummaryReportView,
)

urlpatterns = [
    path("reports/detailed/", DetailedReportView.as_view(), name="report-detailed"),
    path("reports/detailed/csv/", DetailedCsvView.as_view(), name="report-detailed-csv"),
    path("reports/summary/", SummaryReportView.as_view(), name="report-summary"),
    path("reports/summary/csv/", SummaryCsvView.as_view(), name="report-summary-csv"),
    path("reports/dashboard/", DashboardCountsView.as_view(), name="report-dashboard"),
    path("reports/banks/", ReportBanksView.as_view(), name="report-banks"),
]
