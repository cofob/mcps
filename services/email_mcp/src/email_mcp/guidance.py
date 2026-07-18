from importlib.resources import files

EMAIL_MCP_INSTRUCTIONS = """
Email tools operate on private mail and can send messages to external recipients.

Mandatory behavior:
- Call email_list_accounts, email_list_folders, email_list_messages, or email_search_messages only when the user
  directly asks to list, browse, search, find, or check mail or mail configuration. Never inspect mail proactively.
- Before every email_send_message call, present the exact proposed From account, To/Cc/Bcc recipients, subject,
  complete text and HTML message bodies, attachment names, and signing choice, then ask the user for explicit
  confirmation. Do not treat an earlier request to draft or send as confirmation of the final rendered message.
- Confirmation authorizes one exact send call only. If any recipient, subject, body, attachment, or signing choice
  changes, show the revised complete draft and ask again.
- Never retry email_send_message after SMTP submission may have started; report ambiguous delivery status.
- Message reads are read-only and use folder-scoped UIDs. Do not infer that a UID belongs to another folder.

Read skill://email-mcp/usage for detailed search, sending, attachment, and OpenPGP/MIME guidance.
""".strip()


def email_usage_skill() -> str:
    return files("email_mcp").joinpath("resources", "email-usage", "SKILL.md").read_text(encoding="utf-8")
