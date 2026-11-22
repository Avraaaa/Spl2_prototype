from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.db import migrations


def _legacy_file_is_clean(attachment) -> bool:
    suffix = Path(attachment.original_name).suffix.lower()
    allowed = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".pdf",
        ".txt",
        ".log",
        ".csv",
        ".zip",
        ".docx",
        ".xlsx",
        ".pptx",
    }
    if suffix not in allowed or not attachment.file:
        return False
    if attachment.size <= 0 or attachment.size > 10 * 1024 * 1024:
        return False
    try:
        with attachment.file.open("rb") as stream:
            content = stream.read(10 * 1024 * 1024 + 1)
        if len(content) != attachment.size or len(content) > 10 * 1024 * 1024:
            return False
        if b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content:
            return False
        expected_content_type = {
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
        }[suffix]
        if attachment.content_type != expected_content_type:
            return False
        if suffix in {".txt", ".log", ".csv"}:
            content.decode("utf-8")
            return b"\x00" not in content
        if suffix in {".docx", ".xlsx", ".pptx"}:
            expected = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}[suffix]
            with ZipFile(BytesIO(content)) as archive:
                names = archive.namelist()
            return "[Content_Types].xml" in names and any(
                name.startswith(expected) for name in names
            )
        signatures = {
            ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
            ".jpg": content.startswith(b"\xff\xd8\xff"),
            ".jpeg": content.startswith(b"\xff\xd8\xff"),
            ".gif": content.startswith((b"GIF87a", b"GIF89a")),
            ".pdf": content.startswith(b"%PDF-"),
            ".zip": content.startswith((b"PK\x03\x04", b"PK\x05\x06")),
        }
        return signatures.get(suffix, False)
    except (BadZipFile, OSError, UnicodeDecodeError, ValueError):
        return False


def rescan_legacy_quarantined(apps, schema_editor):
    Attachment = apps.get_model("attachments", "Attachment")
    for attachment in Attachment.objects.filter(
        quarantine_status__in=["unscanned", "QUARANTINED"]
    ).iterator():
        if _legacy_file_is_clean(attachment):
            attachment.quarantine_status = "CLEAN"
            attachment.save(update_fields=["quarantine_status"])
        else:
            if attachment.file:
                attachment.file.delete(save=False)
                attachment.file = ""
            attachment.quarantine_status = "REJECTED"
            attachment.save(update_fields=["file", "quarantine_status"])


class Migration(migrations.Migration):
    dependencies = [("attachments", "0002_quarantine_default")]

    operations = [migrations.RunPython(rescan_legacy_quarantined, migrations.RunPython.noop)]
