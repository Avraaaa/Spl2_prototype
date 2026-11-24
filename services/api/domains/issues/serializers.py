from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from domains.products.models import Module, Product
from domains.search.models import IssueLabelSelection
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import authorized_rows, portal_organization

from .models import Issue, IssueEvent, Priority, RequestType, WorkflowSettings


class ConfirmedLabelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class IssueEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.account.full_name", read_only=True)
    assignee_name = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_assignee_name(self, obj: IssueEvent) -> str | None:
        assignee_id = obj.details.get("to_assignee") if isinstance(obj.details, dict) else None
        if not isinstance(assignee_id, int):
            return None
        user = User.objects.filter(pk=assignee_id).select_related("account").first()
        return user.account.full_name if user else None

    class Meta:
        model = IssueEvent
        fields = (
            "id",
            "actor",
            "actor_name",
            "assignee_name",
            "kind",
            "from_status",
            "to_status",
            "reason",
            "details",
            "created_at",
        )


class IssueSerializer(serializers.ModelSerializer):
    events = IssueEventSerializer(many=True, read_only=True)
    recurring_requests = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True, allow_null=True)
    organization_code = serializers.CharField(source="organization.code", read_only=True)
    created_by_name = serializers.CharField(source="created_by.account.full_name", read_only=True)
    assignee_name = serializers.SerializerMethodField()
    related_request_reference = serializers.SerializerMethodField()
    related_request_title = serializers.SerializerMethodField()
    recurring_of_reference = serializers.SerializerMethodField()
    recurring_of_title = serializers.SerializerMethodField()
    confirmed_label = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_assignee_name(self, obj: Issue) -> str | None:
        return obj.assignee.account.full_name if obj.assignee else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_related_request_reference(self, obj: Issue) -> str | None:
        return obj.related_request.reference if obj.related_request else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_related_request_title(self, obj: Issue) -> str | None:
        return obj.related_request.title if obj.related_request else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_recurring_of_reference(self, obj: Issue) -> str | None:
        return obj.recurring_of.reference if obj.recurring_of else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_recurring_of_title(self, obj: Issue) -> str | None:
        return obj.recurring_of.title if obj.recurring_of else None

    @extend_schema_field(ConfirmedLabelSerializer(allow_null=True))
    def get_confirmed_label(self, obj: Issue) -> dict[str, int | str] | None:
        try:
            selection = obj.label_selection
        except IssueLabelSelection.DoesNotExist:
            return None
        return {"id": selection.label_id, "name": selection.label.name}

    @extend_schema_field(serializers.BooleanField)
    def get_is_overdue(self, obj: Issue) -> bool:
        return bool(
            obj.tentative_delivery_date
            and obj.tentative_delivery_date < timezone.localdate()
            and obj.actual_delivery_at is None
        )

    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
    def get_recurring_requests(self, obj: Issue) -> list[int]:
        rows = Issue.objects.filter(recurring_of=obj, organization=obj.organization)
        request = self.context.get("request")
        if request is None:
            rows = rows.exclude(status="DRAFT")
        else:
            rows = authorized_rows(request.user, rows, allow_datasoft=True)
            organization = portal_organization(request.user)
            if organization and organization.kind == OrganizationKind.DATASOFT:
                rows = rows.exclude(status="DRAFT")
            else:
                rows = rows.filter(~Q(status="DRAFT") | Q(created_by=request.user))
        return list(rows.values_list("pk", flat=True))

    class Meta:
        model = Issue
        fields = (
            "id",
            "reference",
            "title",
            "description",
            "acceptance_criteria",
            "request_type",
            "product",
            "product_name",
            "module",
            "priority",
            "environment",
            "steps_to_reproduce",
            "expected_result",
            "actual_result",
            "related_request",
            "related_request_reference",
            "related_request_title",
            "recurring_of",
            "recurring_of_reference",
            "recurring_of_title",
            "confirmed_label",
            "recurring_requests",
            "organization",
            "organization_name",
            "organization_code",
            "created_by_name",
            "assignee_name",
            "is_overdue",
            "status",
            "version",
            "assignee",
            "tentative_delivery_date",
            "tentative_delivery_later",
            "actual_delivery_at",
            "delivery_note",
            "deployment_details",
            "closed_at",
            "last_status_at",
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
    acceptance_criteria = serializers.CharField(required=False, allow_blank=True, max_length=20000)
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
    recurring_of = serializers.IntegerField(required=False, allow_null=True, min_value=1)

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
        if "recurring_of" in attrs and attrs["recurring_of"] is not None:
            user = self.context["request"].user
            rows = authorized_rows(user, Issue.objects.filter(status="CLOSED"))
            previous = rows.filter(pk=attrs["recurring_of"]).first()
            if previous is None or (
                issue and (previous.pk == issue.pk or previous.created_at >= issue.created_at)
            ):
                raise serializers.ValidationError({"recurring_of": "Invalid closed request."})
            attrs["recurring_of"] = previous
        return attrs


class MaskPreviewSerializer(serializers.Serializer):
    fields = serializers.DictField(
        child=serializers.CharField(max_length=20000, allow_blank=True), allow_empty=True
    )


class MaskPreviewResponseSerializer(serializers.Serializer):
    masked_fields = serializers.DictField(child=serializers.CharField(allow_blank=True))
    detected_types = serializers.ListField(child=serializers.CharField())


class IssueDraftEditSerializer(IssueWriteSerializer):
    version = serializers.IntegerField(min_value=1, required=False)


class TransitionVersionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    comment = serializers.CharField(
        required=False, allow_blank=True, max_length=5000, trim_whitespace=True
    )


class SubmitSerializer(serializers.Serializer):
    comment = serializers.CharField(
        required=False, allow_blank=True, max_length=5000, trim_whitespace=True
    )


class AcceptSerializer(TransitionVersionSerializer):
    tentative_delivery_date = serializers.DateField(required=False, allow_null=True)
    tentative_delivery_later = serializers.BooleanField(required=False, default=False)


class DateRevisionSerializer(AcceptSerializer):
    pass


class ReasonSerializer(TransitionVersionSerializer):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class AssignSerializer(TransitionVersionSerializer):
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class DeliverySerializer(TransitionVersionSerializer):
    delivery_note = serializers.CharField(trim_whitespace=True, allow_blank=False)
    deployment_details = serializers.CharField(trim_whitespace=True, allow_blank=False)


class WorkflowSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowSettings
        fields = ("reopen_days",)

    reopen_days = serializers.IntegerField(min_value=1, max_value=365)


class WorkflowAssigneeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="account.full_name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "full_name")
