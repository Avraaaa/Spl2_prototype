"""Build a deterministic, clearly synthetic feature-evaluation dataset."""

import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from domains.accounts.roles import Role
from domains.comments.services import create_comment
from domains.issues import services, workflow
from domains.issues.models import Issue, IssueEvent
from domains.products.models import Module, Product
from domains.search.models import EmbeddingJob, IssueLabelSelection, Label
from domains.tenants.models import Organization

VARIANTS = ("English", "Bangla", "Banglish", "Code-switched", "Typo")
GROUPS = (
    (
        "session-timeout",
        "Authentication",
        "session token refresh",
        "session token expires before refresh",
    ),
    ("ledger-delay", "Transaction", "ledger posting delay", "ledger transaction stays pending"),
    ("report-slow", "Performance", "monthly report slow", "monthly report takes too long"),
    ("schema-mismatch", "Database", "schema migration mismatch", "database schema is not migrated"),
    (
        "button-layout",
        "User Interface",
        "submit button layout",
        "submit button is hidden on small screen",
    ),
)
VARIANT_TEXT = {
    "English": "{a}; {b}. Synthetic reproduction in sandbox.",
    "Bangla": "{a} সমস্যা হচ্ছে; {b}। কৃত্রিম পরীক্ষার তথ্য।",
    "Banglish": "{a} hocche na, {b} pending thake. Synthetic test.",
    "Code-switched": "{a} issue: {b}; please check sandbox logs.",
    "Typo": "{a} probelm; {b} takse too long. Synthtic repro.",
}
BANGLA_TEXT = {
    "session-timeout": "সেশন টোকেন সময়মতো রিফ্রেশ হচ্ছে না; মেয়াদ শেষ হওয়ার আগে টোকেন নবায়ন দরকার।",
    "ledger-delay": "লেনদেন লেজারে আটকে থাকে; পরীক্ষার লেনদেন সম্পন্ন হয় না।",
    "report-slow": "মাসিক প্রতিবেদন তৈরি হতে অনেক সময় লাগে; পরীক্ষার ফল ধীর।",
    "schema-mismatch": "ডাটাবেসের স্কিমা হালনাগাদ নয়; পরীক্ষার কলাম পাওয়া যাচ্ছে না।",
    "button-layout": "ছোট পর্দায় জমা দেওয়ার বোতাম দেখা যায় না; পরীক্ষার ফর্ম ব্যবহার করা যায় না।",
    "emerging-passkey-traces": "পাসকি নিরীক্ষার ট্রেস অসম্পূর্ণ; কৃত্রিম পরিচয় যাচাইয়ের তথ্য ভাগ হয়ে গেছে।",
}
LABEL_KEYWORDS = {
    "Authentication": ["session", "token", "login", "refresh"],
    "Transaction": ["ledger", "posting", "transaction", "pending"],
    "Performance": ["report", "slow", "latency", "timeout"],
    "Database": ["schema", "migration", "database", "column"],
    "User Interface": ["button", "screen", "layout", "submit"],
}
STATUSES = [
    "DRAFT",
    "SUBMITTED",
    "REJECTED",
    "ACCEPTED",
    "PENDING",
    "IN_PROGRESS",
    "AWAITING_VERIFICATION",
    "VERIFIED",
    "CLOSED",
    "REOPENED",
]


class Command(BaseCommand):
    help = "Create deterministic synthetic requests for live feature comparison."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=400)
        parser.add_argument("--seed", type=int, default=20261122)
        parser.add_argument("--manifest", default="seed/p7t9_synthetic_manifest.json")
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--allow", action="store_true")
        parser.add_argument("--skip-embeddings", action="store_true")

    def handle(self, *args, **options):
        configured_hosts = set(settings.ALLOWED_HOSTS)
        local_hosts = {"localhost", "127.0.0.1", "[::1]"}
        if not settings.DEBUG and configured_hosts - local_hosts:
            raise CommandError("seed_synthetic is disabled for non-local deployments.")
        if not settings.DEBUG and not options["allow"]:
            raise CommandError("seed_synthetic requires DEBUG or the explicit --allow flag.")
        count = options["count"]
        if count < 2 or count > 500:
            raise CommandError("--count must be between 2 and 500.")
        manifest_path = Path(options["manifest"])
        if not manifest_path.is_absolute():
            manifest_path = Path.cwd() / manifest_path
        if options["reset"]:
            self._reset()
            self.stdout.write(
                "Removed tagged synthetic requests and their generated feature records."
            )
            return
        existing = list(Issue.objects.filter(is_synthetic=True).order_by("synthetic_key"))
        if existing:
            expected_keys = [f"p7t9-{options['seed']}-{index:04d}" for index in range(count)]
            if [row.synthetic_key for row in existing] != expected_keys:
                raise CommandError("A different synthetic dataset exists; run with --reset first.")
            manifest = self._manifest(existing, options["seed"])
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            if not options["skip_embeddings"]:
                self._backfill_embeddings()
            self.stdout.write(f"Synthetic dataset already contains {len(existing)} requests.")
            return

        with transaction.atomic():
            rows = self._generate(count, options["seed"])
            manifest = self._manifest(rows, options["seed"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if not options["skip_embeddings"]:
            self._backfill_embeddings()
        self.stdout.write(f"Generated {len(rows)} synthetic requests; manifest: {manifest_path}")

    def _backfill_embeddings(self):
        call_command("backfill_embeddings", verbosity=0)
        pending = EmbeddingJob.objects.filter(issue__is_synthetic=True, status="pending").count()
        if pending:
            self.stdout.write(
                f"Embedding backfill skipped or incomplete; {pending} synthetic jobs remain pending."
            )

    @staticmethod
    def _actors():
        banks = {
            code: Organization.objects.filter(code=code, kind="BANK").first()
            for code in ("NWD", "RSD")
        }
        if any(bank is None for bank in banks.values()):
            raise CommandError("Run seed_demo first; both synthetic demo banks are required.")
        officers = {}
        for code, bank in banks.items():
            officers[code] = (
                User.objects.filter(
                    account__organization=bank, memberships__role=Role.ISSUE_OFFICER
                )
                .distinct()
                .first()
            )
            if officers[code] is None:
                raise CommandError(f"No synthetic Issue Officer is available for {code}.")
        staff = (
            User.objects.filter(memberships__role__in=[Role.SUPPORT_AGENT, Role.DATASOFT_ADMIN])
            .distinct()
            .first()
        )
        if staff is None:
            raise CommandError("Run seed_demo first; a synthetic DataSoft operator is required.")
        return banks, officers, staff

    def _generate(self, count, seed):
        banks, officers, staff = self._actors()
        product, _ = Product.objects.get_or_create(name="Synthetic Feature Lab")
        module, _ = Module.objects.get_or_create(product=product, name="Synthetic Request Module")
        labels = {
            name: Label.objects.get_or_create(
                name=name,
                defaults={"description": f"Synthetic {name.lower()} issues", "keywords": keywords},
            )[0]
            for name, keywords in LABEL_KEYWORDS.items()
        }
        generated = []
        epoch = timezone.now()
        for index in range(count):
            code = "NWD" if index % 2 == 0 else "RSD"
            officer = officers[code]
            emerging_start = max(0, count - max(3, count // 10))
            emerging = index >= emerging_start
            group_index = (index // 5) % len(GROUPS)
            group, label_name, phrase_a, phrase_b = GROUPS[group_index]
            if emerging:
                group = "emerging-passkey-traces"
                phrase_a = "passkey audit trace"
                phrase_b = "synthetic credential handoff telemetry is fragmented"
            variant = VARIANTS[index % len(VARIANTS)]
            title = f"Synthetic {phrase_a} case {index:04d}"
            description = (
                BANGLA_TEXT[group]
                if variant == "Bangla"
                else VARIANT_TEXT[variant].format(a=phrase_a, b=phrase_b)
            )
            category = index % 25
            if category == 0:
                description += " OTP 583104; contact demo.person@example.test."
            elif category == 1:
                description += " Test card 4111111111111111 and account 123456789012."
            elif category == 2:
                description += " NID 1987654321098; phone 01712345678."
            elif category == 3:
                description += " Txn ID 778899001122; version 2.4 and error E-4012 are lookalikes."
            issue = services.create_draft(
                officer,
                {
                    "title": title,
                    "description": description,
                    "request_type": "BUG",
                    "product": product,
                    "module": module,
                    "priority": "MEDIUM",
                    "environment": "Synthetic sandbox only",
                    "steps_to_reproduce": "Use synthetic account and inspect test screen.",
                    "expected_result": "Synthetic request completes.",
                    "actual_result": "Synthetic test behavior is reproduced.",
                },
            )
            key = f"p7t9-{seed}-{index:04d}"
            Issue.objects.filter(pk=issue.pk).update(
                is_synthetic=True,
                synthetic_key=key,
                created_at=epoch
                - timedelta(days=index - emerging_start if emerging else 365 - (index % 365)),
            )
            issue.refresh_from_db()
            target = STATUSES[index % len(STATUSES)]
            if target != "DRAFT":
                issue = services.submit(officer, issue, comment="Synthetic dataset submission.")
            issue = self._advance(issue, target, staff, banks[code])
            if not emerging:
                IssueLabelSelection.objects.update_or_create(
                    issue=issue,
                    defaults={"label": labels[label_name], "actor": staff},
                )
            if index % 17 == 0:
                create_comment(issue=issue, author=officer, body="Synthetic comment; OTP 315624.")
            generated.append(issue)
        return generated

    @staticmethod
    def _advance(issue, target, staff, bank):
        index = int(issue.synthetic_key.rsplit("-", maxsplit=1)[-1])
        delivery = timezone.localdate() + timedelta(days=(-5 if index % 10 == 0 else 10))
        issue.refresh_from_db()
        if target == "DRAFT":
            return issue
        if target == "SUBMITTED":
            return issue

        if target == "REJECTED":
            issue = workflow.reject(
                staff, issue.pk, issue.version, reason="Synthetic rejection reason."
            )
            issue.refresh_from_db()
            return issue

        issue = workflow.accept(staff, issue.pk, issue.version, tentative_delivery_date=delivery)
        issue.refresh_from_db()
        if target == "ACCEPTED":
            return issue
        issue = workflow.assign(staff, issue.pk, issue.version, assignee=staff)
        issue.refresh_from_db()
        if target == "PENDING":
            return issue
        # The workflow service only permits start from PENDING. Keep this
        # guard explicit so later lifecycle additions cannot accidentally
        # issue an invalid transition from an intermediate status.
        if issue.status != "PENDING":
            raise CommandError(
                f"Cannot advance synthetic request {issue.synthetic_key} to {target} "
                f"from {issue.status}; expected PENDING before start."
            )
        issue = workflow.start(staff, issue.pk, issue.version)
        issue.refresh_from_db()

        # Include failed-verification samples, then continue from the status the
        # workflow actually produced (IN_PROGRESS); never start a second time.
        if index % 7 == 0:
            verifier = bank.memberships.filter(role=Role.ISSUE_VERIFIER).first()
            if verifier:
                issue = workflow.deliver(
                    staff,
                    issue.pk,
                    issue.version,
                    delivery_note="Synthetic delivery note.",
                    deployment_details="Synthetic build 2.4.",
                )
                issue.refresh_from_db()
                issue = workflow.fail_verification(
                    verifier.user,
                    issue.pk,
                    issue.version,
                    reason="Synthetic verification failure.",
                )
                issue.refresh_from_db()
                # fail_verification returns IN_PROGRESS. Delivery is the next
                # valid transition; never call start after a failed verification.
                if target == "IN_PROGRESS":
                    return issue
        if target == "IN_PROGRESS":
            return issue
        issue = workflow.deliver(
            staff,
            issue.pk,
            issue.version,
            delivery_note="Synthetic delivery note.",
            deployment_details="Synthetic build 2.4.",
        )
        issue.refresh_from_db()
        if target == "AWAITING_VERIFICATION":
            return issue
        verifier = bank.memberships.filter(role=Role.ISSUE_VERIFIER).first()
        if verifier is None:
            raise CommandError(f"No synthetic verifier is available for {bank.code}.")
        issue = workflow.verify(verifier.user, issue.pk, issue.version)
        issue.refresh_from_db()
        if target == "VERIFIED":
            return issue
        issue = workflow.close(staff, issue.pk, issue.version)
        issue.refresh_from_db()
        if target == "CLOSED":
            return issue
        # Reopening is a normal named workflow transition; final status is in progress.
        issue = workflow.reopen(
            staff, issue.pk, issue.version, reason="Synthetic reopening scenario."
        )
        issue.refresh_from_db()
        return issue

    @staticmethod
    def _manifest(rows, seed):
        group_rows = {}
        expected_masks = []
        must_not_mask = []
        records = []
        for index, issue in enumerate(rows):
            emerging_start = max(0, len(rows) - max(3, len(rows) // 10))
            emerging = index >= emerging_start
            group = "emerging-passkey-traces" if emerging else GROUPS[(index // 5) % len(GROUPS)][0]
            variant = VARIANTS[index % len(VARIANTS)]
            group_rows.setdefault(f"{issue.organization.code}:{group}", []).append(issue.pk)
            categories = {
                0: ["otp", "email"],
                1: ["card", "account"],
                2: ["nid", "phone"],
                3: [],
            }.get(index % 25, [])
            if categories:
                expected_masks.append({"issue_id": issue.pk, "categories": categories})
            if index % 25 == 3:
                must_not_mask.append(
                    {
                        "issue_id": issue.pk,
                        "tokens": ["Txn ID 778899001122", "error_code", "version"],
                    }
                )
            expected_label = None if emerging else GROUPS[(index // 5) % len(GROUPS)][1]
            records.append(
                {
                    "issue_id": issue.pk,
                    "key": issue.synthetic_key,
                    "tenant": issue.organization.code,
                    "language": variant,
                    "group": group,
                    "topic": group,
                    "status": issue.status,
                    "workflow_events": list(issue.events.values_list("kind", flat=True)),
                    "expected_label": expected_label,
                    "mask_categories": categories,
                }
            )
        return {
            "revision": f"p7t9-seed-{seed}",
            "seed": seed,
            "synthetic_only": True,
            "groups": group_rows,
            "records": records,
            "expected_masks": expected_masks,
            "must_not_mask": must_not_mask,
        }

    @staticmethod
    @transaction.atomic
    def _reset():
        ids = list(Issue.objects.filter(is_synthetic=True).values_list("pk", flat=True))
        if not ids:
            return
        # Remove only generated history and children before the tagged issue rows.
        Issue.objects.filter(pk__in=ids).update(related_request=None, recurring_of=None)
        IssueEvent.objects.filter(issue_id__in=ids).delete()
        from domains.comments.models import Comment
        from domains.notifications.models import Notification, OutboxMessage
        from domains.search.models import DuplicateReview, SuggestionFeedback

        Notification.objects.filter(issue_id__in=ids).delete()
        OutboxMessage.objects.filter(payload__issue_id__in=ids).delete()
        Comment.objects.filter(issue_id__in=ids).delete()
        DuplicateReview.objects.filter(Q(issue_id__in=ids) | Q(candidate_issue_id__in=ids)).delete()
        SuggestionFeedback.objects.filter(
            Q(issue_id__in=ids) | Q(candidate_issue_id__in=ids)
        ).delete()
        IssueLabelSelection.objects.filter(issue_id__in=ids).delete()
        Issue.objects.filter(pk__in=ids).delete()
