from pathlib import Path
from typing import Self

from pydantic import Field, field_validator

from mcp_common import BaseServiceSettings, ToolSettings


class FilesystemSettings(BaseServiceSettings):
    filesystem_root_dir: Path = Field(alias="FILESYSTEM_ROOT_DIR")
    ignore_patterns: list[str] = Field(
        default_factory=list,
        alias="FILESYSTEM_IGNORE_PATTERNS",
    )
    max_inline_size: int = Field(default=5 * 1024 * 1024, alias="FILESYSTEM_MAX_INLINE_SIZE")
    max_base64_size: int = Field(default=1 * 1024 * 1024, alias="FILESYSTEM_MAX_BASE64_SIZE")
    max_search_results: int = Field(default=1000, alias="FILESYSTEM_MAX_SEARCH_RESULTS")
    max_searchable_size: int = Field(
        default=10 * 1024 * 1024,
        alias="FILESYSTEM_MAX_SEARCHABLE_SIZE",
    )
    tools: ToolSettings = Field(default_factory=ToolSettings)

    @field_validator("filesystem_root_dir")
    @classmethod
    def validate_root_dir(cls, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not resolved.exists():
            raise ValueError(f"Root directory does not exist: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"Root path is not a directory: {resolved}")
        return resolved

    @classmethod
    def from_env(cls) -> Self:
        return cls()  # type: ignore[call-arg]
