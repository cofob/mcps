import calendar
import difflib
import json
import re
import subprocess
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path

from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.models import (
    ExportChatEntry,
    ExportFileEntry,
    ExportReadResult,
    ExportSearchMatch,
    ExportTopicEntry,
)


class TgExportTxtService:
    def __init__(self, settings: TgExportTxtSettings) -> None:
        self._settings = settings
        self._root_dir = settings.export_root_dir
        self._rg_path = settings.rg_path

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def resolve_path(self, requested_path: str) -> Path:
        normalized = requested_path.strip() or "."
        raw_candidate = Path(normalized).expanduser()
        candidate = raw_candidate if raw_candidate.is_absolute() else (self._root_dir / raw_candidate)
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"Path does not exist: {candidate}") from exc
        if not resolved.is_relative_to(self._root_dir):
            raise ValueError(f"Access denied outside export root: {resolved}")
        return resolved

    def display_path(self, path: Path) -> str:
        if path == self._root_dir:
            return "."
        return str(path.relative_to(self._root_dir))

    def read_export_file(self, path: str, *, start_line: int = 1, max_lines: int | None = None) -> ExportReadResult:
        resolved = self.resolve_path(path)
        if resolved.is_dir():
            raise ValueError("Cannot read a directory.")
        if resolved.suffix != ".txt":
            raise ValueError("Only .txt export files can be read.")
        effective_max_lines = max_lines or self._settings.max_read_lines
        if start_line <= 0:
            raise ValueError("start_line must be greater than 0.")
        if effective_max_lines <= 0:
            raise ValueError("max_lines must be greater than 0.")

        lines = resolved.read_text(encoding="utf-8").splitlines()
        start_index = start_line - 1
        selected_lines = lines[start_index : start_index + effective_max_lines]
        end_line = start_line + max(len(selected_lines) - 1, 0)
        content = "\n".join(selected_lines)
        return ExportReadResult(
            path=self.display_path(resolved),
            absolute_path=str(resolved),
            start_line=start_line,
            end_line=end_line,
            total_lines=len(lines),
            content=content,
        )

    def list_export_files(
        self,
        path: str = ".",
        *,
        max_results: int | None = None,
    ) -> tuple[list[ExportFileEntry], bool]:
        resolved = self.resolve_path(path)
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")

        entries: list[ExportFileEntry] = []
        if resolved.is_file():
            if resolved.suffix != ".txt":
                raise ValueError("Only .txt export files can be listed.")
            entries.append(self._build_file_entry(resolved))
            return entries, False

        candidates = sorted(candidate for candidate in resolved.rglob("*.txt") if candidate.is_file())
        limited = len(candidates) > effective_max_results
        entries.extend(self._build_file_entry(candidate) for candidate in candidates[:effective_max_results])
        return entries, limited

    def list_chats(self, *, max_results: int | None = None) -> tuple[list[ExportChatEntry], bool]:
        chats = self._load_chat_entries()
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")
        limited = len(chats) > effective_max_results
        return chats[:effective_max_results], limited

    def search_chats(self, query: str, *, max_results: int | None = None) -> tuple[list[ExportChatEntry], bool]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty.")

        chats = self._load_chat_entries()
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")

        matches = self._fuzzy_match_entries(
            chats,
            normalized_query,
            key_parts=lambda chat: (chat.chat_id, chat.chat_name),
        )
        limited = len(matches) > effective_max_results
        return matches[:effective_max_results], limited

    def list_topics(self, chat_id: str, *, max_results: int | None = None) -> tuple[list[ExportTopicEntry], bool]:
        normalized_chat_id = chat_id.strip()
        if not normalized_chat_id:
            raise ValueError("chat_id must not be empty.")

        topics_path = self.resolve_path(str(Path("chats") / normalized_chat_id / "topics.txt"))
        topics = self._load_topic_entries(topics_path)
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")
        limited = len(topics) > effective_max_results
        return topics[:effective_max_results], limited

    def search_topics(
        self,
        chat_id: str,
        query: str,
        *,
        max_results: int | None = None,
    ) -> tuple[list[ExportTopicEntry], bool]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty.")

        topics, _ = self.list_topics(chat_id, max_results=None)
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")

        matches = self._fuzzy_match_entries(
            topics,
            normalized_query,
            key_parts=lambda topic: (topic.topic_id, topic.topic_name),
        )
        limited = len(matches) > effective_max_results
        return matches[:effective_max_results], limited

    def search_exports(
        self,
        path: str,
        query: str,
        *,
        max_results: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> tuple[list[ExportSearchMatch], bool]:
        resolved = self.resolve_path(path)
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")
        start_bound, end_bound = self._parse_date_bounds(start_date, end_date)
        search_paths, use_glob = self._resolve_search_paths(
            resolved,
            start_bound=start_bound,
            end_bound=end_bound,
        )
        if not search_paths:
            return [], False

        command = [
            self._rg_path,
            "--json",
            "--line-number",
            "--max-count",
            str(effective_max_results),
            "--color=never",
            "--smart-case",
            *(["--glob", "*.txt"] if use_glob else []),
            query,
            *(str(search_path) for search_path in search_paths),
        ]
        matches: list[ExportSearchMatch] = []
        limited = False
        wait_completed = False

        try:
            process: subprocess.Popen[str] = subprocess.Popen(  # noqa: S603
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            raise ValueError(f"rg executable not found: {self._rg_path}") from exc

        try:
            stdout = process.stdout
            stderr = process.stderr
            if stdout is None or stderr is None:
                raise ValueError("rg did not provide stdout/stderr pipes")

            for line in self._iter_rg_output(stdout):
                maybe_match = self._parse_search_match(line)
                if maybe_match is None:
                    continue
                matches.append(maybe_match)
                if len(matches) >= effective_max_results:
                    limited = True
                    process.terminate()
                    break

            stderr_output = stderr.read()
            return_code = process.wait()
            wait_completed = True
        finally:
            if not wait_completed and process.poll() is None:
                process.kill()
                process.wait()

        if not limited and return_code not in {0, 1}:
            message = stderr_output.strip() or "rg failed"
            raise ValueError(message)

        return matches, limited

    def _resolve_search_paths(
        self,
        resolved: Path,
        *,
        start_bound: date | None = None,
        end_bound: date | None = None,
    ) -> tuple[list[Path], bool]:
        if resolved.is_file():
            if resolved.suffix != ".txt":
                raise ValueError("Only .txt export files can be searched.")
            if not self._matches_date_bounds(resolved, start_bound=start_bound, end_bound=end_bound):
                return [], False
            return [resolved], False

        if start_bound is None and end_bound is None:
            return [resolved], True

        return sorted(
            (
                candidate
                for candidate in resolved.rglob("*.txt")
                if candidate.is_file()
                and self._matches_date_bounds(candidate, start_bound=start_bound, end_bound=end_bound)
            ),
            key=self.display_path,
            reverse=True,
        ), False

    def _parse_date_bounds(
        self,
        start_date: str | None,
        end_date: str | None,
    ) -> tuple[date | None, date | None]:
        start_bound = self._parse_optional_date(start_date, field_name="start_date")
        end_bound = self._parse_optional_date(end_date, field_name="end_date")
        if start_bound is not None and end_bound is not None and start_bound > end_bound:
            raise ValueError("start_date must be less than or equal to end_date.")
        return start_bound, end_bound

    def _parse_optional_date(self, value: str | None, *, field_name: str) -> date | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        try:
            return date.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc

    def _matches_date_bounds(
        self,
        path: Path,
        *,
        start_bound: date | None,
        end_bound: date | None,
    ) -> bool:
        if start_bound is None and end_bound is None:
            return True

        bucket_range = self._extract_bucket_date_range(path)
        if bucket_range is None:
            return False

        bucket_start, bucket_end = bucket_range
        if start_bound is not None and bucket_end < start_bound:
            return False
        return end_bound is None or bucket_start <= end_bound

    def _extract_bucket_date_range(self, path: Path) -> tuple[date, date] | None:
        match = re.fullmatch(r"(\d{4})-(\d{2})-w([1-5])", path.stem)
        if match is None:
            return None

        year = int(match.group(1))
        month = int(match.group(2))
        week = int(match.group(3))
        last_day = calendar.monthrange(year, month)[1]
        start_day = ((week - 1) * 7) + 1
        end_day = min(week * 7, last_day)
        return date(year, month, start_day), date(year, month, end_day)

    def _fuzzy_match_entries[T](
        self,
        entries: list[T],
        query: str,
        *,
        key_parts: Callable[[T], tuple[str, ...]],
    ) -> list[T]:
        lowered_query = query.casefold()
        scored_matches: list[tuple[tuple[int, int, int], T]] = []

        for index, entry in enumerate(entries):
            parts = tuple(part.casefold() for part in key_parts(entry))
            haystack = " ".join(parts)
            if not haystack:
                continue

            substring_score = int(any(lowered_query in part for part in parts))
            ratio_score = int(difflib.SequenceMatcher(None, lowered_query, haystack).ratio() * 1000)
            token_score = max(
                (int(difflib.SequenceMatcher(None, lowered_query, part).ratio() * 1000) for part in parts),
                default=0,
            )
            score = max(ratio_score, token_score)
            if substring_score == 0 and score < 400:
                continue

            scored_matches.append(((substring_score, score, -index), entry))

        scored_matches.sort(reverse=True)
        return [entry for _, entry in scored_matches]

    def _build_file_entry(self, path: Path) -> ExportFileEntry:
        return ExportFileEntry(
            path=self.display_path(path),
            absolute_path=str(path),
            size_bytes=path.stat().st_size,
        )

    def _load_chat_entries(self) -> list[ExportChatEntry]:
        chats_path = self._root_dir / "chats.txt"
        if not chats_path.exists():
            raise ValueError(f"Chat mapping file does not exist: {chats_path}")

        chats: list[ExportChatEntry] = []
        for line in chats_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            chat_id, separator, chat_name = line.partition("\t")
            if not separator:
                continue
            chats.append(ExportChatEntry(chat_id=chat_id, chat_name=chat_name))
        return chats

    def _load_topic_entries(self, topics_path: Path) -> list[ExportTopicEntry]:
        if not topics_path.exists():
            raise ValueError(f"Topic mapping file does not exist: {topics_path}")

        topics: list[ExportTopicEntry] = []
        for line in topics_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            topic_id, separator, topic_name = line.partition("\t")
            if not separator:
                continue
            topics.append(ExportTopicEntry(topic_id=topic_id, topic_name=topic_name))
        return topics

    def _iter_rg_output(self, stdout: Iterator[str]) -> Iterator[str]:
        yield from stdout

    def _parse_search_match(self, line: str) -> ExportSearchMatch | None:
        payload = json.loads(line)
        if payload.get("type") != "match":
            return None

        data = payload.get("data", {})
        path_data = data.get("path", {})
        line_number = data.get("line_number")
        lines_data = data.get("lines", {})
        text_data = lines_data.get("text")
        if not isinstance(line_number, int) or not isinstance(text_data, str):
            return None

        absolute_path = Path(path_data.get("text", "")).resolve()
        if not absolute_path.is_relative_to(self._root_dir):
            return None

        return ExportSearchMatch(
            path=self.display_path(absolute_path),
            absolute_path=str(absolute_path),
            line_number=line_number,
            line_text=text_data.rstrip("\n"),
        )
