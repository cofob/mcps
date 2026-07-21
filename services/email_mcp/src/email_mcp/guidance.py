from importlib.resources import files

EMAIL_MCP_INSTRUCTIONS = """
Email tools operate on private mail and can send messages to external recipients.

Mandatory behavior:
- Call mail-reading tools only when the user directly asks to list, browse, search, find, check, or read that mail or
  mail configuration. This includes email_list_accounts, email_list_folders, email_list_messages,
  email_search_messages, and email_get_thread. Never inspect mail proactively.
- Before every email_send_message or email_reply_message call, present the exact proposed account, resolved From
  address, To/Cc/Bcc recipients, subject, complete text and HTML message bodies, attachment names, and signing choice,
  then ask for
  explicit confirmation. For a reply, also show the source folder and UID and whether reply-all is enabled. Do not
  treat an earlier request to draft, reply, or send as confirmation of the final rendered message.
- Confirmation authorizes one exact send call only. If the account, From address, recipient, subject, body, attachment,
  or signing choice changes, show the revised complete draft and ask again.
- Never retry email_send_message or email_reply_message after SMTP submission may have started; report ambiguous
  delivery status.
- Message reads are read-only and use folder-scoped UIDs. Do not infer that a UID belongs to another folder.

Read skill://email-mcp/usage for detailed search, sending, attachment, and OpenPGP/MIME guidance.
""".strip()


def email_usage_skill() -> str:
    return files("email_mcp").joinpath("resources", "email-usage", "SKILL.md").read_text(encoding="utf-8")
