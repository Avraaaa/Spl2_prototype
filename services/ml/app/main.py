"""Service boundary: ML inference is optional; do not send raw personal data here."""

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.masking import mask_text

app = FastAPI(title="DataSoft private NLP service", docs_url=None, redoc_url=None)


class MaskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class MaskResponse(BaseModel):
    masked_text: str
    review_required: bool = True


class EmbedResponse(BaseModel):
    enabled: bool
    reason: str | None = None


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
    response_model=EmbedResponse,
    dependencies=[Depends(service_auth)],
)
def embedding_readiness() -> EmbedResponse:
    if os.getenv("ML_MODEL_ENABLED", "0") != "1":
        return EmbedResponse(
            enabled=False,
            reason="Model deliberately disabled until approved local checkpoint is pinned",
        )
    return EmbedResponse(enabled=False, reason="Inference implementation scheduled in later phase")
