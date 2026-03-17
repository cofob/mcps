from dataclasses import dataclass


@dataclass(frozen=True)
class ExportReadResult:
    path: str
    absolute_path: str
    start_line: int
    end_line: int
    total_lines: int
    content: str


@dataclass(frozen=True)
class ExportSearchMatch:
    path: str
    absolute_path: str
    line_number: int
    line_text: str


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
