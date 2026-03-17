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
