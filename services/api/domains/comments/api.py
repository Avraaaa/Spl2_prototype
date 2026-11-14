from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.models import Membership
from domains.accounts.roles import BANK_ROLES, DATASOFT_ROLES
from domains.issues.api import visible_rows
from domains.issues.models import IssueStatus
from domains.issues.services import mask_sensitive
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import get_authorized_object_or_404, portal_organization

from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.account.full_name", read_only=True)

    class Meta:
        model = Comment
        fields = ("id", "issue", "author", "author_name", "body", "created_at")
        read_only_fields = fields


class CommentWriteSerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=False, trim_whitespace=True)


def comment_issue(user, id):
    return get_authorized_object_or_404(user, visible_rows(user), id, allow_datasoft=True)


class CommentListView(APIView):
    @extend_schema(responses=CommentSerializer(many=True), tags=["comments"])
    def get(self, request, id):
        issue = comment_issue(request.user, id)
        rows = Comment.objects.filter(issue=issue).select_related("author__account")
        return Response(CommentSerializer(rows.order_by("created_at", "id"), many=True).data)

    @extend_schema(
        request=CommentWriteSerializer, responses={201: CommentSerializer}, tags=["comments"]
    )
    def post(self, request, id):
        issue = comment_issue(request.user, id)
        organization = portal_organization(request.user)
        roles = BANK_ROLES if organization.kind == OrganizationKind.BANK else DATASOFT_ROLES
        if not Membership.objects.filter(
            user=request.user, organization=organization, role__in=roles
        ).exists():
            raise PermissionDenied("Comment role required.")
        if issue.status == IssueStatus.DRAFT and issue.created_by_id != request.user.pk:
            raise PermissionDenied("Only the creator may comment on a draft.")
        data = CommentWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        body = mask_sensitive(data.validated_data["body"])
        if not body.strip():
            raise ValidationError({"body": "A comment is required."})
        comment = Comment.objects.create(issue=issue, author=request.user, body=body)
        # TODO(P3-T2): enqueue comment notification after the outbox domain is available.
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
