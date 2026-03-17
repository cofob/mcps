import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

from tg_export_txt_mcp.config import TgExportTxtSettings
from tg_export_txt_mcp.models import ExportReadResult, ExportSearchMatch


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

    def search_exports(
        self,
        path: str,
        query: str,
        *,
        max_results: int | None = None,
    ) -> tuple[list[ExportSearchMatch], bool]:
        resolved = self.resolve_path(path)
        effective_max_results = max_results or self._settings.max_search_results
        if effective_max_results <= 0:
            raise ValueError("max_results must be greater than 0.")

        command = [
            self._rg_path,
            "--json",
            "--line-number",
            "--max-count",
            str(effective_max_results),
            "--color=never",
            "--smart-case",
            "--glob",
            "*.txt",
            query,
            str(resolved),
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
