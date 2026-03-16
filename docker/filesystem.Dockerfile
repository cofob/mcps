FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml ./
COPY packages ./packages
COPY services/filesystem_mcp ./services/filesystem_mcp

RUN uv sync --package filesystem-mcp

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /app /app

ENV HOST=0.0.0.0
ENV PORT=8082

EXPOSE 8082

CMD ["uv", "run", "--package", "filesystem-mcp", "filesystem-mcp"]
