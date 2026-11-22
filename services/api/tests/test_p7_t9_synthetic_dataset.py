"""P7-T9 synthetic dataset and live feature comparison acceptance tests."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from domains.accounts import services as account_services
from domains.accounts.roles import Role
from domains.issues.models import Issue
from domains.issues.services import create_draft, mask_sensitive
from domains.products.models import Product
from domains.search.models import EmbeddingJob
from domains.tenants.models import Organization, OrganizationKind


class SyntheticDatasetCommandTests(TestCase):
    def setUp(self):
        datasoft = account_services.ensure_datasoft_organization()
        banks = {}
        for code, name in (("NWD", "Northwind Demo Bank"), ("RSD", "Riverstone Demo Bank")):
            banks[code], _ = Organization.objects.get_or_create(
                code=code,
                defaults={"name": name, "kind": OrganizationKind.BANK},
            )
        self._user("p7t9_admin", datasoft, Role.DATASOFT_ADMIN)
        for code, bank in banks.items():
            self._user(f"p7t9_{code.lower()}_officer", bank, Role.ISSUE_OFFICER)
            self._user(f"p7t9_{code.lower()}_verifier", bank, Role.ISSUE_VERIFIER)

    @staticmethod
    def _user(username, organization, *roles):
        return account_services.create_user_unchecked(
            organization=organization,
            username=username,
            email=f"{username}@example.test",
            full_name=username,
            roles=list(roles),
        )

    def test_seed_is_deterministic_tagged_and_manifest_tracks_masked_expectations(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            with override_settings(DEBUG=True):
                call_command("seed_synthetic", count=12, seed=73, manifest=str(path), verbosity=0)
            first_manifest = json.loads(path.read_text(encoding="utf-8"))
            first = list(Issue.objects.filter(is_synthetic=True).order_by("synthetic_key"))
            first_data = [
                (row.synthetic_key, row.title, row.description, row.organization_id)
                for row in first
            ]
            self.assertEqual(len(first), 12)
            self.assertEqual(len(first_manifest["records"]), 12)
            self.assertEqual({row.organization.code for row in first}, {"NWD", "RSD"})
            self.assertTrue(first_manifest["groups"])
            self.assertTrue(first_manifest["expected_masks"])
            self.assertTrue(first_manifest["must_not_mask"])
            events = {kind for row in first_manifest["records"] for kind in row["workflow_events"]}
            self.assertIn("REOPENED", events)
            self.assertIn("VERIFICATION_FAILED", events)
            self.assertFalse(any("123456789012" in row.description for row in first))

            with override_settings(DEBUG=True):
                call_command("seed_synthetic", count=12, seed=73, manifest=str(path), verbosity=0)
            second = list(Issue.objects.filter(is_synthetic=True).order_by("synthetic_key"))
            self.assertEqual(
                first_data,
                [
                    (row.synthetic_key, row.title, row.description, row.organization_id)
                    for row in second
                ],
            )
            self.assertEqual(first_manifest, json.loads(path.read_text(encoding="utf-8")))
            self.assertGreater(EmbeddingJob.objects.filter(issue__is_synthetic=True).count(), 0)

    def test_reset_removes_only_generated_rows(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            with override_settings(DEBUG=True):
                call_command("seed_synthetic", count=10, seed=8, manifest=str(path), verbosity=0)
                ordinary = create_draft(
                    User.objects.get(username="p7t9_nwd_officer"),
                    {
                        "title": "Ordinary non-synthetic test request",
                        "description": "This request must remain after reset.",
                        "product": Product.objects.get(name="Synthetic Feature Lab"),
                    },
                )
                ordinary_ids = set(
                    Issue.objects.filter(is_synthetic=False).values_list("pk", flat=True)
                )
                call_command("seed_synthetic", reset=True, manifest=str(path), verbosity=0)
            self.assertFalse(Issue.objects.filter(is_synthetic=True).exists())
            remaining = set(Issue.objects.filter(pk__in=ordinary_ids).values_list("pk", flat=True))
            self.assertEqual(remaining, ordinary_ids)
            self.assertTrue(Issue.objects.filter(pk=ordinary.pk, is_synthetic=False).exists())

    def test_seed_refuses_non_debug_without_explicit_flag(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("seed_synthetic", count=10)

    def test_seed_refuses_non_local_hosts_even_with_allow_flag(self):
        with (
            override_settings(DEBUG=False, ALLOWED_HOSTS=["portal.example.test"]),
            self.assertRaises(CommandError),
        ):
            call_command("seed_synthetic", count=10, allow=True)

    def test_comparison_reports_live_metric_keys_and_skips_dense_without_embedder(self):
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            output = Path(directory) / "comparison.json"
            with override_settings(DEBUG=True):
                call_command(
                    "seed_synthetic", count=12, seed=9, manifest=str(manifest), verbosity=0
                )
            with patch(
                "domains.search.management.commands.compare_features._load_embedder",
                return_value=None,
            ):
                call_command(
                    "compare_features", manifest=str(manifest), output=str(output), verbosity=0
                )
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(set(result["ranking"]), {"lexical", "dense", "hybrid"})
            self.assertTrue(
                {"hit_rate@5", "mrr@5", "ndcg@5"}.issubset(result["ranking"]["lexical"])
            )
            self.assertEqual(result["ranking"]["dense"]["status"], "SKIPPED")
            self.assertIn("per_tenant_language", result["ranking"]["lexical"])
            self.assertIn("labels", result)
            self.assertIn("topics", result)
            self.assertIn("masking", result)
            self.assertTrue(result["tenant_isolation"]["cross_bank_candidates"] == 0)
            self.assertTrue(output.with_suffix(".md").exists())

    def test_comparison_uses_injected_fake_embedder_for_dense_and_hybrid(self):
        class FakeEmbedder:
            @staticmethod
            def encode(texts, normalize_embeddings=True):
                return [[1.0] + [0.0] * 383 for _ in texts]

        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            output = Path(directory) / "comparison.json"
            with override_settings(DEBUG=True):
                call_command(
                    "seed_synthetic", count=12, seed=10, manifest=str(manifest), verbosity=0
                )
            with patch(
                "domains.search.management.commands.compare_features.Command._load_embedder",
                return_value=FakeEmbedder(),
            ):
                call_command(
                    "compare_features", manifest=str(manifest), output=str(output), verbosity=0
                )
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotEqual(result["ranking"]["dense"]["status"], "SKIPPED")
            self.assertNotEqual(result["ranking"]["hybrid"]["status"], "SKIPPED")


class SyntheticMaskingRegressionTests(TestCase):
    def test_bangla_nid_spellings_are_masked(self):
        spellings = (
            "\u099c\u09be\u09a4\u09c0\u09af\u09bc "
            "\u09aa\u09b0\u09bf\u099a\u09af\u09bc\u09aa\u09a4\u09cd\u09b0",
            "\u099c\u09be\u09a4\u09c0\u09df \u09aa\u09b0\u09bf\u099a\u09df\u09aa\u09a4\u09cd\u09b0",
        )
        for spelling in spellings:
            with self.subTest(spelling=spelling):
                self.assertIn("[NID]", mask_sensitive(f"{spelling}: 1234567890123"))

    def test_transaction_reference_shields_only_its_own_token(self):
        masked = mask_sensitive(
            "Txn ID 123456789012 then phone 01712345678 and account 987654321012"
        )
        self.assertIn("Txn ID 123456789012", masked)
        self.assertIn("[PHONE_NUMBER]", masked)
        self.assertIn("[ACCOUNT_NUMBER]", masked)

    def test_transaction_placeholder_collision_does_not_hide_real_sensitive_values(self):
        masked = mask_sensitive("Txn ID 123456789012 __TRANSACTION_REFERENCE_0__ phone 01712345678")
        self.assertIn("[PHONE_NUMBER]", masked)
        self.assertNotIn("01712345678", masked)

    def test_error_and_version_lookalikes_remain_while_adjacent_phone_is_masked(self):
        masked = mask_sensitive(
            "Txn ID 123456789012; error E-4012 on version 2.4; phone 01712345678"
        )
        self.assertIn("Txn ID 123456789012", masked)
        self.assertIn("E-4012", masked)
        self.assertIn("2.4", masked)
        self.assertIn("[PHONE_NUMBER]", masked)
