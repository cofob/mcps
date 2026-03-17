from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ExportReadResult:
    path: str
    absolute_path: str
    start_line: int
    end_line: int
    total_lines: int
    content: str


@dataclass(frozen=True)
class CliCommandResult:
    command: str
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    truncated: bool


@dataclass(frozen=True)
class ExportSearchMatch:
    path: str
    absolute_path: str
    line_number: int
    line_text: str
    chat_id: str | None
    topic_id: str | None
    bucket_label: str | None
    bucket_start: date | None
    bucket_end: date | None
    rank_score: int


@dataclass(frozen=True)
class ExportFileEntry:
    path: str
    absolute_path: str
    size_bytes: int


@dataclass(frozen=True)
class ExportChatEntry:
    chat_id: str
    chat_name: str


@dataclass(frozen=True)
class ExportTopicEntry:
    topic_id: str
    topic_name: str
