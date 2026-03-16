from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class FileReadResult:
    path: str
    absolute_path: str
    mime_type: str
    size: int
    is_text: bool
    is_image: bool
    text: str | None = None
    binary_base64: str | None = None


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    path: str
    is_dir: bool
    size: int
    modified: datetime


@dataclass(frozen=True)
class FileMetadata:
    path: str
    absolute_path: str
    size: int
    created: datetime
    modified: datetime
    accessed: datetime
    is_directory: bool
    is_file: bool
    permissions: str


@dataclass(frozen=True)
class SearchFileMatch:
    path: str
    absolute_path: str
    is_dir: bool


@dataclass(frozen=True)
class SearchWithinMatch:
    path: str
    absolute_path: str
    line_number: int
    line_content: str


@dataclass(frozen=True)
class TreeNode:
    name: str
    path: str
    is_dir: bool
    size: int
    modified: datetime
    children: list["TreeNode"] = field(default_factory=list)
