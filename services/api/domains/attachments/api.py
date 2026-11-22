from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from domains.accounts.services import is_datasoft_admin
from domains.issues.api import visible_rows
from domains.issues.services import mask_extracted_text, safe_original_text
from domains.tenants.models import OrganizationKind
from domains.tenants.selectors import get_authorized_object_or_404, portal_organization

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
        upload.seek(0)
        content = upload.read()
        upload.seek(0)
        try:
            content.decode("utf-8")
            valid = b"\x00" not in content
        except UnicodeDecodeError:
            valid = False
    elif suffix in OOXML_DIRECTORIES:
        valid = header.startswith(b"PK\x03\x04") and valid_ooxml(upload, suffix)
    else:
        valid = signatures[suffix]
    if not valid:
        raise ValidationError({"file": "Content does not match the allowed file type."})
    return MIME_TYPES[suffix]


def scan_attachment(contents: bytes) -> str:
    """Local pluggable scanner; deployments can replace this implementation."""
    rejected = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in contents
    return "REJECTED" if rejected else "CLEAN"


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
        organization = portal_organization(request.user)
        if organization and organization.kind == OrganizationKind.BANK:
            rows = rows.exclude(quarantine_status="REJECTED")
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
        upload.seek(0)
        contents = upload.read()
        upload.seek(0)
        comment = None
        if "comment" in data.validated_data:
            comment = get_authorized_object_or_404(
                request.user,
                issue.comments.all(),
                data.validated_data["comment"],
                organization_field="issue__organization",
                allow_datasoft=True,
            )
        quarantine_status = scan_attachment(contents)
        masked_text = None
        if Path(upload.name).suffix.lower() in {".txt", ".csv", ".log"}:
            try:
                extracted_text = contents.decode("utf-8")
            except UnicodeDecodeError as exc:
                # Recheck the bytes actually read for persistence. Do not allow
                # a changed or unusual upload stream to fail after validation.
                raise ValidationError(
                    {"file": "Text attachments must use UTF-8 encoding."}
                ) from exc
            masked_text = mask_extracted_text(extracted_text)
            contents = safe_original_text(extracted_text).encode("utf-8")
        # Validate and scan before creating either the row or stored file. The
        # transaction keeps metadata and quarantine state in step if persistence fails.
        attachment = Attachment(
            issue=issue,
            comment=comment,
            file=ContentFile(contents, name=Path(upload.name).name),
            original_name=Path(upload.name).name[:255],
            content_type=content_type,
            size=len(contents),
            uploaded_by=request.user,
            quarantine_status=quarantine_status,
        )
        try:
            with transaction.atomic():
                attachment.save()
                if quarantine_status == "REJECTED":
                    attachment.file.delete(save=True)
        except Exception:
            # Storage is not transaction-aware; remove an orphan if a later DB
            # operation failed after the storage backend accepted the content.
            if attachment.file:
                attachment.file.delete(save=False)
            raise
        if quarantine_status == "CLEAN" and masked_text is not None:
            from domains.search.services import _ml_embeddings

            try:
                _ml_embeddings([masked_text[:20_000]])
            except Exception:
                # Optional inference must not turn an otherwise valid upload into
                # an inconsistent failed request.
                pass
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
        if attachment.quarantine_status != "CLEAN":
            return Response({"detail": "Attachment is not available for download."}, status=423)
        is_text = Path(attachment.original_name).suffix.lower() in {".txt", ".csv", ".log"}
        may_view_original = is_datasoft_admin(request.user) or request.user.has_perm(
            "issues.view_unmasked_original"
        )
        if is_text and not may_view_original:
            original = attachment.file.open("rb").read().decode("utf-8")
            masked = mask_extracted_text(original).encode("utf-8")
            response = FileResponse(
                ContentFile(masked),
                as_attachment=True,
                filename=attachment.original_name,
                content_type=attachment.content_type,
            )
        else:
            if is_text:
                from domains.audit.services import append_record

                append_record(
                    organization=attachment.issue.organization,
                    actor=request.user,
                    action="ATTACHMENT_ORIGINAL_VIEWED",
                    payload={
                        "attachment_id": attachment.pk,
                        "issue_id": attachment.issue_id,
                        "request_method": request.method,
                        "request_path": request.path,
                    },
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
