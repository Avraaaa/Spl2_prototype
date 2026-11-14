from rest_framework import serializers

from domains.products.models import Module, Product
from domains.tenants.selectors import authorized_rows

from .models import Issue, IssueEvent, Priority, RequestType


class IssueEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueEvent
        fields = ("id", "actor", "kind", "from_status", "to_status", "created_at")


class IssueSerializer(serializers.ModelSerializer):
    events = IssueEventSerializer(many=True, read_only=True)

    class Meta:
        model = Issue
        fields = (
            "id",
            "reference",
            "title",
            "description",
            "request_type",
            "product",
            "module",
            "priority",
            "environment",
            "steps_to_reproduce",
            "expected_result",
            "actual_result",
            "related_request",
            "status",
            "version",
            "created_by",
            "submitted_by",
            "submitted_at",
            "created_at",
            "updated_at",
            "events",
        )


class IssueWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    request_type = serializers.ChoiceField(choices=RequestType.choices, required=False)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), required=False, allow_null=True
    )
    module = serializers.PrimaryKeyRelatedField(
        queryset=Module.objects.filter(is_active=True), required=False, allow_null=True
    )
    priority = serializers.ChoiceField(choices=Priority.choices, required=False)
    environment = serializers.CharField(required=False, allow_blank=True)
    steps_to_reproduce = serializers.CharField(required=False, allow_blank=True)
    expected_result = serializers.CharField(required=False, allow_blank=True)
    actual_result = serializers.CharField(required=False, allow_blank=True)
    related_request = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unknown field." for key in unknown})
        return super().to_internal_value(data)

    def validate(self, attrs):
        issue = self.context.get("issue")
        product = attrs.get("product", issue.product if issue else None)
        module = attrs.get("module", issue.module if issue else None)
        if module and (not product or module.product_id != product.pk):
            raise serializers.ValidationError({"module": "Module must belong to the product."})
        if "related_request" in attrs and attrs["related_request"] is not None:
            user = self.context["request"].user
            rows = authorized_rows(user, Issue.objects.exclude(status="DRAFT"))
            related = rows.filter(pk=attrs["related_request"]).first()
            if related is None or (issue and related.pk == issue.pk):
                raise serializers.ValidationError({"related_request": "Invalid related request."})
            attrs["related_request"] = related
        return attrs
