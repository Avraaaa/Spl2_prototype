"""Evaluate lexical, dense, and reciprocal-rank hybrid search on synthetic data."""

import json
import os
import re
from pathlib import Path

from django.core.management.base import BaseCommand

from domains.search.embeddings import MODEL_ID, PREPROCESSING_VERSION, query_text
from domains.search.evaluation import evaluate_rankings
from domains.search.services import _ml_embeddings


class Command(BaseCommand):
    help = "Run the synthetic English/Bangla/Banglish retrieval evaluation."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="seed/p7t5_experiment_manifest.json")

    def handle(self, *args, **options):
        root = Path.cwd()
        fixture = json.loads((root / "seed/search_evaluation.json").read_text(encoding="utf-8"))
        by_language = {}
        all_metrics = {"lexical": [], "dense": [], "hybrid": []}
        for sample in fixture["queries"]:
            candidates = sample["candidates"]
            grades = [item["grade"] for item in candidates]
            query = sample["text"]
            query_terms = set(re.findall(r"[\w\u0980-\u09ff]+", query.casefold()))
            lexical_scores = [
                len(query_terms & set(re.findall(r"[\w\u0980-\u09ff]+", item["text"].casefold())))
                for item in candidates
            ]
            lexical_rank = sorted(
                range(len(candidates)), key=lambda index: (-lexical_scores[index], index)
            )
            vectors = _ml_embeddings(
                [query_text(query), *[f"passage: {item['text']}" for item in candidates]]
            )
            if vectors:
                dense_scores = [
                    sum(a * b for a, b in zip(vectors[0], vector, strict=True))
                    for vector in vectors[1:]
                ]
                dense_rank = sorted(
                    range(len(candidates)), key=lambda index: (-dense_scores[index], index)
                )
            else:
                dense_rank = list(lexical_rank)
            ranks = [
                {item: rank for rank, item in enumerate(order, start=1)}
                for order in (lexical_rank, dense_rank)
            ]
            fused = {
                index: sum(1 / (60 + rank.get(index, 999)) for rank in ranks)
                for index in range(len(candidates))
            }
            hybrid_rank = sorted(fused, key=lambda index: (-fused[index], index))
            metrics = evaluate_rankings(
                grades, {"lexical": lexical_rank, "dense": dense_rank, "hybrid": hybrid_rank}
            )
            by_language[sample["language"]] = metrics
            for name in all_metrics:
                all_metrics[name].append(metrics[name])
        aggregate = {
            name: {
                metric: round(sum(row[metric] for row in values) / len(values), 4)
                for metric in values[0]
            }
            for name, values in all_metrics.items()
        }
        manifest = {
            "model_id": MODEL_ID,
            "model_revision": os.getenv("ML_MODEL_REVISION", "unversioned-local-checkpoint"),
            "preprocessing_version": PREPROCESSING_VERSION,
            "prefix_scheme": {"stored": "passage:", "query": "query:"},
            "fusion": {"method": "rrf", "k": 60},
            "dataset_revision": fixture["revision"],
            "dataset_split": fixture["split"],
            "metrics": {"aggregate": aggregate, "language_variant": by_language},
        }
        output = root / options["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.stdout.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
