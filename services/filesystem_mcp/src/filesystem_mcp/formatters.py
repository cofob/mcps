from collections.abc import Iterable, Sequence

from filesystem_mcp.models import (
    DirectoryEntry,
    FileMetadata,
    FileReadResult,
    SearchFileMatch,
    SearchWithinMatch,
    TreeNode,
)


def _bool_text(value: bool) -> str:
    return "yes" if value else "no"


def format_file_read(result: FileReadResult) -> str:
    lines = [
        f"Path: {result.path}",
        f"Absolute path: {result.absolute_path}",
        f"MIME type: {result.mime_type}",
        f"Size: {result.size} bytes",
    ]
    if result.text is not None:
        lines.extend(["", "Content", result.text])
    elif result.binary_base64 is not None:
        lines.extend(
            [
                "",
                "Binary content",
                "The file is not plain text. Base64 content follows.",
                result.binary_base64,
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Content omitted",
                "The file is too large to inline safely.",
            ]
        )
    return "\n".join(lines)


def format_multiple_file_reads(results: Sequence[FileReadResult]) -> str:
    sections = [format_file_read(result) for result in results]
    return "\n\n---\n\n".join(sections)


def format_directory_list(path: str, entries: Sequence[DirectoryEntry]) -> str:
    lines = [f"Directory: {path}", f"Entries: {len(entries)}"]
    for index, entry in enumerate(entries, start=1):
        kind = "dir" if entry.is_dir else "file"
        lines.append(
            f"{index}. [{kind}] {entry.path} "
            f"(size={entry.size}, modified={entry.modified.isoformat()})"
        )
    return "\n".join(lines)


def _render_tree(node: TreeNode, prefix: str, is_last: bool, output: list[str]) -> None:
    branch = "└── " if is_last else "├── "
    marker = "/" if node.is_dir else ""
    output.append(f"{prefix}{branch}{node.name}{marker}")
    child_prefix = f"{prefix}{'    ' if is_last else '│   '}"
    for index, child in enumerate(node.children):
        _render_tree(child, child_prefix, index == len(node.children) - 1, output)


def format_tree(root: TreeNode) -> str:
    lines = [f"Tree for {root.path}", f"{root.name}/" if root.is_dir else root.name]
    for index, child in enumerate(root.children):
        _render_tree(child, "", index == len(root.children) - 1, lines)
    return "\n".join(lines)


def format_file_info(info: FileMetadata) -> str:
    return "\n".join(
        [
            f"Path: {info.path}",
            f"Absolute path: {info.absolute_path}",
            f"Directory: {_bool_text(info.is_directory)}",
            f"File: {_bool_text(info.is_file)}",
            f"Size: {info.size} bytes",
            f"Permissions: {info.permissions}",
            f"Created: {info.created.isoformat()}",
            f"Modified: {info.modified.isoformat()}",
            f"Accessed: {info.accessed.isoformat()}",
        ]
    )


def format_search_files(
    base_path: str,
    pattern: str,
    matches: Sequence[SearchFileMatch],
) -> str:
    lines = [f'Search results for "{pattern}" under {base_path}: {len(matches)} match(es)']
    for index, match in enumerate(matches, start=1):
        kind = "dir" if match.is_dir else "file"
        lines.append(f"{index}. [{kind}] {match.path}")
    return "\n".join(lines)


def format_search_within_files(
    base_path: str,
    substring: str,
    matches: Sequence[SearchWithinMatch],
    *,
    limited: bool,
) -> str:
    lines = [
        f'Search within files for "{substring}" under {base_path}: '
        f"{len(matches)} match(es)"
    ]
    current_path: str | None = None
    for match in matches:
        if match.path != current_path:
            current_path = match.path
            lines.extend(["", f"File: {match.path}"])
        lines.append(f"  Line {match.line_number}: {match.line_content}")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_results limit."])
    return "\n".join(lines)


def format_allowed_directories(paths: Iterable[str]) -> str:
    resolved = list(paths)
    lines = [f"Allowed directories: {len(resolved)}"]
    for index, path in enumerate(resolved, start=1):
        lines.append(f"{index}. {path}")
    return "\n".join(lines)


def format_summary(summary: str) -> str:
    return summary
