# MCP Servers

This repository contains three HTTP MCP servers implemented in Python 3.12+ with `uv`, `FastMCP`, strict `mypy`, and `ruff`.

Every server exposes:

- MCP over `http://<host>:<port>/mcp`
- health check over `http://<host>:<port>/healthz`

Repository: `cofob/mcps`  
Container namespace: `ghcr.io/cofob/mcps/<service>`

## Navigation

- [Services](#services)
- [Development](#development)
- [Running Locally](#running-locally)
- [Deployment](#deployment)
- [HTTP Endpoints](#http-endpoints)
- [Configuration](#configuration)
- [Service Notes](#service-notes)
- [CI/CD](#cicd)

## Services

### `navidrome-mcp`

MCP server for [Navidrome](https://www.navidrome.org/) using the Subsonic-compatible API.

Primary use cases:

- search artists, albums, and tracks
- fetch artist, album, track, and playlist details
- list artists, albums, playlists, starred items, random tracks, and tracks by genre
- set ratings
- like and unlike items
- create, update, and delete playlists

Implemented against the local Navidrome source tree at `/Users/cofob/Development/navidrome`.

Exposed tools:

- `navidrome_search`
- `navidrome_get_artist`
- `navidrome_get_album`
- `navidrome_get_track`
- `navidrome_get_playlist`
- `navidrome_list_artists`
- `navidrome_list_albums`
- `navidrome_list_playlists`
- `navidrome_list_starred`
- `navidrome_list_random_tracks`
- `navidrome_list_tracks_by_genre`
- `navidrome_rate`
- `navidrome_like`
- `navidrome_unlike`
- `navidrome_create_playlist`
- `navidrome_update_playlist`
- `navidrome_delete_playlist`

Tool inputs and outputs:

- `navidrome_search(query: str, search_type: str = "all", limit: int = 10) -> str`
  Input: search text, optional result type filter (`all`, `artists`, `albums`, `tracks`), optional per-type limit.
  Output: readable search summary with artist, album, and track sections.
- `navidrome_get_artist(artist_id: str) -> str`
  Input: Navidrome/Subsonic artist id.
  Output: readable artist card with normalized metadata.
- `navidrome_get_album(album_id: str) -> str`
  Input: Navidrome/Subsonic album id.
  Output: readable album card with normalized metadata.
- `navidrome_get_track(track_id: str) -> str`
  Input: Navidrome/Subsonic track id.
  Output: readable track card with normalized metadata.
- `navidrome_get_playlist(playlist_id: str) -> str`
  Input: playlist id.
  Output: readable playlist summary with metadata and entries.
- `navidrome_list_artists(music_folder_id: str | None = None) -> str`
  Input: optional music folder id.
  Output: readable artist listing.
- `navidrome_list_albums(list_type: str, genre: str | None = None, from_year: int | None = None, to_year: int | None = None, size: int = 10, offset: int = 0) -> str`
  Input: Subsonic album list mode plus optional filters and pagination.
  Output: readable album listing.
- `navidrome_list_playlists() -> str`
  Input: none.
  Output: readable playlist list.
- `navidrome_list_starred(music_folder_id: str | None = None) -> str`
  Input: optional music folder id.
  Output: readable grouped starred items summary.
- `navidrome_list_random_tracks(size: int = 10, genre: str | None = None) -> str`
  Input: number of tracks and optional genre filter.
  Output: readable random track list.
- `navidrome_list_tracks_by_genre(genre: str, count: int = 10, offset: int = 0) -> str`
  Input: genre name plus count and offset.
  Output: readable track list for that genre.
- `navidrome_rate(item_type: str, item_id: str, rating: int) -> str`
  Input: item type label for the response text, item id, rating from `0` to `5`.
  Output: short mutation confirmation string.
- `navidrome_like(item_type: str, item_ids: list[str]) -> str`
  Input: item type (`artist`, `album`, `track`) and one or more ids.
  Output: short mutation confirmation string.
- `navidrome_unlike(item_type: str, item_ids: list[str]) -> str`
  Input: item type (`artist`, `album`, `track`) and one or more ids.
  Output: short mutation confirmation string.
- `navidrome_create_playlist(name: str, song_ids: list[str] | None = None) -> str`
  Input: playlist name and optional initial track ids.
  Output: short creation summary including playlist id.
- `navidrome_update_playlist(playlist_id: str, name: str | None = None, comment: str | None = None, public: bool | None = None, song_ids_to_add: list[str] | None = None, song_indexes_to_remove: list[int] | None = None) -> str`
  Input: playlist id and any combination of metadata or track updates.
  Output: short update confirmation string.
- `navidrome_delete_playlist(playlist_id: str) -> str`
  Input: playlist id.
  Output: short deletion confirmation string.

### `slskd-mcp`

MCP server for [slskd](https://github.com/slskd/slskd) using the slskd REST API.

Primary use cases:

- create and inspect searches
- view readable search results
- inspect users and browse user shares
- request downloads
- inspect downloads, queue positions, uploads, and files
- cancel or clear transfers

Implemented against the local slskd source tree at `/Users/cofob/Development/slskd`.

Exposed tools:

- `slskd_create_search`
- `slskd_list_searches`
- `slskd_get_search`
- `slskd_get_search_results`
- `slskd_cancel_search`
- `slskd_delete_search`
- `slskd_get_user`
- `slskd_browse_user`
- `slskd_request_downloads`
- `slskd_list_downloads`
- `slskd_get_download`
- `slskd_get_download_queue_position`
- `slskd_cancel_download`
- `slskd_clear_completed_downloads`
- `slskd_list_uploads`
- `slskd_get_upload`
- `slskd_list_files`

Tool inputs and outputs:

- `slskd_create_search(search_text: str, response_limit: int = 100, file_limit: int = 10000, search_timeout: int = 15, filter_responses: bool = True, minimum_response_file_count: int = 1, maximum_peer_queue_length: int = 1000000, minimum_peer_upload_speed: int = 0) -> str`
  Input: search text and slskd search tuning parameters.
  Output: short confirmation with the created search id.
- `slskd_list_searches() -> str`
  Input: none.
  Output: readable list of tracked searches with ids and search text.
- `slskd_get_search(search_id: UUID) -> str`
  Input: search UUID.
  Output: short readable summary for one search.
- `slskd_get_search_results(search_id: UUID, search_type: str = "all", output_format: str = "both", limit: int = 50) -> str`
  Input: search UUID and display controls.
  Output: readable flattened file result list, intended for choosing download candidates.
- `slskd_cancel_search(search_id: UUID) -> str`
  Input: search UUID.
  Output: short cancellation confirmation string.
- `slskd_delete_search(search_id: UUID) -> str`
  Input: search UUID.
  Output: short deletion confirmation string.
- `slskd_get_user(action: str, username: str, directory: str | None = None) -> str`
  Input: `action` of `status`, `info`, `endpoint`, or `directory`; username; optional directory for `directory` action.
  Output: readable summary prefixed by the action name.
- `slskd_browse_user(username: str) -> str`
  Input: username.
  Output: readable browse tree summary.
- `slskd_request_downloads(username: str, files: list[SlskdDownloadRequest]) -> str`
  Input: username and one or more file requests, each containing `filename` and `size`.
  Output: confirmation plus slskd response summary.
- `slskd_list_downloads(include_removed: bool = False) -> str`
  Input: whether removed downloads should be included.
  Output: readable downloads summary.
- `slskd_get_download(username: str, transfer_id: str) -> str`
  Input: username and transfer id.
  Output: readable download summary.
- `slskd_get_download_queue_position(username: str, transfer_id: str) -> str`
  Input: username and transfer id.
  Output: readable queue position summary.
- `slskd_cancel_download(username: str, transfer_id: str, remove: bool = False) -> str`
  Input: username, transfer id, and optional `remove` flag.
  Output: short cancellation confirmation string.
- `slskd_clear_completed_downloads() -> str`
  Input: none.
  Output: short confirmation string.
- `slskd_list_uploads(include_removed: bool = False) -> str`
  Input: whether removed uploads should be included.
  Output: readable uploads summary.
- `slskd_get_upload(username: str, transfer_id: str) -> str`
  Input: username and transfer id.
  Output: readable upload summary.
- `slskd_list_files(location: str, subdirectory: str | None = None, recursive: bool = False) -> str`
  Input: `location` of `downloads` or `incomplete`, optional subdirectory, optional recursive listing.
  Output: readable directory summary.

### `filesystem-mcp`

Filesystem MCP server for one configured root directory. It is based on the patterns used in the other servers in this repository and reimplements the reference server at `/Users/cofob/Development/mcp-filesystem-server` in Python.

Primary use cases:

- read files and file metadata
- list directories and directory trees
- search by filename and inside files
- write, copy, move, delete, and modify files
- apply unified diff patches with `patch_file`

Safety properties:

- all reads and writes are confined to `FILESYSTEM_ROOT_DIR`
- paths matching `FILESYSTEM_IGNORE_PATTERNS` or any nested `.gitignore` file are excluded from every filesystem tool
- symlink and path traversal escapes outside the configured root are rejected
- `patch_file` is restricted to files under the configured root in the same way as every other write tool

Exposed tools:

- `read_file`
- `read_multiple_files`
- `list_directory`
- `create_directory`
- `tree`
- `list_allowed_directories`
- `get_file_info`
- `search_files`
- `search_within_files`
- `write_file`
- `copy_file`
- `move_file`
- `delete_file`
- `modify_file`
- `patch_file`

Tool inputs and outputs:

- `read_file(path: str) -> str`
  Input: one path under `FILESYSTEM_ROOT_DIR`.
  Output: readable file view with text content inline when allowed, otherwise metadata and encoding details.
- `read_multiple_files(paths: list[str]) -> str`
  Input: multiple paths under `FILESYSTEM_ROOT_DIR`.
  Output: readable multi-file report.
- `list_directory(path: str) -> str`
  Input: one directory path.
  Output: readable directory listing.
- `create_directory(path: str) -> str`
  Input: directory path to create.
  Output: short creation confirmation string.
- `tree(path: str, depth: int = 3, follow_symlinks: bool = False) -> str`
  Input: root path, tree depth, and optional symlink traversal.
  Output: readable directory tree.
- `list_allowed_directories() -> str`
  Input: none.
  Output: readable list of configured accessible roots.
- `get_file_info(path: str) -> str`
  Input: file or directory path.
  Output: readable metadata summary including timestamps, type, size, and permissions.
- `search_files(path: str, pattern: str) -> str`
  Input: root path and filename glob pattern.
  Output: readable list of matching file and directory names.
- `search_within_files(path: str, substring: str, depth: int = 0, max_results: int = 1000) -> str`
  Input: root path, plain-text substring, optional depth, optional result cap.
  Output: readable match list with file paths and line numbers.
- `write_file(path: str, content: str) -> str`
  Input: target path and full file content.
  Output: short write confirmation with byte count.
- `copy_file(source: str, destination: str) -> str`
  Input: source path and destination path.
  Output: short copy confirmation string.
- `move_file(source: str, destination: str) -> str`
  Input: source path and destination path.
  Output: short move confirmation string.
- `delete_file(path: str, recursive: bool = False) -> str`
  Input: target path and optional recursive flag for directories.
  Output: short deletion confirmation string.
- `modify_file(path: str, find: str, replace: str, all_occurrences: bool = True, regex: bool = False) -> str`
  Input: target path, find text or pattern, replacement text, and matching controls.
  Output: short summary with replacement count.
- `patch_file(path: str, patch: str) -> str`
  Input: target path and unified diff patch text.
  Output: short summary with changed line count.

## Development

### Requirements

- Python 3.12+
- `uv`

### Install

```bash
uv sync --all-packages --group dev
```

### Quality gates

```bash
uv run ruff check .
uv run mypy packages services tests
uv run pytest
```

## Running Locally

Run each server from the workspace root with the required environment variables set.

### Navidrome

```bash
export NAVIDROME_URL="https://navidrome.example.com"
export NAVIDROME_USERNAME="alice"
export NAVIDROME_PASSWORD="secret"
export HOST="0.0.0.0"
export PORT="8080"

uv run --package navidrome-mcp navidrome-mcp
```

### slskd

API key mode:

```bash
export SLSKD_URL="https://slskd.example.com"
export SLSKD_API_KEY="your-api-key"
export HOST="0.0.0.0"
export PORT="8081"

uv run --package slskd-mcp slskd-mcp
```

Username/password mode:

```bash
export SLSKD_URL="https://slskd.example.com"
export SLSKD_USERNAME="alice"
export SLSKD_PASSWORD="secret"
export HOST="0.0.0.0"
export PORT="8081"

uv run --package slskd-mcp slskd-mcp
```

### Filesystem

```bash
export FILESYSTEM_ROOT_DIR="/srv/data"
export HOST="0.0.0.0"
export PORT="8082"

uv run --package filesystem-mcp filesystem-mcp
```

## Deployment

Each service has a dedicated Dockerfile under [docker](/Users/cofob/.codex/worktrees/4b01/mcps/docker), and CI builds and publishes images from [.github/workflows/ci.yml](/Users/cofob/.codex/worktrees/4b01/mcps/.github/workflows/ci.yml).

Expected image names for this repository:

- `ghcr.io/cofob/mcps/navidrome-mcp`
- `ghcr.io/cofob/mcps/slskd-mcp`
- `ghcr.io/cofob/mcps/filesystem-mcp`

### Example `docker run`

Navidrome:

```bash
docker run --rm -p 8080:8080 \
  -e NAVIDROME_URL="https://navidrome.example.com" \
  -e NAVIDROME_USERNAME="alice" \
  -e NAVIDROME_PASSWORD="secret" \
  ghcr.io/cofob/mcps/navidrome-mcp:latest
```

slskd:

```bash
docker run --rm -p 8081:8081 \
  -e SLSKD_URL="https://slskd.example.com" \
  -e SLSKD_API_KEY="your-api-key" \
  ghcr.io/cofob/mcps/slskd-mcp:latest
```

filesystem:

```bash
docker run --rm -p 8082:8082 \
  -e FILESYSTEM_ROOT_DIR="/workspace" \
  -v "$PWD:/workspace" \
  ghcr.io/cofob/mcps/filesystem-mcp:latest
```

## HTTP Endpoints

For every service:

- `GET /healthz` returns JSON health data
- `POST /mcp` serves the MCP transport

Example health response:

```json
{
  "status": "ok",
  "service": "navidrome-mcp",
  "version": "0.1.0"
}
```

## Configuration

### Common environment variables

All services support:

- `HOST`
- `PORT`
- `LOG_LEVEL`
- `TIMEOUT_SECONDS`
- `MCP_AUTH_MODE`

Defaults:

- `HOST=0.0.0.0`
- `PORT=8080` unless the container sets a service-specific default
- `LOG_LEVEL=INFO`
- `TIMEOUT_SECONDS=20.0`
- `MCP_AUTH_MODE=none`

### Tool configuration

Tool gating is shared across all services.

Available settings:

- `enabled_tools`
- `disabled_tools`
- `disabled_tool_groups`

These are currently loaded through the nested `TOOLS` settings object. In practice, set them as JSON:

```bash
export TOOLS='{"disabled_tool_groups":["mutate"]}'
```

Examples:

Disable all mutating tools:

```bash
export TOOLS='{"disabled_tool_groups":["mutate"]}'
```

Allow only a small read-only subset:

```bash
export TOOLS='{"enabled_tools":["navidrome_search","navidrome_get_album","navidrome_get_track"]}'
```

Disable one specific tool:

```bash
export TOOLS='{"disabled_tools":["patch_file"]}'
```

Precedence:

1. `enabled_tools` acts as an allowlist when set
2. `disabled_tool_groups` disables matching tool groups
3. `disabled_tools` disables named tools

### OAuth2 for `/mcp`

OAuth2 MCP authentication is optional and is disabled by default.

To enable it:

```bash
export MCP_AUTH_MODE="oauth2"
export OAUTH2='{
  "strategy":"bearer",
  "issuer_url":"https://auth.example.com/",
  "jwks_uri":"https://auth.example.com/.well-known/jwks.json",
  "audience":"mcps"
}'
```

Notes:

- only bearer-token verification is implemented
- `issuer_url`, `jwks_uri`, and `audience` are required for OAuth2 mode
- because `oauth2` is a nested settings model, it is configured through the `OAUTH2` JSON value

### Navidrome configuration

Required:

- `NAVIDROME_URL`
- `NAVIDROME_USERNAME`
- `NAVIDROME_PASSWORD`

Optional:

- `NAVIDROME_CLIENT_NAME`  
  Default: `navidrome-mcp`
- `NAVIDROME_API_VERSION`  
  Default: `1.16.1`

### slskd configuration

Required:

- `SLSKD_URL`
- one of:
  - `SLSKD_API_KEY`
  - `SLSKD_USERNAME` and `SLSKD_PASSWORD`

### Filesystem configuration

Required:

- `FILESYSTEM_ROOT_DIR`

Optional:

- `FILESYSTEM_IGNORE_PATTERNS`
- `FILESYSTEM_MAX_INLINE_SIZE`
- `FILESYSTEM_MAX_BASE64_SIZE`
- `FILESYSTEM_MAX_SEARCH_RESULTS`
- `FILESYSTEM_MAX_SEARCHABLE_SIZE`

Default values:

- `FILESYSTEM_IGNORE_PATTERNS=[]`
- `FILESYSTEM_MAX_INLINE_SIZE=5242880`
- `FILESYSTEM_MAX_BASE64_SIZE=1048576`
- `FILESYSTEM_MAX_SEARCH_RESULTS=1000`
- `FILESYSTEM_MAX_SEARCHABLE_SIZE=10485760`

`FILESYSTEM_IGNORE_PATTERNS` accepts a JSON array of `.gitignore`-style patterns such as
`[".git","node_modules/","*.log","secret/*.txt"]`. These rules are combined with `.gitignore`
files found in the root directory and nested subdirectories. Matching files and directories are
hidden from listings and searches and are rejected by direct read/write/modify/delete operations.

## Service Notes

### Navidrome output style

Navidrome tools return readable text for MCP clients rather than raw upstream JSON. The server normalizes mixed Subsonic response shapes into cleaner text output for albums, artists, tracks, and playlists.

### slskd output style

slskd tools return readable summaries designed for LLM use. Search result tools flatten file results into concise, actionable lists rather than returning raw API payloads.

### Filesystem resources

The filesystem server also exposes a `file://{path*}` MCP resource for files under the configured root directory.

## CI/CD

CI runs:

- `ruff`
- `mypy`
- `pytest`

Docker build and publish runs from [.github/workflows/ci.yml](/Users/cofob/.codex/worktrees/4b01/mcps/.github/workflows/ci.yml) using the Dockerfiles under [docker](/Users/cofob/.codex/worktrees/4b01/mcps/docker).
