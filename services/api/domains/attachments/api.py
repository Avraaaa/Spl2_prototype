from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.issues.api import visible_rows
from domains.tenants.selectors import get_authorized_object_or_404

from .models import Attachment

MAX_FILE_SIZE = 10 * 1024 * 1024
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".log": "text/plain",
    ".csv": "text/csv",
    ".zip": "application/zip",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
OOXML_DIRECTORIES = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}


def valid_ooxml(upload, suffix: str) -> bool:
    try:
        with ZipFile(upload) as archive:
            names = archive.namelist()
            return "[Content_Types].xml" in names and any(
                name.startswith(OOXML_DIRECTORIES[suffix]) for name in names
            )
    except (BadZipFile, OSError, ValueError):
        return False
    finally:
        upload.seek(0)


def checked_file(upload):
    suffix = Path(upload.name).suffix.lower()
    if suffix not in MIME_TYPES:
        raise ValidationError({"file": "File type is not allowed."})
    if upload.size > MAX_FILE_SIZE or upload.size == 0:
        raise ValidationError({"file": "File must be between 1 byte and 10 MB."})
    header = upload.read(8192)
    upload.seek(0)
    signatures = {
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".gif": header.startswith((b"GIF87a", b"GIF89a")),
        ".pdf": header.startswith(b"%PDF-"),
        ".zip": header.startswith((b"PK\x03\x04", b"PK\x05\x06")),
    }
    if suffix in (".txt", ".log", ".csv"):
        try:
            header.decode("utf-8")
            valid = b"\x00" not in header
        except UnicodeDecodeError:
            valid = False
    elif suffix in OOXML_DIRECTORIES:
        valid = header.startswith(b"PK\x03\x04") and valid_ooxml(upload, suffix)
    else:
        valid = signatures[suffix]
    if not valid:
        raise ValidationError({"file": "Content does not match the allowed file type."})
    return MIME_TYPES[suffix]


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = (
            "id",
            "issue",
            "comment",
            "original_name",
            "content_type",
            "size",
            "quarantine_status",
            "uploaded_by",
            "created_at",
        )
        read_only_fields = fields


class AttachmentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=True)
    comment = serializers.IntegerField(min_value=1, required=False)


class IssueAttachmentListView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses=AttachmentSerializer(many=True), tags=["attachments"])
    def get(self, request, id):
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), id, allow_datasoft=True
        )
        rows = Attachment.objects.filter(issue=issue).order_by("created_at", "id")
        return Response(AttachmentSerializer(rows, many=True).data)

    @extend_schema(
        request=AttachmentUploadSerializer,
        responses={201: AttachmentSerializer},
        tags=["attachments"],
    )
    def post(self, request, id):
        issue = get_authorized_object_or_404(
            request.user, visible_rows(request.user), id, allow_datasoft=True
        )
        data = AttachmentUploadSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        upload = data.validated_data["file"]
        content_type = checked_file(upload)
        comment = None
        if "comment" in data.validated_data:
            comment = get_authorized_object_or_404(
                request.user,
                issue.comments.all(),
                data.validated_data["comment"],
                organization_field="issue__organization",
                allow_datasoft=True,
            )
        attachment = Attachment.objects.create(
            issue=issue,
            comment=comment,
            file=upload,
            original_name=Path(upload.name).name[:255],
            content_type=content_type,
            size=upload.size,
            uploaded_by=request.user,
        )
        return Response(AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


class AttachmentDownloadView(APIView):
    @extend_schema(
        responses={(200, "application/octet-stream"): OpenApiTypes.BINARY}, tags=["attachments"]
    )
    def get(self, request, id):
        rows = Attachment.objects.filter(issue__in=visible_rows(request.user))
        attachment = get_authorized_object_or_404(
            request.user,
            rows,
            id,
            organization_field="issue__organization",
            allow_datasoft=True,
        )
        response = FileResponse(
            attachment.file.open("rb"),
            as_attachment=not attachment.content_type.startswith("image/"),
            filename=attachment.original_name,
            content_type=attachment.content_type,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
