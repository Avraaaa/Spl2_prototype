"""P7-T13 everyday request corpus loading and request-type reporting."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from domains.accounts import services as account_services
from domains.accounts.roles import Role
from domains.issues.models import Issue
from domains.tenants.models import Organization, OrganizationKind

ROOT = Path(__file__).parents[3]


class P7T13EverydayCorpusTests(TestCase):
    def setUp(self):
        datasoft = account_services.ensure_datasoft_organization()
        for code, name in (("NWD", "Northwind Demo Bank"), ("RSD", "Riverstone Demo Bank")):
            bank, _ = Organization.objects.get_or_create(
                code=code,
                defaults={"name": name, "kind": OrganizationKind.BANK},
            )
            account_services.create_user_unchecked(
                organization=bank,
                username=f"p7t13_{code.lower()}_officer",
                email=f"p7t13_{code.lower()}@example.test",
                full_name="Synthetic Issue Officer",
                roles=[Role.ISSUE_OFFICER],
            )
            account_services.create_user_unchecked(
                organization=bank,
                username=f"p7t13_{code.lower()}_verifier",
                email=f"p7t13_{code.lower()}_verifier@example.test",
                full_name="Synthetic Issue Verifier",
                roles=[Role.ISSUE_VERIFIER],
            )
        account_services.create_user_unchecked(
            organization=datasoft,
            username="p7t13_admin",
            email="p7t13_admin@example.test",
            full_name="Synthetic DataSoft Admin",
            roles=[Role.DATASOFT_ADMIN],
        )

    def test_everyday_corpus_shape_and_bug_evidence(self):
        documents = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((ROOT / "seed/synthetic_corpus_everyday").glob("*.json"))
        ]
        self.assertEqual(sum(len(document["groups"]) for document in documents), 60)
        self.assertEqual(
            sum(len(group["requests"]) for document in documents for group in document["groups"]),
            300,
        )
        self.assertEqual(sum(len(document["hard_negatives"]) for document in documents), 30)
        for document in documents:
            for group in document["groups"]:
                self.assertIn(group["request_type"], {"bug", "change", "feature", "support"})
                self.assertTrue(
                    all(
                        request["request_type"] == group["request_type"]
                        for request in group["requests"]
                    )
                )
                for request in group["requests"]:
                    evidence = {
                        "environment",
                        "steps_to_reproduce",
                        "expected_result",
                        "actual_result",
                    }
                    self.assertEqual(evidence <= request.keys(), request["request_type"] == "bug")

    def test_everyday_seed_maps_bug_fields_and_keeps_non_bug_evidence_blank(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True):
            manifest_path = Path(directory) / "manifest.json"
            call_command(
                "seed_synthetic",
                count=50,
                seed=1313,
                corpus="everyday",
                manifest=str(manifest_path),
                skip_embeddings=True,
                verbosity=0,
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            issues = list(Issue.objects.filter(is_synthetic=True).order_by("synthetic_key"))

        self.assertEqual(len(issues), 50)
        self.assertEqual(
            {row.request_type for row in issues}, {"BUG", "CHANGE", "FEATURE", "SUPPORT"}
        )
        everyday = [
            request
            for path in (ROOT / "seed/synthetic_corpus_everyday").glob("*.json")
            for group in json.loads(path.read_text(encoding="utf-8"))["groups"]
            for request in group["requests"]
        ]
        bug_evidence = {
            request[field]
            for request in everyday
            if request["request_type"] == "bug"
            for field in (
                "environment",
                "steps_to_reproduce",
                "expected_result",
                "actual_result",
            )
        }
        bug_issues = [row for row in issues if row.request_type == "BUG"]
        self.assertTrue(any(row.environment in bug_evidence for row in bug_issues))
        self.assertTrue(
            all(
                not any(
                    (
                        row.environment,
                        row.steps_to_reproduce,
                        row.expected_result,
                        row.actual_result,
                    )
                )
                for row in issues
                if row.request_type != "BUG"
            )
        )
        self.assertTrue(all("request_type" in record for record in manifest["records"]))
        self.assertTrue(
            all("label" in record and "near_group" in record for record in manifest["records"])
        )

    def test_corpus_filter_and_group_tenant_cohesion(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True):
            manifest_path = Path(directory) / "manifest.json"
            call_command(
                "seed_synthetic",
                count=25,
                seed=1414,
                corpus="everyday",
                manifest=str(manifest_path),
                skip_embeddings=True,
                verbosity=0,
            )
            records = json.loads(manifest_path.read_text(encoding="utf-8"))["records"]
        areas = {"auth", "cards", "core", "digital", "transfer"}
        self.assertTrue(all(record["group"].split("-")[0] in areas for record in records))
        tenant_by_group = {}
        for record in records:
            tenant_by_group.setdefault(record["group"], record["tenant"])
            self.assertEqual(tenant_by_group[record["group"]], record["tenant"])

    def test_comparison_reports_ranking_and_label_metrics_by_request_type(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True):
            manifest_path = Path(directory) / "manifest.json"
            output_path = Path(directory) / "comparison.json"
            call_command(
                "seed_synthetic",
                count=50,
                seed=1515,
                corpus="everyday",
                manifest=str(manifest_path),
                skip_embeddings=True,
                verbosity=0,
            )
            with patch(
                "domains.search.management.commands.compare_features._load_embedder",
                return_value=None,
            ):
                call_command(
                    "compare_features",
                    manifest=str(manifest_path),
                    output=str(output_path),
                    verbosity=0,
                )
            comparison = json.loads(output_path.read_text(encoding="utf-8"))

        expected = {"bug", "change", "feature", "support"}
        self.assertEqual(
            set(comparison["ranking"]["lexical"]["per_request_type"]),
            expected,
        )
        self.assertTrue(comparison["labels"]["per_request_type"])
