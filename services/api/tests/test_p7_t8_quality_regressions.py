"""Additional P7-T8 regression cases for fixture integrity and detector edges."""

import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from domains.issues.services import mask_sensitive
from domains.search.evaluation import validate_fixture


class EvaluationFixtureIntegrityTests(SimpleTestCase):
    def test_multilingual_queries_are_not_question_marks_or_unicode_escapes(self):
        fixture = json.loads(
            (Path(__file__).parents[3] / "seed/search_evaluation.json").read_text(encoding="utf-8")
        )
        validate_fixture(fixture)
        for query in fixture["queries"]:
            text = query["text"]
            if query["language"] in {"Bangla", "Code-switched"}:
                self.assertGreater(sum(char != "?" and not char.isspace() for char in text), 5)
                self.assertNotRegex(text, r"\\u[0-9a-fA-F]{4}")

    def test_validate_fixture_rejects_corrupted_multilingual_query(self):
        fixture = {
            "split_by": "incident",
            "augmentation_applied_after_split": True,
            "queries": [],
        }
        variants = ["English", "Bangla", "Banglish", "Code-switched", "Typo"]
        for variant in variants:
            for index in range(12):
                text = "valid synthetic query text"
                if variant == "Bangla":
                    text = "????? ????? ?????"
                fixture["queries"].append(
                    {
                        "language": variant,
                        "incident": f"incident-{index}",
                        "text": text,
                        "candidates": [{"grade": 2, "text": "candidate"}],
                    }
                )
        with self.assertRaises(ValueError):
            validate_fixture(fixture)


class MaskingDetectorRegressionTests(TestCase):
    def test_nid_keyword_context_allows_longer_labels(self):
        sample = "NID: " + ("customer identity reference " * 2) + "1234567890123"
        masked = mask_sensitive(sample)
        self.assertIn("[NID]", masked)
        self.assertNotIn("1234567890123", masked)

    def test_short_txn_id_reference_is_preserved(self):
        result = mask_sensitive("Txn ID 123456")
        self.assertIn("Txn ID 123456", result)
        self.assertNotIn("[CARD REDACTED]", result)

    def test_validate_fixture_rejects_literal_unicode_escape(self):
        fixture = {
            "split_by": "incident",
            "augmentation_applied_after_split": True,
            "queries": [],
        }
        for variant in ["English", "Bangla", "Banglish", "Code-switched", "Typo"]:
            for index in range(12):
                text = (
                    r"\u09a8\u09bf\u09b0\u09be\u09aa\u09a4\u09cd\u09a4\u09be"
                    if variant == "Bangla"
                    else "valid text"
                )
                fixture["queries"].append(
                    {
                        "language": variant,
                        "incident": f"incident-{index}",
                        "text": text,
                        "candidates": [{"grade": 2, "text": "candidate"}],
                    }
                )
        with self.assertRaises(ValueError):
            validate_fixture(fixture)
