"""Compare live, tenant-scoped suggestions with the synthetic ground-truth manifest."""

import json
import os
import re
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from domains.issues.models import Issue
from domains.issues.services import mask_sensitive
from domains.search.banglish import normalize_banglish
from domains.search.embeddings import MODEL_ID, embedding_input, passage_text, query_text
from domains.search.evaluation import (
    label_metrics,
    ndcg_at_k,
    reciprocal_rank,
    topic_cluster_purity,
)
from domains.search.models import IssueLabelSelection, Label
from domains.search.services import cluster_recent_unidentified, label_suggestions

TOKEN = re.compile(r"[\w\u0980-\u09ff]+", re.UNICODE)
SENSITIVE = {
    "otp": "[OTP REDACTED]",
    "email": "[EMAIL]",
    "card": "[CARD REDACTED]",
    "account": "[ACCOUNT_NUMBER]",
    "nid": "[NID]",
    "phone": "[PHONE_NUMBER]",
}


def _load_embedder(path):
    """Load the optional local sentence model without requiring a download."""
    if not path:
        return None
    checkpoint = Path(path)
    if not (checkpoint / "config.json").exists() and (checkpoint / MODEL_ID).is_dir():
        checkpoint = checkpoint / MODEL_ID
    if not checkpoint.is_dir():
        return None
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(str(checkpoint.resolve()), local_files_only=True)


class Command(BaseCommand):
    help = "Compare duplicate, label, topic and masking features on tagged live synthetic requests."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", default="seed/p7t9_synthetic_manifest.json")
        parser.add_argument("--output", default="seed/p7t9_feature_comparison.json")
        parser.add_argument("--embedder-path", default=os.getenv("ML_MODELS_DIR"))

    def handle(self, *args, **options):
        root = Path.cwd()
        manifest_path = Path(options["manifest"])
        if not manifest_path.is_absolute():
            manifest_path = root / manifest_path
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot read synthetic manifest: {exc}") from exc
        if manifest.get("synthetic_only") is not True or not manifest.get("records"):
            raise CommandError("Manifest is not a P7-T9 synthetic dataset manifest.")
        ids = [row["issue_id"] for row in manifest["records"]]
        issues = {
            issue.pk: issue
            for issue in Issue.objects.filter(pk__in=ids, is_synthetic=True).select_related(
                "organization", "product", "module"
            )
        }
        records = [row for row in manifest["records"] if row["issue_id"] in issues]
        if not records:
            raise CommandError("No tagged manifest requests exist in the live database.")
        embedder_path = options["embedder_path"] or (root / "models")
        embedder = self._load_embedder(embedder_path)
        result = self._compare(records, issues, embedder)
        output = Path(options["output"])
        if not output.is_absolute():
            output = root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown = output.with_suffix(".md")
        markdown.write_text(self._summary(result), encoding="utf-8")
        self.stdout.write(f"Feature comparison written to {output} and {markdown}")

    @staticmethod
    def _load_embedder(path):
        return _load_embedder(path)

    @classmethod
    def _compare(cls, records, issues, embedder):
        candidates_by_tenant = defaultdict(list)
        for issue in issues.values():
            candidates_by_tenant[issue.organization_id].append(issue)
        cutoff = timezone.now() - timedelta(days=365)
        rankings = {name: defaultdict(list) for name in ("lexical", "dense", "hybrid")}
        labels_report = []
        tenants = {}
        cross_bank_candidates = 0
        labels = list(Label.objects.filter(is_active=True).order_by("pk"))
        for record in records:
            query = issues[record["issue_id"]]
            candidates = [
                row
                for row in candidates_by_tenant[query.organization_id]
                if row.pk != query.pk and row.status != "DRAFT" and row.created_at >= cutoff
            ]
            cross_bank_candidates += sum(
                row.organization_id != query.organization_id for row in candidates
            )
            # Group ids are manifest-only; equality is resolved below from peer records.
            group_peers = {
                item["issue_id"]
                for item in records
                if item["tenant"] == record["tenant"] and item["group"] == record["group"]
            }
            relevant_ids = group_peers - {query.pk}
            ordered = sorted(candidates, key=lambda row: row.pk)
            grades = [2 if row.pk in relevant_ids else 0 for row in ordered]
            lexical_scores = [cls._overlap(query, row) for row in ordered]
            lexical_order = sorted(
                range(len(ordered)), key=lambda idx: (-lexical_scores[idx], ordered[idx].pk)
            )
            rankings["lexical"][(record["tenant"], record["language"])].append(
                (grades, lexical_order)
            )
            if embedder is not None and ordered:
                inputs = [
                    embedding_input(query_text(f"{query.title}\n{query.description}")),
                    *(
                        embedding_input(passage_text(f"{row.title}\n{row.description}"))
                        for row in ordered
                    ),
                ]
                encoded = embedder.encode(inputs, normalize_embeddings=True)
                vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
                dense_order = sorted(
                    range(len(ordered)),
                    key=lambda idx: (
                        -sum(a * b for a, b in zip(vectors[0], vectors[idx + 1], strict=True)),
                        ordered[idx].pk,
                    ),
                )
                rankings["dense"][(record["tenant"], record["language"])].append(
                    (grades, dense_order)
                )
                rrf = {
                    idx: 1 / (60 + lexical_order.index(idx) + 1)
                    + 1 / (60 + dense_order.index(idx) + 1)
                    for idx in range(len(ordered))
                }
                hybrid_order = sorted(
                    range(len(ordered)), key=lambda idx: (-rrf[idx], ordered[idx].pk)
                )
                rankings["hybrid"][(record["tenant"], record["language"])].append(
                    (grades, hybrid_order)
                )
            suggestions = label_suggestions(
                title=query.title,
                description=query.description,
                labels=labels,
                organization=query.organization,
            )
            prediction = suggestions[0] if suggestions else None
            selected = (
                IssueLabelSelection.objects.filter(issue=query).select_related("label").first()
            )
            thresholds = {label.name: label.confidence_threshold for label in labels}
            if record.get("expected_label"):
                labels_report.append(
                    {
                        "tenant": record["tenant"],
                        "expected": record["expected_label"],
                        "predicted": prediction["name"] if prediction else None,
                        "score": prediction["score"] if prediction else 0.0,
                        "threshold": (
                            thresholds.get(prediction["name"], 1.0) if prediction else 1.0
                        ),
                        "confirmed": selected.label.name if selected else None,
                    }
                )
            tenants[record["tenant"]] = query.organization
        ranking_result = {}
        for mode in ("lexical", "dense", "hybrid"):
            by_variant = {}
            all_rows = [item for samples in rankings[mode].values() for item in samples]
            for key, samples in rankings[mode].items():
                by_variant[f"{key[0]}:{key[1]}"] = cls._rank_metrics(samples)
            if all_rows:
                ranking_result[mode] = cls._rank_metrics(all_rows)
            elif mode == "lexical" or embedder is not None:
                # An available embedder with no eligible candidates is still a
                # completed comparison; report zero samples instead of claiming
                # the model was unavailable.
                ranking_result[mode] = cls._rank_metrics([])
            else:
                ranking_result[mode] = {
                    "status": "SKIPPED",
                    "reason": "no local embedder available",
                }
            ranking_result[mode]["per_tenant_language"] = by_variant
            if mode in {"dense", "hybrid"} and embedder is None:
                ranking_result[mode] = {
                    "status": "SKIPPED",
                    "reason": "no local embedder available",
                    "per_tenant_language": {},
                }
        topic_ids = {
            str(record["issue_id"]): record.get("topic", record["group"]) for record in records
        }
        topic_clusters = []
        topic_by_tenant = {}
        for tenant, organization in tenants.items():
            proposals = cluster_recent_unidentified(
                Issue.objects.filter(organization=organization, is_synthetic=True)
            )
            clusters = [
                [str(issue_id) for issue_id in proposal["issue_ids"]] for proposal in proposals
            ]
            topic_clusters.extend(clusters)
            topic_by_tenant[tenant] = {
                "cluster_count": len(clusters),
                "purity": topic_cluster_purity(clusters, topic_ids),
            }
        mask_totals = {"true_positive": 0, "false_positive": 0, "false_negative": 0}
        for record in records:
            issue = issues[record["issue_id"]]
            expected = set(record.get("mask_categories", []))
            detected = {
                category for category, marker in SENSITIVE.items() if marker in issue.description
            }
            mask_totals["true_positive"] += len(expected & detected)
            mask_totals["false_positive"] += len(detected - expected)
            mask_totals["false_negative"] += len(expected - detected)
        tp, fp, fn = (
            mask_totals[key] for key in ("true_positive", "false_positive", "false_negative")
        )
        masking = {
            **mask_totals,
            "precision": round(tp / (tp + fp), 4) if tp + fp else 1.0,
            "recall": round(tp / (tp + fn), 4) if tp + fn else 1.0,
        }
        return {
            "dataset_revision": "p7t9-live",
            "sample_count": len(records),
            "ranking": ranking_result,
            "labels": label_metrics(labels_report),
            "topics": {
                "purity": topic_cluster_purity(topic_clusters, topic_ids),
                "per_tenant": topic_by_tenant,
            },
            "masking": masking,
            "tenant_isolation": {"cross_bank_candidates": cross_bank_candidates},
        }

    @staticmethod
    def _overlap(query, candidate):
        left_text = normalize_banglish(mask_sensitive(f"{query.title} {query.description}"))
        right_text = normalize_banglish(
            mask_sensitive(f"{candidate.title} {candidate.description}")
        )
        left = set(TOKEN.findall(left_text.casefold()))
        right = set(TOKEN.findall(right_text.casefold()))
        return len(left & right) / max(1, len(left | right))

    @staticmethod
    def _rank_metrics(samples):
        if not samples:
            return {
                "status": "OK",
                "hit_rate@5": 0.0,
                "mrr@5": 0.0,
                "ndcg@5": 0.0,
                "sample_count": 0,
            }
        hits = [float(any(grades[index] > 0 for index in order[:5])) for grades, order in samples]
        mrr = [reciprocal_rank(grades, order) for grades, order in samples]
        ndcg = [ndcg_at_k(grades, order) for grades, order in samples]
        return {
            "status": "OK",
            "hit_rate@5": round(sum(hits) / len(hits), 4),
            "mrr@5": round(sum(mrr) / len(mrr), 4),
            "ndcg@5": round(sum(ndcg) / len(ndcg), 4),
            "sample_count": len(samples),
        }

    @staticmethod
    def _summary(result):
        lines = [
            "# P7-T9 live feature comparison",
            "",
            f"Synthetic requests scored: {result['sample_count']}",
            "",
            "## Duplicate ranking",
            "",
            "| Method | HitRate@5 | MRR@5 | nDCG@5 |",
            "|---|---:|---:|---:|",
        ]
        for method, metrics in result["ranking"].items():
            if metrics.get("status") == "SKIPPED":
                lines.append(f"| {method} | SKIPPED | SKIPPED | SKIPPED |")
            else:
                lines.append(
                    f"| {method} | {metrics['hit_rate@5']:.4f} | "
                    f"{metrics['mrr@5']:.4f} | {metrics['ndcg@5']:.4f} |"
                )
        labels = result["labels"]
        lines.extend(
            [
                "",
                "## Labels and masking",
                "",
                f"Label accuracy@1: {labels['accuracy@1']:.4f}; "
                f"coverage: {labels['coverage']:.4f}; "
                f"abstention: {labels['abstention_rate']:.4f}.",
                f"Masking precision: {result['masking']['precision']:.4f}; "
                f"recall: {result['masking']['recall']:.4f}.",
                f"Topic cluster purity: {result['topics']['purity']:.4f}.",
                "",
            ]
        )
        return "\n".join(lines)
