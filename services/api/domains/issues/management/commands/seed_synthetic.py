"""Build a deterministic, clearly synthetic feature-evaluation dataset."""

import json
import random
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
from domains.search.progress import ProgressReporter
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
        parser.add_argument("--count", type=int)
        parser.add_argument("--seed", type=int, default=20261122)
        parser.add_argument("--manifest", default="seed/p7t9_synthetic_manifest.json")
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--allow", action="store_true")
        parser.add_argument("--skip-embeddings", action="store_true")
        parser.add_argument("--embed-locally", action="store_true")
        parser.add_argument("--progress-every", type=int, default=25)
        parser.add_argument("--log-file")
        parser.add_argument("--corpus", choices=("realistic", "everyday", "all"), default="all")

    def handle(self, *args, **options):
        configured_hosts = set(settings.ALLOWED_HOSTS)
        local_hosts = {"localhost", "127.0.0.1", "[::1]"}
        if not settings.DEBUG and configured_hosts - local_hosts:
            raise CommandError("seed_synthetic is disabled for non-local deployments.")
        if not settings.DEBUG and not options["allow"]:
            raise CommandError("seed_synthetic requires DEBUG or the explicit --allow flag.")
        count = options["count"]
        if count is None:
            count = self._default_count(options["corpus"])
        if options["progress_every"] < 1:
            raise CommandError("--progress-every must be positive")
        if count < 2 or count > 2000:
            raise CommandError("--count must be between 2 and 2000.")
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
            manifest = self._manifest(existing, options["seed"], options["corpus"])
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            if not options["skip_embeddings"]:
                self._backfill_embeddings(
                    options["embed_locally"], options["progress_every"], options["log_file"]
                )
            self.stdout.write(f"Synthetic dataset already contains {len(existing)} requests.")
            return

        with transaction.atomic():
            rows = self._generate(
                count,
                options["seed"],
                options["progress_every"],
                options["log_file"],
                options["corpus"],
            )
            manifest = self._manifest(rows, options["seed"], options["corpus"])
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if not options["skip_embeddings"]:
            self._backfill_embeddings(
                options["embed_locally"], options["progress_every"], options["log_file"]
            )
        self.stdout.write(f"Generated {len(rows)} synthetic requests; manifest: {manifest_path}")

    def _backfill_embeddings(self, embed_locally=False, progress_every=25, log_file=None):
        call_command(
            "backfill_embeddings",
            embed_locally=embed_locally,
            progress_every=progress_every,
            log_file=log_file,
            verbosity=0,
        )
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

    def _generate(self, count, seed, progress_every=25, log_file=None, corpus_kind="all"):
        banks, officers, staff = self._actors()
        corpus, sensitive_cases = self._corpus(corpus_kind)
        random.Random(seed).shuffle(corpus)
        corpus = [corpus[index % len(corpus)] for index in range(count)]
        # Retain the legacy fixture product used by existing synthetic reset tests.
        Product.objects.get_or_create(name="Synthetic Feature Lab")
        generated = []
        epoch = timezone.now()
        progress = ProgressReporter("generating requests", count, progress_every, log_file)
        progress.start()
        emerging_start = max(0, count - max(3, count // 10))
        for index in range(count):
            source = corpus[index]
            # Keep every variant of one incident, including its hard negatives,
            # in the same tenant. Stable group hashing makes the split seedable.
            code = "NWD" if sum(source["group"].encode("utf-8")) % 2 == 0 else "RSD"
            officer = officers[code]
            label_name = source["label"]
            title = source["request"]["title"]
            description = source["request"]["description"]
            request_type = source["request_type"]
            legacy_evidence = source["corpus"] == "synthetic_corpus"
            if sensitive_cases and index % 5 == 0:
                sensitive = sensitive_cases[index % len(sensitive_cases)]
                description = f"{description}\n{sensitive['text']}"
            product, _ = Product.objects.get_or_create(name=source["product"])
            module, _ = Module.objects.get_or_create(product=product, name=source["module"])
            label = None
            if label_name:
                label, _ = Label.objects.get_or_create(
                    name=label_name,
                    defaults={
                        "description": f"Synthetic {label_name.lower()} issues",
                        "keywords": [],
                    },
                )
            issue = services.create_draft(
                officer,
                {
                    "title": title,
                    "description": description,
                    "request_type": request_type.upper(),
                    "product": product,
                    "module": module,
                    "priority": source["request"]["priority"].upper(),
                    "environment": source["request"].get(
                        "environment", "Synthetic sandbox only" if legacy_evidence else ""
                    ),
                    "steps_to_reproduce": source["request"].get(
                        "steps_to_reproduce",
                        "Use synthetic account and inspect test screen." if legacy_evidence else "",
                    ),
                    "expected_result": source["request"].get(
                        "expected_result",
                        "Synthetic request completes." if legacy_evidence else "",
                    ),
                    "actual_result": source["request"].get(
                        "actual_result",
                        "Synthetic test behavior is reproduced." if legacy_evidence else "",
                    ),
                },
            )
            key = f"p7t9-{seed}-{index:04d}"
            Issue.objects.filter(pk=issue.pk).update(
                is_synthetic=True,
                synthetic_key=key,
                created_at=epoch
                - timedelta(
                    days=(
                        index - emerging_start if index >= emerging_start else 365 - (index % 365)
                    )
                ),
            )
            issue.refresh_from_db()
            target = STATUSES[index % len(STATUSES)]
            if target != "DRAFT":
                issue = services.submit(officer, issue, comment="Synthetic dataset submission.")
            issue = self._advance(issue, target, staff, banks[code])
            if label and not source["hard_negative"] and index < emerging_start:
                IssueLabelSelection.objects.update_or_create(
                    issue=issue,
                    defaults={"label": label, "actor": staff},
                )
            if index % 17 == 0:
                create_comment(issue=issue, author=officer, body="Synthetic comment; OTP 315624.")
            generated.append(issue)
            progress.item(index + 1)
        progress.finish()
        return generated

    @staticmethod
    def _default_count(corpus_kind):
        return len(Command._corpus(corpus_kind)[0])

    @staticmethod
    def _corpus(corpus_kind="all"):
        roots = []
        if corpus_kind in {"realistic", "all"}:
            roots.append(Path.cwd() / "seed" / "synthetic_corpus")
        if corpus_kind in {"everyday", "all"}:
            roots.append(Path.cwd() / "seed" / "synthetic_corpus_everyday")
        try:
            documents = [
                (json.loads(path.read_text(encoding="utf-8")), root.name)
                for root in roots
                for path in sorted(root.glob("*.json"))
            ]
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot read synthetic request corpus: {exc}") from exc
        if not documents:
            raise CommandError("No synthetic request corpus files found.")
        records = []
        sensitive_cases = []
        for document, corpus_name in documents:
            for group in document.get("groups", []):
                records.extend(
                    {
                        "group": group["group_id"],
                        "label": group.get("label"),
                        "product": group["product"],
                        "module": group["module"],
                        "request": request,
                        "request_type": request.get("request_type", "bug"),
                        "corpus": corpus_name,
                        "hard_negative": False,
                        "emerging_topic": group.get("label") is None,
                    }
                    for request in group["requests"]
                )
            records.extend(
                {
                    "group": item["near_group"],
                    "label": item.get("label"),
                    "product": item["product"],
                    "module": item["module"],
                    "request": item,
                    "request_type": item.get("request_type", "bug"),
                    "corpus": corpus_name,
                    "hard_negative": True,
                    "emerging_topic": False,
                }
                for item in document.get("hard_negatives", [])
            )
            sensitive_cases.extend(document.get("sensitive_cases", []))
        if not records:
            raise CommandError("Synthetic corpus is missing requests.")
        return records, sensitive_cases

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
    def _manifest(rows, seed, corpus_kind="all"):
        corpus, sensitive_cases = Command._corpus(corpus_kind)
        random.Random(seed).shuffle(corpus)
        group_rows = {}
        expected_masks = []
        must_not_mask = []
        records = []
        for index, issue in enumerate(rows):
            emerging_start = max(0, len(rows) - max(3, len(rows) // 10))
            source = corpus[index % len(corpus)]
            emerging = source.get("emerging_topic", False) or index >= emerging_start
            group = source["group"]
            variant = source["request"]["variant"]
            group_rows.setdefault(f"{issue.organization.code}:{group}", []).append(issue.pk)
            categories = []
            sensitive = None
            if sensitive_cases and index % 5 == 0:
                sensitive = sensitive_cases[index % len(sensitive_cases)]
                categories = sorted({item["type"].lower() for item in sensitive["expected"]})
            if categories:
                expected_masks.append({"issue_id": issue.pk, "categories": categories})
            if sensitive:
                must_not_mask.append(
                    {
                        "issue_id": issue.pk,
                        "tokens": sensitive.get("must_not_mask", []),
                    }
                )
            expected_label = None if source["hard_negative"] or emerging else source["label"]
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
                    "label": source["label"],
                    "mask_categories": categories,
                    "must_not_mask": sensitive.get("must_not_mask", []) if sensitive else [],
                    "hard_negative": source["hard_negative"],
                    "near_group": source["group"] if source["hard_negative"] else None,
                    "emerging_topic_sample": emerging,
                    "request_type": source["request_type"],
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
