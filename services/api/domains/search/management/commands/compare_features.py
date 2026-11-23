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
from domains.search.progress import ProgressReporter
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
        parser.add_argument("--progress-every", type=int, default=25)
        parser.add_argument("--log-file")

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
        if options["progress_every"] < 1:
            raise CommandError("--progress-every must be positive")
        result = self._compare(
            records, issues, embedder, options["progress_every"], options["log_file"]
        )
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

    @staticmethod
    def _encode_issue_vectors(records, issues, embedder):
        """Encode each manifest issue as a query and passage in one batch."""
        issue_ids = [record["issue_id"] for record in records]
        inputs = [
            encoded_text
            for issue_id in issue_ids
            for encoded_text in (
                embedding_input(
                    query_text(f"{issues[issue_id].title}\n{issues[issue_id].description}")
                ),
                embedding_input(
                    passage_text(f"{issues[issue_id].title}\n{issues[issue_id].description}")
                ),
            )
        ]
        encoded = embedder.encode(inputs, normalize_embeddings=True)
        vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        return {
            issue_id: (vectors[index * 2], vectors[index * 2 + 1])
            for index, issue_id in enumerate(issue_ids)
        }

    @classmethod
    def _compare(cls, records, issues, embedder, progress_every=25, log_file=None):
        candidates_by_tenant = defaultdict(list)
        for issue in issues.values():
            candidates_by_tenant[issue.organization_id].append(issue)
        cutoff = timezone.now() - timedelta(days=365)
        rankings = {name: defaultdict(list) for name in ("lexical", "dense", "hybrid")}
        rankings_by_type = {name: defaultdict(list) for name in rankings}
        hard_negative_ranks = {name: [] for name in rankings}
        labels_report = []
        tenants = {}
        cross_bank_candidates = 0
        labels = list(Label.objects.filter(is_active=True).order_by("pk"))
        vectors_by_issue = (
            cls._encode_issue_vectors(records, issues, embedder) if embedder is not None else {}
        )
        progress = ProgressReporter(
            "ranking lexical and dense", len(records), progress_every, log_file
        )
        labels_progress = ProgressReporter("labels", len(records), progress_every, log_file)
        progress.start()
        labels_progress.start()
        for done, record in enumerate(records, start=1):
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
                if item["tenant"] == record["tenant"]
                and item["group"] == record["group"]
                and not item.get("hard_negative", False)
            }
            relevant_ids = group_peers - {query.pk}
            ordered = sorted(candidates, key=lambda row: row.pk)
            grades = [2 if row.pk in relevant_ids else 0 for row in ordered]
            lexical_scores = [cls._overlap(query, row) for row in ordered]
            lexical_order = sorted(
                range(len(ordered)), key=lambda idx: (-lexical_scores[idx], ordered[idx].pk)
            )
            hard_negative_ids = {
                item["issue_id"]
                for item in records
                if item["tenant"] == record["tenant"] and item.get("hard_negative", False)
            }
            hard_negative_candidates = hard_negative_ids & {row.pk for row in ordered}
            if hard_negative_candidates:
                hard_negative_ranks["lexical"].append(
                    any(ordered[idx].pk in hard_negative_candidates for idx in lexical_order[:5])
                )
            rankings["lexical"][(record["tenant"], record["language"])].append(
                (grades, lexical_order)
            )
            request_type = record.get("request_type", query.request_type or "unknown")
            rankings_by_type["lexical"][request_type].append((grades, lexical_order))
            if embedder is not None and ordered:
                query_vector = vectors_by_issue[query.pk][0]
                dense_order = sorted(
                    range(len(ordered)),
                    key=lambda idx: (
                        -sum(
                            a * b
                            for a, b in zip(
                                query_vector,
                                vectors_by_issue[ordered[idx].pk][1],
                                strict=True,
                            )
                        ),
                        ordered[idx].pk,
                    ),
                )
                rankings["dense"][(record["tenant"], record["language"])].append(
                    (grades, dense_order)
                )
                rankings_by_type["dense"][request_type].append((grades, dense_order))
                if hard_negative_candidates:
                    hard_negative_ranks["dense"].append(
                        any(ordered[idx].pk in hard_negative_candidates for idx in dense_order[:5])
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
                rankings_by_type["hybrid"][request_type].append((grades, hybrid_order))
                if hard_negative_candidates:
                    hard_negative_ranks["hybrid"].append(
                        any(ordered[idx].pk in hard_negative_candidates for idx in hybrid_order[:5])
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
                        "request_type": request_type,
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
            progress.item(done)
            labels_progress.item(done)
        progress.finish()
        labels_progress.finish()
        ranking_result = {}
        for mode in ("lexical", "dense", "hybrid"):
            by_variant = {}
            variant_samples = defaultdict(list)
            all_rows = [item for samples in rankings[mode].values() for item in samples]
            for key, samples in rankings[mode].items():
                by_variant[f"{key[0]}:{key[1]}"] = cls._rank_metrics(samples)
                variant_samples[key[1]].extend(samples)
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
            ranking_result[mode]["per_request_type"] = {
                request_type: cls._rank_metrics(samples)
                for request_type, samples in sorted(rankings_by_type[mode].items())
            }
            ranking_result[mode]["per_variant"] = {
                variant: cls._rank_metrics(samples)
                for variant, samples in sorted(variant_samples.items())
            }
            negative_samples = hard_negative_ranks[mode]
            ranking_result[mode]["hard_negatives"] = {
                "false_positive_rate@5": round(sum(negative_samples) / len(negative_samples), 4)
                if negative_samples
                else 0.0,
                "sample_count": len(negative_samples),
            }
            if mode in {"dense", "hybrid"} and embedder is None:
                ranking_result[mode] = {
                    "status": "SKIPPED",
                    "reason": "no local embedder available",
                    "per_tenant_language": {},
                    "per_variant": {},
                    "per_request_type": {
                        request_type: cls._rank_metrics(samples)
                        for request_type, samples in sorted(rankings_by_type[mode].items())
                    },
                    "hard_negatives": {
                        "false_positive_rate@5": 0.0,
                        "sample_count": len(hard_negative_ranks[mode]),
                    },
                }
        topic_ids = {
            str(record["issue_id"]): record.get("topic", record["group"]) for record in records
        }
        topic_clusters = []
        proposed_issue_ids = set()
        emerging_ids = {
            record["issue_id"] for record in records if record.get("emerging_topic_sample")
        }
        topic_by_tenant = {}
        progress = ProgressReporter("topics", len(tenants), progress_every, log_file)
        progress.start()
        for done, (tenant, organization) in enumerate(tenants.items(), start=1):
            proposals = cluster_recent_unidentified(
                Issue.objects.filter(organization=organization, is_synthetic=True)
            )
            clusters = [
                [str(issue_id) for issue_id in proposal["issue_ids"]] for proposal in proposals
            ]
            proposed_issue_ids.update(
                issue_id for proposal in proposals for issue_id in proposal["issue_ids"]
            )
            topic_clusters.extend(clusters)
            topic_by_tenant[tenant] = {
                "cluster_count": len(clusters),
                "purity": topic_cluster_purity(clusters, topic_ids),
            }
            progress.item(done)
        progress.finish()
        mask_totals = {"true_positive": 0, "false_positive": 0, "false_negative": 0}
        altered_lookalikes = []
        sensitive_types = ("otp", "card", "account", "nid", "email", "phone")
        mask_by_type = {
            category: {"true_positive": 0, "false_positive": 0, "false_negative": 0}
            for category in sensitive_types
        }
        progress = ProgressReporter("masking", len(records), progress_every, log_file)
        progress.start()
        for done, record in enumerate(records, start=1):
            issue = issues[record["issue_id"]]
            expected = set(record.get("mask_categories", []))
            detected = {
                category for category, marker in SENSITIVE.items() if marker in issue.description
            }
            altered = [
                token for token in record.get("must_not_mask", []) if token not in issue.description
            ]
            if altered:
                altered_lookalikes.append({"issue_id": issue.pk, "substrings": altered})
            mask_totals["true_positive"] += len(expected & detected)
            mask_totals["false_positive"] += len(detected - expected)
            mask_totals["false_negative"] += len(expected - detected)
            for category in sensitive_types:
                mask_by_type[category]["true_positive"] += int(
                    category in expected and category in detected
                )
                mask_by_type[category]["false_positive"] += int(
                    category not in expected and category in detected
                )
                mask_by_type[category]["false_negative"] += int(
                    category in expected and category not in detected
                )
            progress.item(done)
        progress.finish()
        tp, fp, fn = (
            mask_totals[key] for key in ("true_positive", "false_positive", "false_negative")
        )
        masking = {
            **mask_totals,
            "precision": round(tp / (tp + fp), 4) if tp + fp else 1.0,
            "recall": round(tp / (tp + fn), 4) if tp + fn else 1.0,
            "per_type": {
                category: {
                    **totals,
                    "precision": round(
                        totals["true_positive"]
                        / (totals["true_positive"] + totals["false_positive"]),
                        4,
                    )
                    if totals["true_positive"] + totals["false_positive"]
                    else 1.0,
                    "recall": round(
                        totals["true_positive"]
                        / (totals["true_positive"] + totals["false_negative"]),
                        4,
                    )
                    if totals["true_positive"] + totals["false_negative"]
                    else 1.0,
                }
                for category, totals in mask_by_type.items()
            },
            "altered_must_not_mask": altered_lookalikes,
        }
        return {
            "dataset_revision": "p7t9-live",
            "sample_count": len(records),
            "ranking": ranking_result,
            "labels": {
                **label_metrics(labels_report),
                "per_request_type": {
                    request_type: label_metrics(
                        [item for item in labels_report if item["request_type"] == request_type]
                    )
                    for request_type in sorted({item["request_type"] for item in labels_report})
                },
            },
            "topics": {
                "purity": topic_cluster_purity(topic_clusters, topic_ids),
                "emerging_samples": len(emerging_ids),
                "emerging_samples_proposed": len(emerging_ids & proposed_issue_ids),
                "emerging_proposal_coverage": round(
                    len(emerging_ids & proposed_issue_ids) / len(emerging_ids), 4
                )
                if emerging_ids
                else 0.0,
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
        lines.extend(["", "## Hard-negative ranking", ""])
        for method, metrics in result["ranking"].items():
            negative = metrics.get("hard_negatives", {})
            lines.append(
                f"{method}: false-positive rate@5 "
                f"{negative.get('false_positive_rate@5', 0.0):.4f} "
                f"({negative.get('sample_count', 0)} samples)."
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
                "",
                "| Sensitive type | Precision | Recall | TP | FP | FN |",
                "|---|---:|---:|---:|---:|---:|",
                *[
                    f"| {category} | {metrics['precision']:.4f} | {metrics['recall']:.4f} | "
                    f"{metrics['true_positive']} | {metrics['false_positive']} | "
                    f"{metrics['false_negative']} |"
                    for category, metrics in result["masking"]["per_type"].items()
                ],
                f"Topic cluster purity: {result['topics']['purity']:.4f}.",
                f"Emerging topic proposal coverage: "
                f"{result['topics']['emerging_proposal_coverage']:.4f} "
                f"({result['topics']['emerging_samples_proposed']}/"
                f"{result['topics']['emerging_samples']}).",
                "",
            ]
        )
        return "\n".join(lines)
