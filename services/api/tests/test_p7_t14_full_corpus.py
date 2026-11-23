"""P7-T14 full synthetic corpus defaults and comparison embedding efficiency."""

import argparse
from unittest.mock import Mock

from django.test import TestCase

from domains.issues.management.commands.seed_synthetic import Command as SeedCommand
from domains.search.management.commands.compare_features import Command as CompareCommand


class P7T14FullCorpusTests(TestCase):
    def test_default_seed_covers_full_790_record_corpus_and_allows_it(self):
        parser = argparse.ArgumentParser()
        SeedCommand().add_arguments(parser)
        options = parser.parse_args([])
        corpus, _ = SeedCommand._corpus("all")

        self.assertEqual(len(corpus), 790)
        self.assertIsNone(options.count)
        self.assertEqual(SeedCommand._default_count("all"), 790)
        parser.parse_args(["--count", "790"])

    def test_compare_preencodes_query_and_passage_vectors_in_one_batch(self):
        issues = {
            1: Mock(pk=1, title="first", description="details"),
            2: Mock(pk=2, title="second", description="other details"),
        }
        records = [{"issue_id": issue_id} for issue_id in issues]
        embedder = Mock()
        embedder.encode.return_value = [[1.0], [2.0], [3.0], [4.0]]

        vectors = CompareCommand._encode_issue_vectors(records, issues, embedder)

        embedder.encode.assert_called_once()
        self.assertEqual(len(embedder.encode.call_args.args[0]), 4)
        self.assertEqual(vectors[1], ([1.0], [2.0]))
        self.assertEqual(vectors[2], ([3.0], [4.0]))
