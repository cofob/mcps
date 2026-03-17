FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY services/tg_export_txt_mcp ./services/tg_export_txt_mcp

RUN uv sync --package tg-export-txt-mcp

FROM python:3.12-slim AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

RUN useradd --create-home --home-dir /home/appuser --shell /usr/sbin/nologin --uid 10001 appuser \
    && chown -R appuser:appuser /app

ENV HOST=0.0.0.0
ENV PORT=8085

EXPOSE 8085

USER appuser

CMD ["/app/.venv/bin/tg-export-txt-mcp"]
