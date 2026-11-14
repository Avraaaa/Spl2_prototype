# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6 AS uvbin
FROM python:3.13-slim
COPY --from=uvbin /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
WORKDIR /workspace
COPY . /workspace/
# Core inference image is intentionally small; Phase P5 provisions an approved local model extra.
RUN uv sync --locked --no-dev --package datasoft-ml
ENV PATH="/workspace/.venv/bin:$PATH"
EXPOSE 8001
CMD ["uv", "run", "--no-sync", "--package", "datasoft-ml", "uvicorn", "app.main:app", "--app-dir", "services/ml", "--host", "0.0.0.0", "--port", "8001"]
