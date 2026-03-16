FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY services/slskd_mcp ./services/slskd_mcp

RUN uv sync --package slskd-mcp

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /app /app

ENV HOST=0.0.0.0
ENV PORT=8081

EXPOSE 8081

CMD ["uv", "run", "--package", "slskd-mcp", "slskd-mcp"]

