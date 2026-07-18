from collections.abc import Sequence

from email_mcp.config import EmailSettings
from email_mcp.models import MailboxFolder, MessageSummary, ParsedMessage


def format_accounts(settings: EmailSettings) -> str:
    lines = [f"Configured email accounts: {len(settings.email_accounts)}"]
    for name, account in sorted(settings.email_accounts.items()):
        identity = f"{account.from_name} <{account.from_address}>" if account.from_name else account.from_address
        lines.append(f"- {name}: {identity} (GPG signing: {'configured' if account.gpg_key_fingerprint else 'off'})")
    return "\n".join(lines)


def format_folders(account: str, folders: Sequence[MailboxFolder]) -> str:
    lines = [f"Folders for account {account}: {len(folders)}"]
    for folder in folders:
        flags = f" [{', '.join(folder.flags)}]" if folder.flags else ""
        lines.append(f"- {folder.name}{flags}")
    return "\n".join(lines)


def format_messages(account: str, folder: str, messages: Sequence[MessageSummary]) -> str:
    lines = [f"Messages in {account}/{folder}: {len(messages)}"]
    for index, message in enumerate(messages, start=1):
        lines.append(f"{index}. {message.subject or '(no subject)'}")
        lines.append(f"   uid: {message.uid}")
        lines.append(f"   from: {message.sender or '(unknown)'}")
        if message.date:
            lines.append(f"   date: {message.date}")
        if message.flags:
            lines.append(f"   flags: {', '.join(message.flags)}")
        lines.append(f"   size: {message.size_bytes} bytes")
    return "\n".join(lines)


def format_message(account: str, folder: str, message: ParsedMessage) -> str:
    summary = message.summary
    lines = [
        f"Message {account}/{folder} UID {summary.uid}",
        f"- subject: {summary.subject or '(no subject)'}",
        f"- from: {summary.sender or '(unknown)'}",
        f"- to: {summary.recipients or '(none)'}",
    ]
    if message.cc:
        lines.append(f"- cc: {message.cc}")
    if summary.date:
        lines.append(f"- date: {summary.date}")
    if summary.message_id:
        lines.append(f"- message-id: {summary.message_id}")
    if summary.flags:
        lines.append(f"- flags: {', '.join(summary.flags)}")
    lines.extend([f"- size: {summary.size_bytes} bytes", f"- body format: {message.body_format}"])
    if message.attachments:
        lines.extend(["", "Attachments"])
        for attachment in message.attachments:
            lines.append(
                f"- [{attachment.index}] {attachment.filename} "
                f"({attachment.content_type}, {attachment.size_bytes} bytes, {attachment.disposition})"
            )
            if attachment.content_id:
                lines.append(f"  content-id: {attachment.content_id}")
    lines.extend(["", "Body", message.body or "(empty)"])
    return "\n".join(lines)


def format_sent(
    account: str,
    message_id: str,
    recipients: Sequence[str],
    *,
    signed: bool,
    attachment_count: int,
) -> str:
    return "\n".join(
        [
            f"Email sent from account {account}.",
            f"- message-id: {message_id}",
            f"- recipients: {', '.join(recipients)}",
            f"- attachments: {attachment_count}",
            f"- OpenPGP/MIME signed: {str(signed).lower()}",
        ]
    )
