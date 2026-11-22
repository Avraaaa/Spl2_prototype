"""P7-T8 regression coverage for honest evaluation and masking gaps."""

import json

from django.test import TestCase

from domains.issues.services import mask_sensitive
from domains.search.evaluation import (
    label_metrics,
    require_local_embedder,
    topic_cluster_purity,
    validate_fixture,
)


class P7T8FixtureTests(TestCase):
    def test_fixture_has_variant_coverage_and_incident_split(self):
        from pathlib import Path

        fixture = json.loads(
            (Path(__file__).parents[3] / "seed/search_evaluation.json").read_text(encoding="utf-8")
        )
        summary = validate_fixture(fixture)
        self.assertGreaterEqual(summary["query_count"], 60)
        self.assertTrue(all(count >= 10 for count in summary["variant_counts"].values()))
        self.assertEqual(fixture["split_by"], "incident")
        self.assertTrue(fixture["augmentation_applied_after_split"])

    def test_label_and_topic_metrics_are_measurable(self):
        rows = [
            {"expected": "Authentication", "predicted": "Authentication", "threshold": 0.6},
            {"expected": "Transaction", "predicted": None, "threshold": 0.6},
            {"expected": "Other", "predicted": "Authentication", "threshold": 0.6},
        ]
        metrics = label_metrics(rows)
        self.assertAlmostEqual(metrics["accuracy@1"], 1 / 3, places=4)
        self.assertAlmostEqual(metrics["coverage"], 2 / 3, places=4)
        self.assertAlmostEqual(metrics["abstention_rate"], 1 / 3, places=4)
        self.assertEqual(
            topic_cluster_purity(
                [["a", "b", "c"], ["d", "e"]],
                {"a": "x", "b": "x", "c": "y", "d": "z", "e": "z"},
            ),
            0.8,
        )

    def test_dense_config_without_local_embedder_is_skipped(self):
        matrix, skipped = require_local_embedder(
            [
                {"name": "lexical", "mode": "lexical"},
                {"name": "dense", "mode": "dense"},
                {"name": "hybrid", "mode": "hybrid"},
            ],
            None,
        )
        self.assertEqual([row["name"] for row in matrix], ["lexical"])
        self.assertEqual(len(skipped), 2)
        self.assertTrue(all(row["status"] == "SKIPPED" for row in skipped))
        self.assertTrue(all("no local embedder" in row["reason"] for row in skipped))

    def test_dense_config_uses_injected_embedder(self):
        fake_embedder = object()
        matrix, skipped = require_local_embedder(
            [{"name": "dense", "mode": "dense"}], fake_embedder
        )
        self.assertIs(matrix[0]["embedder"], fake_embedder)
        self.assertEqual(skipped, [])


class P7T8MaskingTests(TestCase):
    def test_email_addresses_are_masked(self):
        self.assertIn("[EMAIL]", mask_sensitive("Contact synthetic.user@example.test"))
        masked = mask_sensitive("synthetic.user@example.test")
        self.assertNotIn("synthetic.user@example.test", masked)

    def test_nid_keywords_mask_ascii_and_bangla_digits(self):
        for sample in (
            "NID: 1234567890123",
            "national ID 1234567890123",
            "জাতীয় পরিচয়পত্র: ১২৩৪৫৬৭৮৯০১২৩",
            "এনআইডি ১২৩৪৫৬৭৮৯০১২৩",
        ):
            with self.subTest(sample=sample):
                masked = mask_sensitive(sample)
                self.assertIn("[NID]", masked)
                self.assertNotIn("1234567890123", masked)
                self.assertNotIn("১২৩৪৫৬৭৮৯০১২৩", masked)

    def test_labeled_long_transaction_references_are_not_cards(self):
        sample = "Txn ID 12345678901234567890; Order no 98765432109876543210"
        masked = mask_sensitive(sample)
        self.assertIn("12345678901234567890", masked)
        self.assertIn("98765432109876543210", masked)
        self.assertNotIn("[CARD REDACTED]", masked)
