"""Optional local semantic ranking; never downloads weights or calls external APIs."""

from collections.abc import Sequence

from app.embedding import load_local_sentence_transformer


def semantic_scores(query: str, candidates: Sequence[str]) -> list[float]:
    model = load_local_sentence_transformer()
    vectors = model.encode([query, *candidates], normalize_embeddings=True)
    query_vector = vectors[0]
    return [
        sum(float(left) * float(right) for left, right in zip(query_vector, vector, strict=False))
        for vector in vectors[1:]
    ]
