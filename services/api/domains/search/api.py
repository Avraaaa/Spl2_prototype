from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.issues.api import visible_rows
from domains.tenants.selectors import get_authorized_object_or_404, portal_organization

from .models import Label, SuggestionFeedback
from .services import candidate_suggestions, label_suggestions


class SuggestionRequest(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=True)
    description = serializers.CharField(max_length=20000, allow_blank=True)


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
                "labels": label_suggestions(labels=labels, **data.validated_data),
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
        SuggestionFeedback.objects.create(actor=request.user, organization=organization, **fields)
        return Response({"recorded": True}, status=status.HTTP_201_CREATED)
