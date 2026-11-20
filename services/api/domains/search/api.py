from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.services import is_datasoft_admin
from domains.issues.api import visible_rows
from domains.tenants.models import Organization
from domains.tenants.selectors import get_authorized_object_or_404, portal_organization

from .models import IssueLabelSelection, Label, SuggestionFeedback, TopicProposal
from .services import candidate_suggestions, create_topic_proposals, label_suggestions


class SuggestionRequest(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=True)
    description = serializers.CharField(max_length=20000, allow_blank=True)
    product = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    module = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class FeedbackRequest(serializers.Serializer):
    kind = serializers.CharField()
    accepted = serializers.BooleanField()
    issue = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    candidate_issue = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    label = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    score = serializers.FloatField(required=False, allow_null=True)

    def validate_kind(self, value):
        if value not in SuggestionFeedback.Kind.values:
            raise serializers.ValidationError("Unknown feedback kind.")
        return value


class SuggestionResponse(serializers.Serializer):
    duplicates = serializers.ListField(child=serializers.DictField())
    labels = serializers.ListField(child=serializers.DictField())
    available = serializers.BooleanField()


class FeedbackResponse(serializers.Serializer):
    recorded = serializers.BooleanField()


class EvaluationResponse(serializers.Serializer):
    duplicate_feedback = serializers.DictField()
    label_feedback = serializers.DictField()


class TopicProposalSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    organization = serializers.IntegerField()
    title = serializers.CharField()
    keywords = serializers.ListField(child=serializers.CharField())
    issue_ids = serializers.ListField(child=serializers.IntegerField())
    status = serializers.CharField()


class TopicProposalCreatedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class TopicReviewRequest(serializers.Serializer):
    status = serializers.ChoiceField(choices=("proposed", "accepted", "rejected"))


class TopicReviewResponse(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()


class LabelWrite(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    description = serializers.CharField(max_length=300, allow_blank=True, required=False)
    keywords = serializers.ListField(child=serializers.CharField(max_length=80), allow_empty=True)
    confidence_threshold = serializers.FloatField(min_value=0, max_value=1, required=False)
    is_active = serializers.BooleanField(required=False)


class LabelResponse(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField()
    keywords = serializers.ListField(child=serializers.CharField())
    confidence_threshold = serializers.FloatField()
    is_active = serializers.BooleanField()


class SuggestionsView(APIView):
    @extend_schema(request=SuggestionRequest, responses=SuggestionResponse, tags=["search"])
    def post(self, request):
        data = SuggestionRequest(data=request.data)
        data.is_valid(raise_exception=True)
        organization = portal_organization(request.user)
        if organization is None:
            return Response({"duplicates": [], "labels": [], "available": False})
        rows = visible_rows(request.user).select_related("organization")
        labels = Label.objects.filter(is_active=True)
        return Response(
            {
                "duplicates": candidate_suggestions(rows, **data.validated_data),
                "labels": label_suggestions(
                    title=data.validated_data["title"],
                    description=data.validated_data["description"],
                    labels=labels,
                    organization=organization,
                ),
                "available": True,
            }
        )


class SuggestionFeedbackView(APIView):
    @extend_schema(request=FeedbackRequest, responses={201: FeedbackResponse}, tags=["search"])
    def post(self, request):
        data = FeedbackRequest(data=request.data)
        data.is_valid(raise_exception=True)
        organization = portal_organization(request.user)
        if organization is None:
            raise ValidationError("Portal organization required.")
        fields = data.validated_data.copy()
        for key in ("issue", "candidate_issue"):
            if fields.get(key) is not None:
                fields[key] = get_authorized_object_or_404(
                    request.user, visible_rows(request.user), fields[key], allow_datasoft=True
                )
        if fields.get("label") is not None:
            fields["label"] = Label.objects.filter(pk=fields["label"], is_active=True).first()
            if fields["label"] is None:
                raise ValidationError({"label": "Unknown label."})
        if fields.get("kind") == SuggestionFeedback.Kind.LABEL and fields.get("issue"):
            issue = fields["issue"]
            label = fields.get("label")
            if fields["accepted"] and label is not None:
                IssueLabelSelection.objects.update_or_create(
                    issue=issue,
                    defaults={"label": label, "actor": request.user},
                )
            elif not fields["accepted"]:
                IssueLabelSelection.objects.filter(issue=issue).delete()
        SuggestionFeedback.objects.create(actor=request.user, organization=organization, **fields)
        return Response({"recorded": True}, status=status.HTTP_201_CREATED)


class TopicProposalView(APIView):
    @extend_schema(responses=TopicProposalSerializer(many=True), tags=["search"])
    def get(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        rows = TopicProposal.objects.select_related("organization").order_by("-created_at")[:100]
        return Response(
            [
                {
                    "id": row.id,
                    "organization": row.organization_id,
                    "title": row.title,
                    "keywords": row.keywords,
                    "issue_ids": row.issue_ids,
                    "status": row.status,
                }
                for row in rows
            ]
        )


class SuggestionEvaluationView(APIView):
    @extend_schema(responses=EvaluationResponse, tags=["search"])
    def get(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")

        def summary(kind: str) -> dict[str, float | int]:
            rows = SuggestionFeedback.objects.filter(kind=kind)
            total = rows.count()
            accepted = rows.filter(accepted=True).count()
            return {
                "total": total,
                "accepted": accepted,
                "rejected": total - accepted,
                "acceptance_rate": round(accepted / total, 4) if total else 0.0,
            }

        return Response(
            {
                "duplicate_feedback": summary(SuggestionFeedback.Kind.DUPLICATE),
                "label_feedback": summary(SuggestionFeedback.Kind.LABEL),
            }
        )

    @extend_schema(
        request=None, responses=TopicProposalCreatedSerializer(many=True), tags=["search"]
    )
    def post(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        staff_rows = visible_rows(request.user)
        proposals = []
        for organization_id in staff_rows.values_list("organization_id", flat=True).distinct():
            scoped = staff_rows.filter(organization_id=organization_id)
            if scoped.exists():
                bank = Organization.objects.get(pk=organization_id)
                proposals.extend(create_topic_proposals(organization=bank, rows=scoped))
        return Response(
            [{"id": proposal.id, "title": proposal.title} for proposal in proposals],
            status=status.HTTP_201_CREATED,
        )


class TopicProposalReviewView(APIView):
    @extend_schema(request=TopicReviewRequest, responses=TopicReviewResponse, tags=["search"])
    def patch(self, request, id):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        data = TopicReviewRequest(data=request.data)
        data.is_valid(raise_exception=True)
        status_value = data.validated_data["status"]
        proposal = TopicProposal.objects.filter(pk=id).first()
        if proposal is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        proposal.status = status_value
        proposal.reviewed_by = request.user
        proposal.save(update_fields=["status", "reviewed_by"])
        return Response({"id": proposal.id, "status": proposal.status})


def _label_payload(label: Label) -> dict:
    return {
        "id": label.id,
        "name": label.name,
        "description": label.description,
        "keywords": label.keywords,
        "confidence_threshold": label.confidence_threshold,
        "is_active": label.is_active,
    }


class LabelAdminView(APIView):
    @extend_schema(responses=LabelResponse(many=True), tags=["search"])
    def get(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        return Response([_label_payload(label) for label in Label.objects.all()])

    @extend_schema(request=LabelWrite, responses={201: LabelResponse}, tags=["search"])
    def post(self, request):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        data = LabelWrite(data=request.data)
        data.is_valid(raise_exception=True)
        label = Label.objects.create(**data.validated_data)
        return Response(_label_payload(label), status=status.HTTP_201_CREATED)


class LabelAdminDetailView(APIView):
    @extend_schema(request=LabelWrite, responses=LabelResponse, tags=["search"])
    def patch(self, request, id):
        if not is_datasoft_admin(request.user):
            raise PermissionDenied("DataSoft administrator role required.")
        label = Label.objects.filter(pk=id).first()
        if label is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = LabelWrite(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        for key, value in data.validated_data.items():
            setattr(label, key, value)
        label.save()
        return Response(_label_payload(label))
