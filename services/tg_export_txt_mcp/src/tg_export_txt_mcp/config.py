from pathlib import Path
from typing import Self

from pydantic import Field, field_validator

from mcp_common import BaseServiceSettings, ToolSettings


class TgExportTxtSettings(BaseServiceSettings):
    export_root_dir: Path = Field(alias="TG_EXPORT_TXT_ROOT_DIR")
    rg_path: str = Field(default="rg", alias="TG_EXPORT_TXT_RG_PATH")
    max_read_lines: int = Field(default=400, alias="TG_EXPORT_TXT_MAX_READ_LINES")
    max_search_results: int = Field(default=200, alias="TG_EXPORT_TXT_MAX_SEARCH_RESULTS")
    tools: ToolSettings = Field(default_factory=ToolSettings)

    @field_validator("export_root_dir")
    @classmethod
    def validate_export_root_dir(cls, value: Path) -> Path:
        resolved = value.expanduser().resolve()
        if not resolved.exists():
            raise ValueError(f"Export root directory does not exist: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"Export root path is not a directory: {resolved}")
        return resolved

    @field_validator("max_read_lines", "max_search_results")
    @classmethod
    def validate_positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Expected a positive integer.")
        return value

    @classmethod
    def from_env(cls) -> Self:
        return cls()  # type: ignore[call-arg]
