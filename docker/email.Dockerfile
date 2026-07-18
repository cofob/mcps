FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY uv.lock ./
COPY packages ./packages
COPY services ./services
COPY src ./src

RUN uv sync --frozen --no-dev --package email-mcp

FROM python:3.12-slim AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends gnupg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

RUN useradd --create-home --home-dir /home/appuser --shell /usr/sbin/nologin --uid 10001 appuser \
    && chown -R appuser:appuser /app /home/appuser

ENV HOST=0.0.0.0
ENV PORT=8084

EXPOSE 8084

USER appuser

CMD ["/app/.venv/bin/email-mcp", "--transport", "http"]
