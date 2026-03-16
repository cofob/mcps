FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY services/navidrome_mcp ./services/navidrome_mcp

RUN uv sync --package navidrome-mcp

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /app /app

ENV HOST=0.0.0.0
ENV PORT=8080

EXPOSE 8080

CMD ["uv", "run", "--package", "navidrome-mcp", "navidrome-mcp"]

