# AGENTS.md

## Project Overview

This repository contains a small Python 3.12+ MCP monorepo built around HTTP-first MCP servers using `FastMCP`.

Current services:

- `filesystem-mcp`: local filesystem MCP server rooted to one configured directory
- `navidrome-mcp`: Navidrome/Subsonic MCP server
- `slskd-mcp`: slskd REST MCP server
- `mcp-common`: shared auth, config, HTTP, typing, formatting, and tool-registration helpers

All services are exposed over HTTP:

- MCP transport at `/mcp`
- health endpoint at `/healthz`

The repository publishes Docker images to `ghcr.io/cofob/mcps/<service>`.

## Essential Commands

### Development Setup

```bash
# Sync the entire workspace, including dev dependencies
uv sync --all-packages --group dev
```

### Code Quality

```bash
# Lint
uv run ruff check .

# Type-check
uv run mypy packages services tests

# Run tests
uv run pytest
```

### Running Services

```bash
# Navidrome MCP
uv run --package navidrome-mcp navidrome-mcp

# slskd MCP
uv run --package slskd-mcp slskd-mcp

# Filesystem MCP
uv run --package filesystem-mcp filesystem-mcp
```

### Docker

```bash
# Build one image
docker build -f docker/navidrome.Dockerfile .
docker build -f docker/slskd.Dockerfile .
docker build -f docker/filesystem.Dockerfile .
```

## Architecture

### Workspace Layout

- `packages/mcp_common`: shared infrastructure
- `services/navidrome_mcp`: Navidrome MCP server
- `services/slskd_mcp`: slskd MCP server
- `services/filesystem_mcp`: filesystem MCP server
- `tests`: shared and service-specific tests
- `docker`: per-service Dockerfiles
- `.github/workflows/ci.yml`: lint, type-check, test, and image publishing workflow

### Service Pattern

Each service follows the same structure:

- `config.py`: Pydantic settings
- `app.py`: `FastMCP` construction, tool registration, HTTP app wiring
- `__main__.py`: process entrypoint
- client or service layer:
  - remote API services use a typed client (`NavidromeClient`, `SlskdClient`)
  - local filesystem logic lives in `FilesystemService`
- `tools/`: MCP tool methods grouped by workflow
- `formatters.py`: LLM-readable string output
- `models.py`: typed data models

### Shared Infrastructure

`mcp_common` owns the common pieces:

- `auth.py`: optional OAuth2 bearer token verification for `/mcp`
- `config.py`: shared server config and tool gating
- `http.py`: async `httpx` helpers and upstream error mapping
- `json_utils.py`: typed JSON helpers and `TypeGuard`-based narrowing
- `mcp_http.py`: Starlette wrapper that mounts the MCP app and `/healthz`
- `tool_registry.py`: config-driven MCP tool enable/disable logic
- `types.py`: shared JSON and query param typing

## Key Patterns

### 1. HTTP-first MCP

This repository is not stdio-first. Services are intended to be deployed as HTTP MCP servers.

Expected contract:

- `mcp.http_app(path="/mcp")`
- parent Starlette app built through `mcp_common.build_http_app(...)`
- no double application of `/mcp`

### 2. LLM-readable Tool Outputs

Tools should return concise, readable text instead of raw upstream JSON whenever possible.

Preferred pattern:

- parse upstream payload into typed models or validated dictionaries
- normalize inconsistent upstream structures
- render stable human/LLM-readable text in `formatters.py`

Do not expose raw API envelopes unless there is a strong reason to preserve them.

### 3. Strict Typing

The repository uses strict `mypy` and a broad Ruff ruleset.

Rules to preserve:

- no `Any`
- no `object` for loose payload plumbing
- no deep relative imports
- no `from __future__ import annotations`
- prefer shared JSON helpers and `TypeGuard` narrowing over ad hoc casts

When handling JSON:

- use `JsonValue`, `JsonObject`, and `JsonArray`
- use `expect_object`, `expect_array`, `get_object`, `get_object_list`, `get_str`, `get_int`, `get_bool`
- if narrowing is useful, use the `is_json_*` guards from `mcp_common.json_utils`

### 4. Tool Registration

Tools are registered explicitly in each service `app.py`.

Pattern:

- build tool classes around a client/service object
- wrap each exposed method in a `ToolSpec`
- register through `register_enabled_tools(...)`

This keeps the MCP surface stable and allows config-driven tool disabling.

### 5. Config-driven Tool Gating

All services support:

- `enabled_tools`
- `disabled_tools`
- `disabled_tool_groups`

These are used to build read-only or reduced deployments without changing code.

If you add a tool:

1. register it in the service app
2. place it into sensible groups such as `read`, `mutate`, `search`, `playlist`, `downloads`, `files`, or `directory`
3. document it in the root `README.md`

### 6. Optional OAuth2

MCP auth is optional and applied at app construction time.

Current supported mode:

- `MCP_AUTH_MODE=oauth2`
- `OAUTH2={"strategy":"bearer",...}`

OAuth is an HTTP transport concern here. Do not bolt it on as unrelated middleware without confirming it still works with the FastMCP app lifecycle.

## Service-specific Notes

### Navidrome

- Uses the Subsonic-compatible API exposed by Navidrome
- Auth is per-request using Subsonic token auth
- Outputs should stay normalized because upstream shapes vary between artist/album/song/playlist responses
- Local source reference: `/Users/cofob/Development/navidrome`

When adding or changing Navidrome behavior:

- keep tools workflow-oriented
- merge only tools with genuinely similar inputs and semantics
- prefer readable catalog/playlist summaries over raw payload dumps

### slskd

- Uses the slskd REST API
- Auth supports API key or username/password session flow
- Search results should remain optimized for agent use: readable, flattened, actionable
- Local source reference: `/Users/cofob/Development/slskd`

When adding or changing slskd behavior:

- avoid over-merging unrelated actions into one tool
- preserve clear separation between create/list/get/cancel/delete flows
- keep download actions explicit

### Filesystem

- Constrained to `FILESYSTEM_ROOT_DIR`
- All reads and writes must remain confined to that root
- `patch_file` must never allow escaping the configured root
- Local reference server: `/Users/cofob/Development/mcp-filesystem-server`

When adding filesystem behavior:

- validate every path through the shared resolution/confinement flow
- reject directory traversal and symlink escapes
- keep output readable, especially for file reads and search results

## Testing Expectations

For any non-trivial change, run:

```bash
uv run ruff check .
uv run mypy packages services tests
uv run pytest
```

Test guidance:

- put shared tests in `tests/common`
- put service-specific tests under `tests/<service_name>`
- test formatter output when tool output shape changes
- test auth/config behavior when config surface changes
- test confinement behavior for filesystem writes and patching

## CI/CD

GitHub Actions workflow:

- lints with Ruff
- type-checks with mypy
- runs pytest
- builds and publishes service images to GHCR

Published image targets:

- `ghcr.io/cofob/mcps/navidrome-mcp`
- `ghcr.io/cofob/mcps/slskd-mcp`
- `ghcr.io/cofob/mcps/filesystem-mcp`

If you change image names, ports, or entrypoints, update both:

- `README.md`
- `.github/workflows/ci.yml`

## Documentation Expectations

Keep the root `README.md` current when changing:

- service descriptions
- tool names or signatures
- deployment instructions
- OAuth2 configuration
- image names
- environment variables

The README is intended to be an operator-facing document. `AGENTS.md` is the coding and repository workflow guide.
