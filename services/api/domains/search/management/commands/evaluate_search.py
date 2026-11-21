"""Compare lexical and local embedding configurations on synthetic requests."""

import json
import os
import re
from pathlib import Path
from time import perf_counter

from django.core.management.base import BaseCommand

from domains.search.banglish import NORMALIZATION_VERSION, normalize_banglish
from domains.search.embeddings import MODEL_ID, PREPROCESSING_VERSION
from domains.search.evaluation import evaluate_rankings, model_matrix, percentile
from domains.search.services import _ml_embeddings


class Command(BaseCommand):
    help = "Run a local-only synthetic embedding and Banglish comparison matrix."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="seed/p7t6_experiment_manifest.json")
        parser.add_argument("--models-dir", default=os.getenv("ML_MODELS_DIR"))
        parser.add_argument("--embedder-id", default=MODEL_ID)
        parser.add_argument("--embedder-path")
        parser.add_argument(
            "--prefix-scheme", choices=("symmetric", "asymmetric"), default="asymmetric"
        )
        parser.add_argument("--normalization", action="store_true")
        parser.add_argument("--fusion", choices=("rrf", "lexical", "dense"), default="rrf")

    def handle(self, *args, **options):
        root = Path.cwd()
        models_dir = Path(options["models_dir"]) if options["models_dir"] else root / "models"
        fixture = json.loads((root / "seed/search_evaluation.json").read_text(encoding="utf-8"))
        model_ids = [
            "multilingual-e5-small",
            "gte-multilingual-base",
            "bangla-embed-e5-small-banglish",
        ]
        configurations, skipped = model_matrix(
            model_ids=model_ids,
            models_dir=models_dir,
            embedder_factory=lambda path, model_id: self._load_local_embedder(
                path, model_id, models_dir
            ),
            configurations=[
                {"name": "lexical", "mode": "lexical", "normalize": False},
                {"name": "dense", "mode": "dense", "normalize": False},
                {"name": "hybrid", "mode": "hybrid", "normalize": False},
                {"name": "hybrid+normalization", "mode": "hybrid", "normalize": True},
            ],
        )
        if options["embedder_path"] and Path(options["embedder_path"]).is_dir():
            configurations.append(
                {
                    "name": options["embedder_id"],
                    "mode": "hybrid",
                    "normalize": options["normalization"],
                    "model_id": options["embedder_id"],
                    "prefix_scheme": options["prefix_scheme"],
                    "fusion": options["fusion"],
                    "embedder": self._load_local_embedder(
                        Path(options["embedder_path"]), options["embedder_id"], models_dir
                    ),
                }
            )
        elif options["embedder_path"]:
            skipped.append(f"{options['embedder_id']}: missing local checkpoint")
        for configuration in configurations:
            configuration.setdefault("prefix_scheme", options["prefix_scheme"])
            configuration.setdefault("fusion", options["fusion"])

        metric_rows = {item["name"]: [] for item in configurations}
        language_metrics = {}
        latency_seconds = {item["name"]: [] for item in configurations if item["mode"] != "lexical"}
        for sample in fixture["queries"]:
            candidates = sample["candidates"]
            grades = [item["grade"] for item in candidates]
            ranks_by_name = self._rank_configurations(
                sample["text"], candidates, configurations, latency_seconds
            )
            metrics = evaluate_rankings(grades, ranks_by_name)
            language_metrics[sample["language"]] = metrics
            for name, row in metrics.items():
                metric_rows[name].append(row)
        aggregate = {
            name: {
                key: round(sum(row[key] for row in values) / len(values), 4) for key in values[0]
            }
            for name, values in metric_rows.items()
            if values
        }
        latency = {
            name: {
                "p50_ms": percentile([value * 1000 for value in values], 0.50),
                "p95_ms": percentile([value * 1000 for value in values], 0.95),
            }
            for name, values in latency_seconds.items()
        }
        manifest = {
            "models_dir": str(models_dir),
            "model_id": options["embedder_id"],
            "model_revision": os.getenv("ML_MODEL_REVISION", "unversioned-local-checkpoint"),
            "preprocessing_version": PREPROCESSING_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
            "prefix_scheme": options["prefix_scheme"],
            "normalization": options["normalization"],
            "fusion": {"method": options["fusion"], "k": 60},
            "dataset_revision": fixture["revision"],
            "dataset_split": fixture["split"],
            "dataset_split_by": fixture.get("split_by", "incident"),
            "metrics": {"aggregate": aggregate, "language_variant": language_metrics},
            "embedding_latency": latency,
            "skipped_models": skipped,
            "model_notes": {
                "bangla-embed-e5-small-banglish": "prototype checkpoint; licence review pending"
            },
        }
        output = root / options["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        for message in skipped:
            self.stdout.write(f"Skipped {message}")
        self.stdout.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True))

    @staticmethod
    def _load_local_embedder(path: Path, model_id: str, models_dir: Path):
        resolved = path.resolve()
        from sentence_transformers import SentenceTransformer

        allow_remote_code = model_id == "gte-multilingual-base" and resolved.is_relative_to(
            models_dir.resolve()
        )
        return SentenceTransformer(
            str(resolved), local_files_only=True, trust_remote_code=allow_remote_code
        )

    @staticmethod
    def _rank_configurations(text, candidates, configurations, latency_seconds):
        result = {}
        for configuration in configurations:
            name = configuration["name"]
            normalize = configuration.get("normalize", False)
            query = normalize_banglish(text) if normalize else text
            rows = [
                normalize_banglish(item["text"]) if normalize else item["text"]
                for item in candidates
            ]
            query_terms = set(re.findall(r"[\w\u0980-\u09ff]+", query.casefold()))
            lexical_scores = [
                len(query_terms & set(re.findall(r"[\w\u0980-\u09ff]+", value.casefold())))
                for value in rows
            ]
            lexical_rank = sorted(
                range(len(rows)), key=lambda index: (-lexical_scores[index], index)
            )
            mode = configuration["mode"]
            if mode == "lexical":
                result[name] = lexical_rank
                continue
            embedder = configuration.get("embedder")
            if embedder is None:
                if configuration.get("prefix_scheme") == "symmetric":
                    prefix_query = f"passage: {query}"
                else:
                    prefix_query = f"query: {query}"
                prefix_rows = [f"passage: {value}" for value in rows]
                started = perf_counter()
                vectors = _ml_embeddings([prefix_query, *prefix_rows])
            else:
                scheme = "query" if configuration.get("prefix_scheme") == "asymmetric" else ""
                prefix_query = f"{scheme}: {query}" if scheme else query
                prefix_rows = [f"passage: {value}" if scheme else value for value in rows]
                started = perf_counter()
                vectors = embedder.encode(
                    [prefix_query, *prefix_rows], normalize_embeddings=True
                ).tolist()
            latency_seconds.setdefault(name, []).append(perf_counter() - started)
            dense_rank = lexical_rank
            if vectors:
                scores = [
                    sum(a * b for a, b in zip(vectors[0], vector, strict=True))
                    for vector in vectors[1:]
                ]
                dense_rank = sorted(range(len(rows)), key=lambda index: (-scores[index], index))
            if mode == "dense" or configuration.get("fusion") == "dense":
                result[name] = dense_rank
            elif configuration.get("fusion") == "lexical":
                result[name] = lexical_rank
            else:
                ranks = [
                    {item: rank for rank, item in enumerate(order, start=1)}
                    for order in (lexical_rank, dense_rank)
                ]
                fused = {
                    index: sum(1 / (60 + rank.get(index, 999)) for rank in ranks)
                    for index in range(len(rows))
                }
                result[name] = sorted(fused, key=lambda index: (-fused[index], index))
        return result
