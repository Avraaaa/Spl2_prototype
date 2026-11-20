"""Service boundary: ML inference is optional; do not send raw personal data here."""

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.masking import mask_text
from app.ranking import semantic_scores

app = FastAPI(title="DataSoft private NLP service", docs_url=None, redoc_url=None)


class MaskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class MaskResponse(BaseModel):
    masked_text: str
    review_required: bool = True


class ReadinessResponse(BaseModel):
    enabled: bool
    reason: str | None = None


class EmbeddingRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=100)


class EmbeddingResponse(BaseModel):
    vectors: list[list[float]]


class RankRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20000)
    candidates: list[str] = Field(min_length=1, max_length=50)


class RankResponse(BaseModel):
    scores: list[float]


def service_auth(x_service_token: str | None = Header(default=None)) -> None:
    import secrets

    required = os.getenv("ML_SHARED_TOKEN", "")
    if not required or not secrets.compare_digest(x_service_token or "", required):
        raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "ml": "disabled" if os.getenv("ML_MODEL_ENABLED", "0") != "1" else "configured",
    }


@app.post("/internal/mask", response_model=MaskResponse, dependencies=[Depends(service_auth)])
def mask(payload: MaskRequest) -> MaskResponse:
    return MaskResponse(masked_text=mask_text(payload.text))


@app.get(
    "/internal/embedding-readiness",
    response_model=ReadinessResponse,
    dependencies=[Depends(service_auth)],
)
def embedding_readiness() -> ReadinessResponse:
    if os.getenv("ML_MODEL_ENABLED", "0") != "1":
        return ReadinessResponse(
            enabled=False,
            reason="Model deliberately disabled until approved local checkpoint is pinned",
        )
    try:
        from app.embedding import load_local_sentence_transformer

        load_local_sentence_transformer()
    except Exception as exc:
        return ReadinessResponse(enabled=False, reason=type(exc).__name__)
    return ReadinessResponse(enabled=True)


@app.post("/internal/embed", response_model=EmbeddingResponse, dependencies=[Depends(service_auth)])
def embed(payload: EmbeddingRequest) -> EmbeddingResponse:
    try:
        from app.embedding import load_local_sentence_transformer

        model = load_local_sentence_transformer()
        vectors = model.encode(
            [mask_text(text) for text in payload.texts], normalize_embeddings=True
        )
        return EmbeddingResponse(vectors=[[float(value) for value in vector] for vector in vectors])
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Local model unavailable: {type(exc).__name__}"
        ) from exc


@app.post("/internal/rank", response_model=RankResponse, dependencies=[Depends(service_auth)])
def rank(payload: RankRequest) -> RankResponse:
    try:
        scores = semantic_scores(
            mask_text(payload.query), [mask_text(item) for item in payload.candidates]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Local model unavailable: {type(exc).__name__}"
        ) from exc
    return RankResponse(scores=scores)
