from django.contrib.auth.models import User
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.models import Membership
from domains.accounts.roles import DATASOFT_ROLES
from domains.issues.api import visible_rows
from domains.issues.services import mask_sensitive
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import get_authorized_object_or_404, portal_organization

from .models import InternalNote, InternalTask


def require_staff(user):
    org = portal_organization(user)
    if (
        org is None
        or org.kind != OrganizationKind.DATASOFT
        or not Membership.objects.filter(
            user=user, organization=org, role__in=DATASOFT_ROLES
        ).exists()
    ):
        raise PermissionDenied("DataSoft staff role required.")


def task_rows(user) -> QuerySet[InternalTask]:
    require_staff(user)
    return InternalTask.objects.filter(issue__in=visible_rows(user)).select_related(
        "issue", "assignee__account"
    )


class TaskSerializer(serializers.ModelSerializer):
    issue_reference = serializers.CharField(source="issue.reference", read_only=True)
    assignee_name = serializers.CharField(
        source="assignee.account.full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = InternalTask
        fields = (
            "id",
            "issue",
            "issue_reference",
            "title",
            "assignee",
            "assignee_name",
            "status",
            "commit_url",
            "pull_request_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class TaskWriteSerializer(serializers.Serializer):
    issue = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200, allow_blank=False)
    assignee = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    status = serializers.ChoiceField(choices=InternalTask.Status.choices, required=False)
    commit_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    pull_request_url = serializers.URLField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        for key in ("commit_url", "pull_request_url"):
            if attrs.get(key) and not attrs[key].lower().startswith("https://"):
                raise serializers.ValidationError({key: "HTTPS URL required."})
        return attrs


class TaskEditSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, allow_blank=False, required=False)
    assignee = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    status = serializers.ChoiceField(choices=InternalTask.Status.choices, required=False)
    commit_url = serializers.URLField(max_length=500, required=False, allow_blank=True)
    pull_request_url = serializers.URLField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        return TaskWriteSerializer().validate(attrs)


def valid_assignee(pk):
    if pk is None:
        return None
    user = User.objects.filter(pk=pk, is_active=True).first()
    if user is None:
        raise ValidationError({"assignee": "Active DataSoft user required."})
    require_staff(user)
    return user


class TaskListView(APIView):
    @extend_schema(responses=TaskSerializer(many=True), tags=["tasks"])
    def get(self, request):
        rows = task_rows(request.user).order_by("created_at", "id")
        return Response(TaskSerializer(rows, many=True).data)

    @extend_schema(request=TaskWriteSerializer, responses={201: TaskSerializer}, tags=["tasks"])
    def post(self, request):
        require_staff(request.user)
        data = TaskWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data.copy()
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), fields.pop("issue"), allow_datasoft=True
        )
        fields["title"] = mask_sensitive(fields["title"])
        if len(fields["title"]) > 200:
            raise ValidationError({"title": "Masked title must be 200 characters or fewer."})
        if "assignee" in fields:
            fields["assignee"] = valid_assignee(fields["assignee"])
        task = InternalTask.objects.create(issue=issue, created_by=request.user, **fields)
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskDetailView(APIView):
    @extend_schema(responses=TaskSerializer, tags=["tasks"])
    def get(self, request, id):
        task = get_authorized_object_or_404(
            request.user,
            task_rows(request.user),
            id,
            organization_field="issue__organization",
            allow_datasoft=True,
        )
        return Response(TaskSerializer(task).data)

    @extend_schema(request=TaskEditSerializer, responses=TaskSerializer, tags=["tasks"])
    def patch(self, request, id):
        task = get_authorized_object_or_404(
            request.user,
            task_rows(request.user),
            id,
            organization_field="issue__organization",
            allow_datasoft=True,
        )
        data = TaskEditSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data.copy()
        if "assignee" in fields:
            fields["assignee"] = valid_assignee(fields["assignee"])
        if "title" in fields:
            fields["title"] = mask_sensitive(fields["title"])
            if len(fields["title"]) > 200:
                raise ValidationError({"title": "Masked title must be 200 characters or fewer."})
        for key, value in fields.items():
            setattr(task, key, value)
        task.save()
        return Response(TaskSerializer(task).data)


class NoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.account.full_name", read_only=True)

    class Meta:
        model = InternalNote
        fields = ("id", "issue", "task", "body", "author", "author_name", "created_at")
        read_only_fields = fields


class NoteWriteSerializer(serializers.Serializer):
    body = serializers.CharField(allow_blank=False, trim_whitespace=True)


class IssueNoteListView(APIView):
    @extend_schema(responses=NoteSerializer(many=True), tags=["internal"])
    def get(self, request, id):
        require_staff(request.user)
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), id, allow_datasoft=True
        )
        rows = InternalNote.objects.filter(issue=issue, task__isnull=True)
        rows = rows.select_related("author__account").order_by("created_at", "id")
        return Response(NoteSerializer(rows, many=True).data)

    @extend_schema(request=NoteWriteSerializer, responses={201: NoteSerializer}, tags=["internal"])
    def post(self, request, id):
        require_staff(request.user)
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), id, allow_datasoft=True
        )
        data = NoteWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        note = InternalNote.objects.create(
            issue=issue, body=mask_sensitive(data.validated_data["body"]), author=request.user
        )
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class TaskNoteListView(APIView):
    @extend_schema(responses=NoteSerializer(many=True), tags=["internal"])
    def get(self, request, id):
        task = get_authorized_object_or_404(
            request.user,
            task_rows(request.user),
            id,
            organization_field="issue__organization",
            allow_datasoft=True,
        )
        rows = InternalNote.objects.filter(task=task).select_related("author__account")
        return Response(NoteSerializer(rows.order_by("created_at", "id"), many=True).data)

    @extend_schema(request=NoteWriteSerializer, responses={201: NoteSerializer}, tags=["internal"])
    def post(self, request, id):
        task = get_authorized_object_or_404(
            request.user,
            task_rows(request.user),
            id,
            organization_field="issue__organization",
            allow_datasoft=True,
        )
        data = NoteWriteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        note = InternalNote.objects.create(
            issue=task.issue,
            task=task,
            body=mask_sensitive(data.validated_data["body"]),
            author=request.user,
        )
        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)
