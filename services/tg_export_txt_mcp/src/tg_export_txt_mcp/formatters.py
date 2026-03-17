from collections.abc import Sequence

from tg_export_txt_mcp.models import (
    ExportChatEntry,
    ExportFileEntry,
    ExportReadResult,
    ExportSearchMatch,
    ExportTopicEntry,
)


def format_read_result(result: ExportReadResult) -> str:
    lines = [
        f"Path: {result.path}",
        f"Absolute path: {result.absolute_path}",
        f"Lines: {result.start_line}-{result.end_line} of {result.total_lines}",
        "",
        "Content",
        result.content,
    ]
    return "\n".join(lines)


def format_search_results(
    base_path: str,
    query: str,
    matches: Sequence[ExportSearchMatch],
    *,
    limited: bool,
) -> str:
    lines = [f'Search for "{query}" under {base_path}: {len(matches)} match(es)']
    for index, match in enumerate(matches, start=1):
        lines.append(f"{index}. {match.path}:{match.line_number}: {match.line_text}")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_search_results limit."])
    return "\n".join(lines)


def format_file_list(base_path: str, files: Sequence[ExportFileEntry], *, limited: bool) -> str:
    lines = [f"TXT files under {base_path}: {len(files)} file(s)"]
    for index, file in enumerate(files, start=1):
        lines.append(f"{index}. {file.path} ({file.size_bytes} bytes)")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_search_results limit."])
    return "\n".join(lines)


def format_chat_list(chats: Sequence[ExportChatEntry], *, limited: bool) -> str:
    lines = [f"Chats: {len(chats)} match(es)"]
    for index, chat in enumerate(chats, start=1):
        lines.append(f"{index}. {chat.chat_id}\t{chat.chat_name}")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_search_results limit."])
    return "\n".join(lines)


def format_chat_search_results(query: str, chats: Sequence[ExportChatEntry], *, limited: bool) -> str:
    lines = [f'Search chats for "{query}": {len(chats)} match(es)']
    for index, chat in enumerate(chats, start=1):
        lines.append(f"{index}. {chat.chat_id}\t{chat.chat_name}")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_search_results limit."])
    return "\n".join(lines)


def format_topic_list(chat_id: str, topics: Sequence[ExportTopicEntry], *, limited: bool) -> str:
    lines = [f"Topics for chat {chat_id}: {len(topics)} topic(s)"]
    for index, topic in enumerate(topics, start=1):
        lines.append(f"{index}. {topic.topic_id}\t{topic.topic_name}")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_search_results limit."])
    return "\n".join(lines)


def format_topic_search_results(
    chat_id: str,
    query: str,
    topics: Sequence[ExportTopicEntry],
    *,
    limited: bool,
) -> str:
    lines = [f'Search topics in chat {chat_id} for "{query}": {len(topics)} match(es)']
    for index, topic in enumerate(topics, start=1):
        lines.append(f"{index}. {topic.topic_id}\t{topic.topic_name}")
    if limited:
        lines.extend(["", "Results were truncated at the configured max_search_results limit."])
    return "\n".join(lines)
