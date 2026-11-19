import hashlib
import json

from django.db import transaction
from django.utils import timezone

from .models import AuditAnchor, AuditRecord


def _canonical(
    *,
    organization_id: int,
    sequence: int,
    actor_id: int,
    action: str,
    payload: dict,
    previous_hash: str,
    created_at: str,
) -> bytes:
    return json.dumps(
        {
            "organization_id": organization_id,
            "sequence": sequence,
            "actor_id": actor_id,
            "action": action,
            "payload": payload,
            "previous_hash": previous_hash,
            "created_at": created_at,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


@transaction.atomic
def append_record(*, organization, actor, action: str, payload: dict) -> AuditRecord:
    previous = (
        AuditRecord.objects.select_for_update()
        .filter(organization=organization)
        .order_by("-sequence")
        .first()
    )
    sequence = (previous.sequence + 1) if previous else 1
    previous_hash = previous.record_hash if previous else ""
    record = AuditRecord(
        organization=organization,
        sequence=sequence,
        actor=actor,
        action=action,
        payload=payload,
        previous_hash=previous_hash,
        record_hash="pending",
    )
    record.created_at = timezone.now()
    record.record_hash = hashlib.sha256(
        _canonical(
            organization_id=organization.pk,
            sequence=sequence,
            actor_id=actor.pk,
            action=action,
            payload=payload,
            previous_hash=previous_hash,
            created_at=record.created_at.isoformat(),
        )
    ).hexdigest()
    record.save(force_insert=True)
    return record


def verify_chain(organization) -> dict:
    expected_previous = ""
    expected_sequence = 1
    for record in AuditRecord.objects.filter(organization=organization).order_by("sequence"):
        if record.sequence != expected_sequence or record.previous_hash != expected_previous:
            return {"valid": False, "first_invalid_sequence": record.sequence}
        calculated = hashlib.sha256(
            _canonical(
                organization_id=organization.pk,
                sequence=record.sequence,
                actor_id=record.actor_id,
                action=record.action,
                payload=record.payload,
                previous_hash=record.previous_hash,
                created_at=record.created_at.isoformat(),
            )
        ).hexdigest()
        if calculated != record.record_hash:
            return {"valid": False, "first_invalid_sequence": record.sequence}
        expected_previous = record.record_hash
        expected_sequence += 1
    for anchor in AuditAnchor.objects.filter(organization=organization).order_by("sequence"):
        anchor_record = AuditRecord.objects.filter(
            organization=organization, sequence=anchor.sequence, record_hash=anchor.record_hash
        ).first()
        if anchor_record is None:
            return {"valid": False, "first_invalid_sequence": anchor.sequence}
    return {"valid": True, "first_invalid_sequence": None}


@transaction.atomic
def anchor_head(*, organization, actor) -> AuditAnchor:
    head = AuditRecord.objects.filter(organization=organization).order_by("-sequence").first()
    if head is None:
        raise ValueError("Cannot anchor an empty audit chain")
    return AuditAnchor.objects.create(
        organization=organization,
        sequence=head.sequence,
        record_hash=head.record_hash,
    )
