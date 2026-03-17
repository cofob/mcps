from tg_export_txt_mcp.formatters import format_cli_result
from tg_export_txt_mcp.service import TgExportTxtService


class CliTools:
    def __init__(self, service: TgExportTxtService) -> None:
        self._service = service

    async def run_cli(self, command: str, cwd: str = ".") -> str:
        """Run one raw Bash command line inside the Telegram export root.

        How it works:
        - Runs ``bash -lc <command>`` with ``cwd`` resolved inside the configured
          export root.
        - The command line is passed through to Bash directly, so pipes, redirects,
          command substitution, and chaining are available.
        - Prefer this tool over the higher-level search helpers when you need full-text
          search across many files, exact raw ``rg`` behavior, or shell composition
          such as ``rg ... | head`` and ``rg ... | sed ...``.

        How to call it:
        - Search a chat directory:
          ``run_cli(command="rg refund chats/-1001234567890", cwd=".")``
        - Read a slice of a transcript:
          ``run_cli(command="sed -n '1,40p' chats/-1001234567890/2026-03-w3.txt")``
        - Inspect a directory:
          ``run_cli(command="find chats/-1001234567890 -maxdepth 2 -type f")``
        - Combine shell tools directly:
          ``run_cli(command="rg refund chats | head -20")``

        What it returns:
        - A plain-text block with the command, working directory, exit code, stdout,
          and stderr.
        - Very large output is truncated at the configured
          ``TG_EXPORT_TXT_MAX_CLI_OUTPUT_CHARS`` limit.
        """
        return format_cli_result(self._service.run_cli(command, cwd=cwd))
