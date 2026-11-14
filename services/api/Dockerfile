# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6 AS uvbin
FROM python:3.13-slim
COPY --from=uvbin /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY . /workspace/
RUN uv sync --locked --no-dev --package datasoft-api
ENV PATH="/workspace/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "--package", "datasoft-api", "gunicorn", "--chdir", "services/api", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
