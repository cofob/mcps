import calendar
import difflib
import fnmatch
import json
import re
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.models import (
    CliCommandResult,
    ExportChatEntry,
    ExportFileEntry,
    ExportReadResult,
    ExportSearchMatch,
    ExportTopicEntry,
)


@dataclass(frozen=True)
class ExportPathMetadata:
    path: str
    absolute_path: str
    chat_id: str | None
    topic_id: str | None
    bucket_label: str | None
    bucket_start: date | None
    bucket_end: date | None


@dataclass(frozen=True)
class ExportSearchOptions:
    query: str
    max_results: int
    candidate_limit: int
    start_bound: date | None
    end_bound: date | None
    chat_id: str | None
    topic_id: str | None
    path_prefix: str | None
    filename_glob: str | None
    case_sensitive: bool
    whole_word: bool


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

    def run_cli(self, command: str, *, cwd: str = ".") -> CliCommandResult:
        normalized_command = command.strip()
        if not normalized_command:
            raise ValueError("command must not be empty.")

        resolved_cwd = self.resolve_path(cwd)
        if not resolved_cwd.is_dir():
            raise ValueError("cwd must resolve to a directory.")

        completed = subprocess.run(  # noqa: S603
            ["/bin/bash", "-lc", normalized_command],
            cwd=resolved_cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self._settings.timeout_seconds,
            check=False,
        )
        stdout, stderr, truncated = self._truncate_cli_output(completed.stdout, completed.stderr)
        return CliCommandResult(
            command=normalized_command,
            cwd=self.display_path(resolved_cwd),
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            truncated=truncated,
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

    def search_exports(  # noqa: PLR0913
        self,
        path: str,
        query: str,
        *,
        max_results: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        chat_id: str | None = None,
        topic_id: str | None = None,
        path_prefix: str | None = None,
        filename_glob: str | None = None,
        case_sensitive: bool = False,
        whole_word: bool = False,
    ) -> tuple[list[ExportSearchMatch], bool]:
        resolved = self.resolve_path(path)
        options = self._build_search_options(
            query=query,
            max_results=max_results,
            start_date=start_date,
            end_date=end_date,
            chat_id=chat_id,
            topic_id=topic_id,
            path_prefix=path_prefix,
            filename_glob=filename_glob,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )
        search_paths, use_glob = self._resolve_search_paths(
            resolved,
            options,
        )
        if not search_paths:
            return [], False

        command = self._build_search_command(search_paths, options, use_glob=use_glob)
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
                maybe_match = self._parse_search_match(line, query=options.query)
                if maybe_match is None:
                    continue
                if not self._matches_search_filters(maybe_match, options):
                    continue
                matches.append(maybe_match)
                if len(matches) >= options.candidate_limit:
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

        matches.sort(key=self._search_match_sort_key, reverse=True)
        limited = limited or len(matches) > options.max_results
        return matches[: options.max_results], limited

    def _resolve_search_paths(
        self,
        resolved: Path,
        options: ExportSearchOptions,
    ) -> tuple[list[Path], bool]:
        use_explicit_paths = any(
            value is not None
            for value in (
                options.start_bound,
                options.end_bound,
                options.chat_id,
                options.topic_id,
                options.path_prefix,
                options.filename_glob,
            )
        )
        if resolved.is_file():
            if resolved.suffix != ".txt":
                raise ValueError("Only .txt export files can be searched.")
            metadata = self._extract_path_metadata(resolved)
            if not self._matches_path_filters(metadata, options):
                return [], False
            return [resolved], False

        if not use_explicit_paths:
            return [resolved], True

        candidates = [
            candidate
            for candidate in resolved.rglob("*.txt")
            if candidate.is_file()
            and self._matches_path_filters(self._extract_path_metadata(candidate), options)
        ]
        candidates.sort(key=self.display_path, reverse=True)
        return candidates, False

    def _build_search_options(  # noqa: PLR0913
        self,
        *,
        query: str,
        max_results: int | None,
        start_date: str | None,
        end_date: str | None,
        chat_id: str | None,
        topic_id: str | None,
        path_prefix: str | None,
        filename_glob: str | None,
        case_sensitive: bool,
        whole_word: bool,
    ) -> ExportSearchOptions:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty.")
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")
        start_bound, end_bound = self._parse_date_bounds(start_date, end_date)
        return ExportSearchOptions(
            query=normalized_query,
            max_results=effective_max_results,
            candidate_limit=max(effective_max_results * 10, effective_max_results),
            start_bound=start_bound,
            end_bound=end_bound,
            chat_id=self._normalize_optional_filter(chat_id, field_name="chat_id"),
            topic_id=self._normalize_optional_filter(topic_id, field_name="topic_id"),
            path_prefix=self._normalize_optional_filter(path_prefix, field_name="path_prefix"),
            filename_glob=self._normalize_optional_filter(filename_glob, field_name="filename_glob"),
            case_sensitive=case_sensitive,
            whole_word=whole_word,
        )

    def _build_search_command(
        self,
        search_paths: list[Path],
        options: ExportSearchOptions,
        *,
        use_glob: bool,
    ) -> list[str]:
        return [
            self._rg_path,
            "--json",
            "--line-number",
            "--max-count",
            str(options.candidate_limit),
            "--color=never",
            *(["--case-sensitive"] if options.case_sensitive else ["--smart-case"]),
            *(["--word-regexp"] if options.whole_word else []),
            *(["--glob", "*.txt"] if use_glob else []),
            options.query,
            *(str(search_path) for search_path in search_paths),
        ]

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
        normalized_query = self._normalize_search_text(query)
        raw_query = query.casefold()
        query_tokens = tuple(token for token in normalized_query.split() if token)
        scored_matches: list[tuple[tuple[int, int, int, int, int, int], T]] = []

        for index, entry in enumerate(entries):
            raw_parts = tuple(part for part in key_parts(entry) if part)
            if not raw_parts:
                continue
            normalized_parts = tuple(self._normalize_search_text(part) for part in raw_parts)
            raw_lower_parts = tuple(part.casefold() for part in raw_parts)
            normalized_pairs = tuple(zip(normalized_parts, raw_lower_parts, strict=True))
            exact_score = int(
                any(
                    normalized_query == part or raw_query == raw_part
                    for part, raw_part in normalized_pairs
                )
            )
            prefix_score = int(
                any(
                    part.startswith(normalized_query) or raw_part.startswith(raw_query)
                    for part, raw_part in normalized_pairs
                )
            )
            token_match_score = int(
                any(
                    query_tokens and all(token in part.split() for token in query_tokens)
                    for part in normalized_parts
                )
            )
            substring_score = int(
                any(
                    normalized_query in part or raw_query in raw_part
                    for part, raw_part in normalized_pairs
                )
            )
            haystack = " ".join(normalized_parts)
            ratio_score = int(difflib.SequenceMatcher(None, normalized_query, haystack).ratio() * 1000)
            token_score = max(
                (
                    int(difflib.SequenceMatcher(None, normalized_query, part).ratio() * 1000)
                    for part in normalized_parts
                ),
                default=0,
            )
            score = max(ratio_score, token_score)
            if substring_score == 0 and score < 400:
                continue

            scored_matches.append(
                ((exact_score, prefix_score, token_match_score, substring_score, score, -index), entry)
            )

        scored_matches.sort(reverse=True)
        return [entry for _, entry in scored_matches]

    def _normalize_optional_filter(self, value: str | None, *, field_name: str) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")
        return normalized

    def _truncate_cli_output(self, stdout: str, stderr: str) -> tuple[str, str, bool]:
        limit = self._settings.max_cli_output_chars
        combined = len(stdout) + len(stderr)
        if combined <= limit:
            return stdout, stderr, False

        stdout_budget = min(len(stdout), limit // 2)
        stderr_budget = min(len(stderr), limit - stdout_budget)
        return stdout[:stdout_budget], stderr[:stderr_budget], True

    def _normalize_search_text(self, value: str) -> str:
        lowered = value.casefold()
        collapsed = re.sub(r"[^\w]+", " ", lowered)
        return " ".join(collapsed.split())

    def _extract_path_metadata(self, path: Path) -> ExportPathMetadata:
        relative_path = self.display_path(path)
        parts = Path(relative_path).parts
        chat_id: str | None = None
        topic_id: str | None = None
        if len(parts) >= 3 and parts[0] == "chats":
            chat_id = parts[1]
            if len(parts) >= 4:
                topic_id = parts[2]
        bucket_range = self._extract_bucket_date_range(path)
        bucket_label = path.stem if bucket_range is not None else None
        bucket_start, bucket_end = bucket_range if bucket_range is not None else (None, None)
        return ExportPathMetadata(
            path=relative_path,
            absolute_path=str(path),
            chat_id=chat_id,
            topic_id=topic_id,
            bucket_label=bucket_label,
            bucket_start=bucket_start,
            bucket_end=bucket_end,
        )

    def _matches_path_filters(self, metadata: ExportPathMetadata, options: ExportSearchOptions) -> bool:
        prefix_matches = options.path_prefix is None or metadata.path.startswith(options.path_prefix.strip("/"))
        filename_matches = options.filename_glob is None or fnmatch.fnmatch(
            Path(metadata.path).name,
            options.filename_glob,
        )
        id_matches = (
            (options.chat_id is None or metadata.chat_id == options.chat_id)
            and (options.topic_id is None or metadata.topic_id == options.topic_id)
        )
        date_matches = self._metadata_matches_date_bounds(
            metadata,
            start_bound=options.start_bound,
            end_bound=options.end_bound,
        )
        return prefix_matches and filename_matches and id_matches and date_matches

    def _matches_search_filters(
        self,
        match: ExportSearchMatch,
        options: ExportSearchOptions,
    ) -> bool:
        metadata = ExportPathMetadata(
            path=match.path,
            absolute_path=match.absolute_path,
            chat_id=match.chat_id,
            topic_id=match.topic_id,
            bucket_label=match.bucket_label,
            bucket_start=match.bucket_start,
            bucket_end=match.bucket_end,
        )
        return self._matches_path_filters(metadata, options)

    def _metadata_matches_date_bounds(
        self,
        metadata: ExportPathMetadata,
        *,
        start_bound: date | None,
        end_bound: date | None,
    ) -> bool:
        if start_bound is None and end_bound is None:
            return True
        if metadata.bucket_start is None or metadata.bucket_end is None:
            return False
        if start_bound is not None and metadata.bucket_end < start_bound:
            return False
        return end_bound is None or metadata.bucket_start <= end_bound

    def _search_match_sort_key(self, match: ExportSearchMatch) -> tuple[int, int, int, int, int]:
        bucket_ordinal = match.bucket_start.toordinal() if match.bucket_start is not None else 0
        line_length_score = -len(match.line_text)
        line_position_score = -match.line_number
        path_specificity_score = int(match.topic_id is not None)
        return (match.rank_score, bucket_ordinal, path_specificity_score, line_length_score, line_position_score)

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

    def _parse_search_match(self, line: str, *, query: str) -> ExportSearchMatch | None:
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
        metadata = self._extract_path_metadata(absolute_path)
        line_text = text_data.rstrip("\n")

        return ExportSearchMatch(
            path=metadata.path,
            absolute_path=str(absolute_path),
            line_number=line_number,
            line_text=line_text,
            chat_id=metadata.chat_id,
            topic_id=metadata.topic_id,
            bucket_label=metadata.bucket_label,
            bucket_start=metadata.bucket_start,
            bucket_end=metadata.bucket_end,
            rank_score=self._score_search_match(metadata, line_text, query),
        )

    def _score_search_match(self, metadata: ExportPathMetadata, line_text: str, query: str) -> int:
        normalized_query = self._normalize_search_text(query)
        query_tokens = tuple(token for token in normalized_query.split() if token)
        normalized_line = self._normalize_search_text(line_text)
        normalized_path = self._normalize_search_text(metadata.path)
        whole_phrase_score = int(normalized_query in normalized_line) * 5000
        whole_word_score = int(
            bool(query_tokens)
            and all(token in normalized_line.split() for token in query_tokens)
        ) * 2000
        term_hits = sum(token in normalized_line for token in query_tokens) * 300
        line_ratio = int(difflib.SequenceMatcher(None, normalized_query, normalized_line).ratio() * 1000)
        path_ratio = int(difflib.SequenceMatcher(None, normalized_query, normalized_path).ratio() * 300)
        recency_score = metadata.bucket_start.toordinal() % 1000 if metadata.bucket_start is not None else 0
        topic_score = 100 if metadata.topic_id is not None else 0
        return whole_phrase_score + whole_word_score + term_hits + line_ratio + path_ratio + recency_score + topic_score
