from rest_framework import serializers


class DetailedReportRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    reference_id = serializers.CharField()
    bank = serializers.CharField()
    issue_officer = serializers.CharField()
    title = serializers.CharField()
    issue_detail = serializers.CharField()
    status = serializers.CharField()
    creation_date = serializers.CharField()
    submission_date = serializers.CharField(allow_null=True)
    tentative_delivery_date = serializers.CharField(allow_null=True)
    actual_delivery_date = serializers.CharField(allow_null=True)
    last_status_update_date = serializers.CharField(allow_null=True)
    closure_date = serializers.CharField(allow_null=True)
    is_overdue = serializers.BooleanField()
    response_due_date = serializers.CharField()


class SummaryReportSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    by_month = serializers.DictField(child=serializers.IntegerField())
    by_bank = serializers.DictField(child=serializers.IntegerField(), required=False)
    reopened_count = serializers.IntegerField()
    recurring_count = serializers.IntegerField()


class DashboardCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    pending_intake = serializers.IntegerField(required=False)
    recent_deliveries = serializers.IntegerField(required=False)
    overdue = serializers.IntegerField(required=False)
    by_bank = serializers.DictField(child=serializers.IntegerField(), required=False)


class ReportBankSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
