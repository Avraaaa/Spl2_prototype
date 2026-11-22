"""P7-T12 corpus-backed seeding and per-type masking reports."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from domains.accounts import services as account_services
from domains.accounts.roles import Role
from domains.issues.models import Issue
from domains.search.models import EmbeddingJob
from domains.tenants.models import Organization, OrganizationKind

ROOT = Path(__file__).parents[3]


class P7T12CorpusTests(TestCase):
    def setUp(self):
        datasoft = account_services.ensure_datasoft_organization()
        for code, name in (("NWD", "Northwind Demo Bank"), ("RSD", "Riverstone Demo Bank")):
            bank, _ = Organization.objects.get_or_create(
                code=code,
                defaults={"name": name, "kind": OrganizationKind.BANK},
            )
            account_services.create_user_unchecked(
                organization=bank,
                username=f"p7t12_{code.lower()}_officer",
                email=f"p7t12_{code.lower()}@example.test",
                full_name="Synthetic Issue Officer",
                roles=[Role.ISSUE_OFFICER],
            )
            account_services.create_user_unchecked(
                organization=bank,
                username=f"p7t12_{code.lower()}_verifier",
                email=f"p7t12_{code.lower()}_verifier@example.test",
                full_name="Synthetic Issue Verifier",
                roles=[Role.ISSUE_VERIFIER],
            )
        account_services.create_user_unchecked(
            organization=datasoft,
            username="p7t12_admin",
            email="p7t12_admin@example.test",
            full_name="Synthetic DataSoft Admin",
            roles=[Role.DATASOFT_ADMIN],
        )

    def test_corpus_has_expected_breadth_and_well_formed_ground_truth(self):
        corpora = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((ROOT / "seed/synthetic_corpus").glob("*.json"))
        ]
        self.assertEqual(len(corpora), 5)
        self.assertEqual(sum(len(corpus["groups"]) for corpus in corpora), 82)
        self.assertEqual(
            sum(len(group["requests"]) for corpus in corpora for group in corpus["groups"]),
            410,
        )
        self.assertEqual(sum(len(corpus["hard_negatives"]) for corpus in corpora), 50)
        self.assertEqual(sum(len(corpus["sensitive_cases"]) for corpus in corpora), 60)
        variants = {"English", "Bangla", "Banglish", "Code-switched", "Typo"}
        for corpus in corpora:
            for group in corpus["groups"]:
                self.assertEqual({request["variant"] for request in group["requests"]}, variants)
                self.assertTrue(
                    all(
                        request["title"] and request["description"] for request in group["requests"]
                    )
                )

    def test_seed_uses_real_corpus_titles_and_emits_expected_masks(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True):
            manifest_path = Path(directory) / "manifest.json"
            call_command(
                "seed_synthetic", count=12, seed=91, manifest=str(manifest_path), verbosity=0
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            seeded = list(Issue.objects.filter(is_synthetic=True))
        corpus_titles = {
            request["title"]
            for path in (ROOT / "seed/synthetic_corpus").glob("*.json")
            for group in json.loads(path.read_text(encoding="utf-8"))["groups"]
            for request in group["requests"]
        }
        self.assertTrue(any(issue.title in corpus_titles for issue in seeded))
        self.assertFalse(any(issue.title.startswith("Synthetic ") for issue in seeded))
        self.assertTrue(all(issue.product_id and issue.module_id for issue in seeded))
        self.assertTrue(manifest["expected_masks"])
        self.assertTrue(manifest["must_not_mask"])
        self.assertGreater(EmbeddingJob.objects.filter(issue__is_synthetic=True).count(), 0)

    def test_compare_reports_masking_metrics_per_sensitive_type(self):
        with TemporaryDirectory() as directory, override_settings(DEBUG=True):
            manifest_path = Path(directory) / "manifest.json"
            output_path = Path(directory) / "comparison.json"
            call_command(
                "seed_synthetic", count=12, seed=92, manifest=str(manifest_path), verbosity=0
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
            report = comparison["masking"]
        self.assertEqual(
            set(report["per_type"]), {"otp", "card", "account", "nid", "email", "phone"}
        )
        for metrics in report["per_type"].values():
            self.assertEqual(
                set(metrics),
                {"true_positive", "false_positive", "false_negative", "precision", "recall"},
            )
        self.assertTrue(comparison["ranking"]["lexical"]["per_tenant_language"])
        self.assertTrue(comparison["ranking"]["lexical"]["per_variant"])
        self.assertIn("false_positive_rate@5", comparison["ranking"]["lexical"]["hard_negatives"])
        self.assertGreater(comparison["topics"]["emerging_samples"], 0)
