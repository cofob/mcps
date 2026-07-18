# email-mcp

Email MCP server using standard IMAP for reading and SMTP for sending. It supports multiple named accounts, verified
implicit TLS or STARTTLS, MIME attachments, and optional OpenPGP/MIME signatures.

All IMAP mailbox selection is read-only and message fetches use PEEK semantics. Listing, searching, reading, and
downloading attachments never mark messages as read.

## Tools

- `email_list_accounts`: list configured account names, From identities, and whether signing is configured
- `email_list_folders`: list IMAP folders
- `email_list_messages`: page through messages newest UID first
- `email_search_messages`: combine sender, recipient, subject, text, date, and unread filters
- `email_get_message`: read normalized headers, text body, and attachment metadata by folder-scoped UID
- `email_get_attachment`: return one indexed attachment as an MCP binary `EmbeddedResource`
- `email_send_message`: send text/HTML email with attachments and optional OpenPGP/MIME signing

Every tool that accesses mail requires an explicit `account` name.
For maximum portability across IMAP servers, textual search filters currently accept ASCII text.

## Agent Usage Policy

The server publishes mandatory agent instructions and a detailed Markdown skill resource at
`skill://email-mcp/usage`. The resource covers consent boundaries, folder-scoped UIDs, efficient search filters,
attachments, SMTP failure handling, and OpenPGP/MIME signing.

- Agents may call account, folder, or message list tools and `email_search_messages` only when the user directly asks
  to list, browse, search, find, or check mail or mail configuration. They must not inspect mail proactively.
- Before every `email_send_message` call, the agent must show the exact account, recipients, subject, complete text and
  HTML bodies, attachment names, and resolved signing choice, then obtain explicit confirmation in a subsequent turn.
- Confirmation applies to one exact message. Any change requires a new complete preview and confirmation.
- Because SMTP submission is non-idempotent, agents must not automatically retry a send whose delivery status may be
  ambiguous.

## Account Configuration

The recommended local setup is the interactive installer, which offers provider presets, masked credential prompts,
system-keyring storage, and non-sending IMAP/SMTP validation:

```bash
uvx --from 'git+https://github.com/cofob/mcps.git' install
```

The manual environment format remains available for containers and custom deployments.

Set `EMAIL_ACCOUNTS` to a JSON object. Passwords are represented as Pydantic secrets and are never included in account
list output or logs.

```bash
export EMAIL_ACCOUNTS='{
  "personal": {
    "imap_host": "imap.example.com",
    "imap_port": 993,
    "imap_tls": "implicit",
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_tls": "starttls",
    "username": "alice@example.com",
    "password": "app-password",
    "smtp_username": "optional-separate-relay-user",
    "smtp_password": "optional-separate-relay-password",
    "from_address": "alice@example.com",
    "from_name": "Alice",
    "gpg_key_fingerprint": "0123456789ABCDEF0123456789ABCDEF01234567",
    "gpg_home": "/home/alice/.gnupg"
  }
}'
```

`smtp_username` and `smtp_password` must either both be present or both be omitted. When omitted, SMTP uses the shared
username/password. Plaintext protocol connections and disabled certificate verification are not supported.

## Attachments

Incoming message output lists stable attachment indexes. `email_get_attachment` returns the selected bytes as an MCP
blob with the original MIME type. Outgoing attachments are JSON objects:

```json
{
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "content_base64": "JVBERi0xLjQK...",
  "disposition": "attachment",
  "content_id": null
}
```

Use `disposition: "inline"` plus `content_id` for an inline MIME part. Server-local attachment paths are intentionally
not accepted, so behavior is identical over stdio and HTTP.

## OpenPGP/MIME Signing

When an account has `gpg_key_fingerprint`, `email_send_message` signs by default. Pass `sign=false` to send that message
unsigned. Pass `sign=true` to require signing explicitly. A missing key or any GPG error aborts before SMTP submission.

The fingerprint must be the full 40- or 64-character fingerprint. The service invokes `EMAIL_GPG_BINARY` (`gpg` by
default) against the account's `gpg_home`, or the process's normal GPG home when omitted. Private keys and unlocking are
managed externally by the GPG keyring and gpg-agent; the MCP does not accept private keys or passphrases. In containers,
mount a writable GPG home or a correctly configured agent socket for UID 10001. The email image includes `gnupg`.

## Limits

- `EMAIL_MAX_RESULTS=100`
- `EMAIL_MAX_BODY_CHARS=100000`
- `EMAIL_MAX_MESSAGE_BYTES=26214400`
- `EMAIL_MAX_ATTACHMENT_BYTES=10485760`
- `EMAIL_MAX_TOTAL_ATTACHMENT_BYTES=20971520`
- `EMAIL_MAX_RECIPIENTS=50`
- `EMAIL_GPG_BINARY=gpg`

## Running

Stdio is the default:

```bash
uv run --package email-mcp email-mcp
```

HTTP mode exposes `/mcp` and `/healthz`:

```bash
uv run --package email-mcp email-mcp --transport http
```
