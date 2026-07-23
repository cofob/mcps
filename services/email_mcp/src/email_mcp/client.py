import asyncio
import base64
import binascii
import imaplib
import re
import smtplib
import ssl
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from datetime import date
from email import policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import cast

from email_mcp.config import EmailAccountSettings, EmailSettings, TlsMode
from email_mcp.models import Attachment, MailboxFolder, MessageSummary, ParsedMessage
from mcp_common import UpstreamAuthError, UpstreamServerError, UpstreamValidationError

FetchPart = bytes | tuple[bytes, bytes] | None
FETCH_UID_PATTERN = re.compile(rb"\bUID (\d+)\b")
FETCH_SIZE_PATTERN = re.compile(rb"\bRFC822\.SIZE (\d+)\b")
FETCH_FLAGS_PATTERN = re.compile(rb"\bFLAGS \(([^)]*)\)")
LIST_PATTERN = re.compile(rb'^\((?P<flags>[^)]*)\) (?P<delimiter>NIL|"(?:\\.|[^"])*") (?P<name>.+)$')
MESSAGE_ID_PATTERN = re.compile(r"<[^<>\s]+>")


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth > 0:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "li", "tr"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        return "\n".join(line for line in lines if line).strip()


def _decode_modified_utf7(value: bytes) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        ampersand = value.find(b"&", index)
        if ampersand < 0:
            result.append(value[index:].decode("ascii", errors="replace"))
            break
        result.append(value[index:ampersand].decode("ascii", errors="replace"))
        end = value.find(b"-", ampersand)
        if end < 0:
            result.append(value[ampersand:].decode("ascii", errors="replace"))
            break
        encoded = value[ampersand + 1 : end]
        if not encoded:
            result.append("&")
        else:
            standard = encoded.replace(b",", b"/")
            padded = standard + (b"=" * (-len(standard) % 4))
            try:
                result.append(base64.b64decode(padded).decode("utf-16-be"))
            except (binascii.Error, UnicodeDecodeError):
                result.append(value[ampersand : end + 1].decode("ascii", errors="replace"))
        index = end + 1
    return "".join(result)


def _encode_modified_utf7(value: str) -> str:
    result: list[str] = []
    unicode_buffer: list[str] = []

    def flush_unicode() -> None:
        if not unicode_buffer:
            return
        encoded = base64.b64encode("".join(unicode_buffer).encode("utf-16-be")).rstrip(b"=")
        result.append("&" + encoded.replace(b"/", b",").decode("ascii") + "-")
        unicode_buffer.clear()

    for character in value:
        codepoint = ord(character)
        if 0x20 <= codepoint <= 0x7E:
            flush_unicode()
            result.append("&-" if character == "&" else character)
        else:
            unicode_buffer.append(character)
    flush_unicode()
    return "".join(result)


def _unquote_imap(value: bytes) -> bytes:
    if len(value) >= 2 and value.startswith(b'"') and value.endswith(b'"'):
        return value[1:-1].replace(b'\\"', b'"').replace(b"\\\\", b"\\")
    return value


def _decode_header(value: str | None) -> str:
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(value))).strip()
    except (LookupError, UnicodeError):
        return value.strip()


def _format_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return value.strip() or None


def _message_ids(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(dict.fromkeys(MESSAGE_ID_PATTERN.findall(value)))


def _metadata_value(pattern: re.Pattern[bytes], metadata: bytes, *, default: int = 0) -> int:
    match = pattern.search(metadata)
    return int(match.group(1)) if match is not None else default


def _metadata_flags(metadata: bytes) -> tuple[str, ...]:
    match = FETCH_FLAGS_PATTERN.search(metadata)
    if match is None:
        return ()
    return tuple(value.decode("ascii", errors="replace") for value in match.group(1).split())


def _parse_summary(metadata: bytes, header_bytes: bytes) -> MessageSummary:
    message = BytesParser(policy=policy.default).parsebytes(header_bytes, headersonly=True)
    return MessageSummary(
        uid=_metadata_value(FETCH_UID_PATTERN, metadata),
        subject=_decode_header(str(message["Subject"]) if message["Subject"] is not None else None),
        sender=_decode_header(str(message["From"]) if message["From"] is not None else None),
        recipients=_decode_header(str(message["To"]) if message["To"] is not None else None),
        date=_format_date(str(message["Date"]) if message["Date"] is not None else None),
        message_id=_decode_header(str(message["Message-ID"]) if message["Message-ID"] is not None else None) or None,
        flags=_metadata_flags(metadata),
        size_bytes=_metadata_value(FETCH_SIZE_PATTERN, metadata),
    )


def _decoded_part_bytes(part: EmailMessage) -> bytes:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    raw = part.get_payload()
    return raw.encode(part.get_content_charset() or "utf-8", errors="replace") if isinstance(raw, str) else b""


def _decoded_part_text(part: EmailMessage) -> str:
    data = _decoded_part_bytes(part)
    charset = part.get_content_charset() or "utf-8"
    try:
        return data.decode(charset, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


class EmailClient:
    def __init__(self, settings: EmailSettings) -> None:
        self._settings = settings

    def _account(self, name: str) -> EmailAccountSettings:
        try:
            return self._settings.account(name)
        except ValueError as exc:
            raise UpstreamValidationError(str(exc)) from exc

    async def validate_account(self, account_name: str) -> None:
        """Validate IMAP and SMTP authentication without changing or sending mail."""
        await asyncio.to_thread(self._validate_account, account_name)

    def _validate_account(self, account_name: str) -> None:
        account = self._account(account_name)
        with self._imap(account) as imap_connection:
            self._select(imap_connection, "INBOX")
            self._select(imap_connection, self._resolve_sent_folder(imap_connection, account))
        with self._smtp(account) as smtp_connection:
            status, _ = smtp_connection.noop()
            if status != 250:
                raise UpstreamServerError("SMTP NOOP validation failed.")

    @contextmanager
    def _imap(self, account: EmailAccountSettings) -> Iterator[imaplib.IMAP4]:
        connection: imaplib.IMAP4 | None = None
        context = ssl.create_default_context()
        try:
            if account.imap_tls is TlsMode.IMPLICIT:
                connection = imaplib.IMAP4_SSL(
                    account.imap_host,
                    account.imap_port,
                    ssl_context=context,
                    timeout=self._settings.timeout_seconds,
                )
            else:
                connection = imaplib.IMAP4(
                    account.imap_host,
                    account.imap_port,
                    timeout=self._settings.timeout_seconds,
                )
                connection.starttls(ssl_context=context)
            try:
                connection.login(account.username, account.password.get_secret_value())
            except imaplib.IMAP4.error as exc:
                raise UpstreamAuthError("IMAP authentication failed.") from exc
            yield connection
        except (UpstreamAuthError, UpstreamValidationError):
            raise
        except (imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError, TimeoutError) as exc:
            raise UpstreamServerError("IMAP operation failed.") from exc
        finally:
            if connection is not None:
                with suppress(imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError):
                    connection.logout()

    @staticmethod
    def _mailbox_argument(folder: str) -> str:
        if "\r" in folder or "\n" in folder or "\x00" in folder:
            raise UpstreamValidationError("Mailbox names must not contain control characters.")
        encoded_folder = _encode_modified_utf7(folder).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{encoded_folder}"'

    @classmethod
    def _select(cls, connection: imaplib.IMAP4, folder: str) -> None:
        status, _ = connection.select(cls._mailbox_argument(folder), readonly=True)
        if status != "OK":
            raise UpstreamValidationError(f"Could not select mailbox {folder!r}.")

    @staticmethod
    def _folders_from_list(data: Sequence[FetchPart]) -> list[MailboxFolder]:
        folders: list[MailboxFolder] = []
        for raw in data:
            if not isinstance(raw, bytes):
                continue
            match = LIST_PATTERN.match(raw)
            if match is None:
                continue
            delimiter_raw = match.group("delimiter")
            delimiter = (
                None if delimiter_raw == b"NIL" else _unquote_imap(delimiter_raw).decode("ascii", errors="replace")
            )
            folders.append(
                MailboxFolder(
                    name=_decode_modified_utf7(_unquote_imap(match.group("name"))),
                    delimiter=delimiter,
                    flags=tuple(flag.decode("ascii", errors="replace") for flag in match.group("flags").split()),
                )
            )
        return folders

    def _resolve_sent_folder(
        self,
        connection: imaplib.IMAP4,
        account: EmailAccountSettings,
    ) -> str:
        if account.sent_folder is not None:
            return account.sent_folder
        status, data = connection.list()
        if status != "OK":
            raise UpstreamServerError("IMAP LIST failed while locating the Sent mailbox.")
        folders = self._folders_from_list(data)
        for folder in folders:
            if any(flag.casefold() == r"\sent" for flag in folder.flags):
                return folder.name
        common_names = {"sent", "sent mail", "sent messages", "sent items"}
        for folder in folders:
            if folder.name.casefold() in common_names:
                return folder.name
        raise UpstreamValidationError(
            "Could not locate the Sent mailbox. Configure sent_folder for this account.",
        )

    def _validate_page(self, limit: int, offset: int) -> None:
        if limit < 1 or limit > self._settings.email_max_results:
            raise UpstreamValidationError(
                f"limit must be between 1 and {self._settings.email_max_results}.",
            )
        if offset < 0:
            raise UpstreamValidationError("offset must be non-negative.")

    async def list_folders(self, account_name: str) -> list[MailboxFolder]:
        return await asyncio.to_thread(self._list_folders, account_name)

    def _list_folders(self, account_name: str) -> list[MailboxFolder]:
        account = self._account(account_name)
        with self._imap(account) as connection:
            status, data = connection.list()
            if status != "OK":
                raise UpstreamServerError("IMAP LIST failed.")
        folders = self._folders_from_list(data)
        return sorted(folders, key=lambda item: item.name.casefold())

    async def list_messages(
        self,
        account_name: str,
        folder: str,
        *,
        limit: int,
        offset: int,
    ) -> list[MessageSummary]:
        return await asyncio.to_thread(
            self._search_and_fetch,
            account_name,
            folder,
            ("ALL",),
            limit,
            offset,
        )

    async def search_messages(  # noqa: PLR0913
        self,
        account_name: str,
        folder: str,
        *,
        sender: str | None,
        recipient: str | None,
        subject: str | None,
        text: str | None,
        since: date | None,
        before: date | None,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> list[MessageSummary]:
        criteria: list[str] = []
        for key, value in (("FROM", sender), ("TO", recipient), ("SUBJECT", subject), ("TEXT", text)):
            if value is not None:
                criteria.extend((key, self._quote_search(value)))
        if since is not None:
            criteria.extend(("SINCE", since.strftime("%d-%b-%Y")))
        if before is not None:
            criteria.extend(("BEFORE", before.strftime("%d-%b-%Y")))
        if unread_only:
            criteria.append("UNSEEN")
        if not criteria:
            criteria.append("ALL")
        return await asyncio.to_thread(
            self._search_and_fetch,
            account_name,
            folder,
            tuple(criteria),
            limit,
            offset,
        )

    @staticmethod
    def _quote_search(value: str) -> str:
        if "\r" in value or "\n" in value or "\x00" in value:
            raise UpstreamValidationError("Search values must not contain control characters.")
        try:
            value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise UpstreamValidationError("Portable IMAP search filters currently require ASCII text.") from exc
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def _search_and_fetch(
        self,
        account_name: str,
        folder: str,
        criteria: tuple[str, ...],
        limit: int,
        offset: int,
    ) -> list[MessageSummary]:
        self._validate_page(limit, offset)
        account = self._account(account_name)
        with self._imap(account) as connection:
            self._select(connection, folder)
            status, search_data = connection.uid("SEARCH", *criteria)
            if status != "OK":
                raise UpstreamValidationError("IMAP SEARCH failed.")
            raw_uids = search_data[0] if search_data else b""
            uids = list(reversed(raw_uids.split() if isinstance(raw_uids, bytes) else []))
            selected = uids[offset : offset + limit]
            if not selected:
                return []
            uid_set = b",".join(selected).decode("ascii")
            status, raw_fetch = connection.uid(
                "FETCH",
                uid_set,
                "(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.FIELDS (DATE FROM TO CC SUBJECT MESSAGE-ID)])",
            )
            if status != "OK":
                raise UpstreamServerError("IMAP FETCH failed.")
        fetch_parts = cast(list[FetchPart], raw_fetch)
        by_uid: dict[int, MessageSummary] = {}
        for part in fetch_parts:
            if not isinstance(part, tuple):
                continue
            summary = _parse_summary(part[0], part[1])
            if summary.uid:
                by_uid[summary.uid] = summary
        return [by_uid[int(uid)] for uid in selected if int(uid) in by_uid]

    async def get_message(self, account_name: str, folder: str, uid: int) -> ParsedMessage:
        return await asyncio.to_thread(self._get_message, account_name, folder, uid)

    async def get_thread(
        self,
        account_name: str,
        folder: str,
        uid: int,
        *,
        limit: int,
    ) -> list[ParsedMessage]:
        return await asyncio.to_thread(self._get_thread, account_name, folder, uid, limit)

    def _get_message(self, account_name: str, folder: str, uid: int) -> ParsedMessage:
        raw, metadata = self._fetch_message(account_name, folder, uid)
        return self._parse_message(raw, metadata)

    def _get_thread(self, account_name: str, folder: str, uid: int, limit: int) -> list[ParsedMessage]:
        self._validate_page(limit, 0)
        if uid < 1:
            raise UpstreamValidationError("uid must be positive.")
        account = self._account(account_name)
        with self._imap(account) as connection:
            self._select(connection, folder)
            messages = self._fetch_selected_messages(connection, folder, (uid,))
            target = messages.get(uid)
            if target is None:
                raise UpstreamValidationError(f"Message UID {uid} was not found in {folder!r}.")

            pending_ids = list(self._thread_message_ids(target))
            searched_ids: set[str] = set()
            while pending_ids and len(messages) < limit:
                message_id = pending_ids.pop(0)
                if message_id in searched_ids:
                    continue
                searched_ids.add(message_id)
                quoted_id = self._quote_search(message_id)
                status, search_data = connection.uid(
                    "SEARCH",
                    "OR",
                    "OR",
                    "HEADER",
                    "MESSAGE-ID",
                    quoted_id,
                    "HEADER",
                    "IN-REPLY-TO",
                    quoted_id,
                    "HEADER",
                    "REFERENCES",
                    quoted_id,
                )
                if status != "OK":
                    raise UpstreamValidationError("IMAP thread SEARCH failed.")
                raw_uids = search_data[0] if search_data else b""
                uid_values = raw_uids.split() if isinstance(raw_uids, bytes) else []
                matching_uids = [
                    int(raw_uid) for raw_uid in uid_values if raw_uid.isdigit() and int(raw_uid) not in messages
                ]
                available = limit - len(messages)
                fetched = self._fetch_selected_messages(connection, folder, tuple(matching_uids[:available]))
                for fetched_uid, message in fetched.items():
                    messages[fetched_uid] = message
                    pending_ids.extend(
                        identifier for identifier in self._thread_message_ids(message) if identifier not in searched_ids
                    )
        return [messages[message_uid] for message_uid in sorted(messages)]

    @staticmethod
    def _thread_message_ids(message: ParsedMessage) -> tuple[str, ...]:
        values = message.references + message.in_reply_to
        if message.summary.message_id is not None:
            values += _message_ids(message.summary.message_id)
        return tuple(dict.fromkeys(values))

    def _fetch_message(self, account_name: str, folder: str, uid: int) -> tuple[bytes, bytes]:
        if uid < 1:
            raise UpstreamValidationError("uid must be positive.")
        account = self._account(account_name)
        with self._imap(account) as connection:
            self._select(connection, folder)
            status, raw_fetch = connection.uid("FETCH", str(uid), "(UID FLAGS RFC822.SIZE BODY.PEEK[])")
            if status != "OK":
                raise UpstreamValidationError(f"Message UID {uid} was not found in {folder!r}.")
        for part in cast(list[FetchPart], raw_fetch):
            if not isinstance(part, tuple):
                continue
            self._validate_message_size(part[0], part[1])
            return part[1], part[0]
        raise UpstreamValidationError(f"Message UID {uid} was not found in {folder!r}.")

    def _fetch_selected_messages(
        self,
        connection: imaplib.IMAP4,
        folder: str,
        uids: tuple[int, ...],
    ) -> dict[int, ParsedMessage]:
        if not uids:
            return {}
        uid_set = ",".join(str(message_uid) for message_uid in uids)
        status, raw_fetch = connection.uid("FETCH", uid_set, "(UID FLAGS RFC822.SIZE BODY.PEEK[])")
        if status != "OK":
            raise UpstreamValidationError(f"Messages could not be fetched from {folder!r}.")
        messages: dict[int, ParsedMessage] = {}
        for part in cast(list[FetchPart], raw_fetch):
            if not isinstance(part, tuple):
                continue
            self._validate_message_size(part[0], part[1])
            parsed = self._parse_message(part[1], part[0])
            if parsed.summary.uid:
                messages[parsed.summary.uid] = parsed
        return messages

    def _validate_message_size(self, metadata: bytes, raw: bytes) -> None:
        size = _metadata_value(FETCH_SIZE_PATTERN, metadata, default=len(raw))
        if size > self._settings.email_max_message_bytes:
            raise UpstreamValidationError(
                f"Message is {size} bytes; limit is {self._settings.email_max_message_bytes} bytes.",
            )

    def _parse_message(self, raw: bytes, metadata: bytes) -> ParsedMessage:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        plain_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[Attachment] = []
        for part in message.walk():
            if part.is_multipart():
                continue
            disposition = part.get_content_disposition()
            filename = part.get_filename()
            content_id = str(part["Content-ID"]).strip("<>") if part["Content-ID"] is not None else None
            is_attachment = filename is not None or (disposition in {"attachment", "inline"} and content_id is not None)
            if is_attachment:
                data = _decoded_part_bytes(part)
                attachments.append(
                    Attachment(
                        index=len(attachments) + 1,
                        filename=_decode_header(filename) or f"attachment-{len(attachments) + 1}",
                        content_type=part.get_content_type(),
                        disposition=disposition or "attachment",
                        content_id=content_id,
                        data=data,
                    )
                )
            elif part.get_content_type() == "text/plain":
                plain_parts.append(_decoded_part_text(part))
            elif part.get_content_type() == "text/html":
                html_parts.append(_decoded_part_text(part))
        body_format = "plain"
        body = "\n\n".join(value.strip() for value in plain_parts if value.strip())
        if not body and html_parts:
            extractor = _HtmlTextExtractor()
            extractor.feed("\n".join(html_parts))
            body = extractor.text()
            body_format = "html-to-text"
        if len(body) > self._settings.email_max_body_chars:
            body = body[: self._settings.email_max_body_chars] + "\n\n[body truncated]"
        summary = MessageSummary(
            uid=_metadata_value(FETCH_UID_PATTERN, metadata),
            subject=_decode_header(str(message["Subject"]) if message["Subject"] is not None else None),
            sender=_decode_header(str(message["From"]) if message["From"] is not None else None),
            recipients=_decode_header(str(message["To"]) if message["To"] is not None else None),
            date=_format_date(str(message["Date"]) if message["Date"] is not None else None),
            message_id=(
                _decode_header(str(message["Message-ID"]) if message["Message-ID"] is not None else None) or None
            ),
            flags=_metadata_flags(metadata),
            size_bytes=_metadata_value(FETCH_SIZE_PATTERN, metadata, default=len(raw)),
        )
        return ParsedMessage(
            summary=summary,
            cc=_decode_header(str(message["Cc"]) if message["Cc"] is not None else None),
            body=body,
            body_format=body_format,
            attachments=tuple(attachments),
            reply_to=_decode_header(str(message["Reply-To"]) if message["Reply-To"] is not None else None),
            in_reply_to=_message_ids(str(message["In-Reply-To"]) if message["In-Reply-To"] is not None else None),
            references=_message_ids(str(message["References"]) if message["References"] is not None else None),
        )

    async def send_raw(
        self,
        account_name: str,
        sender: str,
        raw_message: bytes,
        recipients: Sequence[str],
    ) -> None:
        await asyncio.to_thread(self._send_raw, account_name, sender, raw_message, tuple(recipients))

    def _send_raw(self, account_name: str, sender: str, raw_message: bytes, recipients: tuple[str, ...]) -> None:
        account = self._account(account_name)
        with self._smtp(account) as connection:
            refused = connection.sendmail(sender, list(recipients), raw_message)
            if refused:
                refused_addresses = ", ".join(sorted(refused))
                raise UpstreamValidationError(
                    f"SMTP refused recipients: {refused_addresses}. Other recipients may have received the message.",
                )
        try:
            self._save_to_sent(account, raw_message)
        except (UpstreamAuthError, UpstreamServerError, UpstreamValidationError) as exc:
            raise UpstreamServerError(
                "Email was accepted by SMTP but could not be saved to the Sent mailbox. "
                "Do not retry automatically because recipients may receive a duplicate.",
            ) from exc

    def _save_to_sent(self, account: EmailAccountSettings, raw_message: bytes) -> None:
        with self._imap(account) as connection:
            sent_folder = self._resolve_sent_folder(connection, account)
            status, _ = cast(
                tuple[str, list[bytes | None]],
                connection.append(
                    self._mailbox_argument(sent_folder),
                    r"\Seen",
                    "",
                    raw_message,
                ),
            )
            if status != "OK":
                raise UpstreamServerError(f"IMAP APPEND to mailbox {sent_folder!r} failed.")

    @contextmanager
    def _smtp(self, account: EmailAccountSettings) -> Iterator[smtplib.SMTP]:
        context = ssl.create_default_context()
        connection: smtplib.SMTP | None = None
        try:
            if account.smtp_tls is TlsMode.IMPLICIT:
                connection = smtplib.SMTP_SSL(
                    account.smtp_host,
                    account.smtp_port,
                    timeout=self._settings.timeout_seconds,
                    context=context,
                )
            else:
                connection = smtplib.SMTP(
                    account.smtp_host,
                    account.smtp_port,
                    timeout=self._settings.timeout_seconds,
                )
                connection.ehlo()
                connection.starttls(context=context)
                connection.ehlo()
            try:
                connection.login(
                    account.resolved_smtp_username,
                    account.resolved_smtp_password.get_secret_value(),
                )
            except smtplib.SMTPAuthenticationError as exc:
                raise UpstreamAuthError("SMTP authentication failed.") from exc
            yield connection
        except (UpstreamAuthError, UpstreamValidationError):
            raise
        except (smtplib.SMTPException, OSError, TimeoutError) as exc:
            raise UpstreamServerError("SMTP operation failed; delivery status may be unknown.") from exc
        finally:
            if connection is not None:
                try:
                    connection.quit()
                except (smtplib.SMTPException, OSError):
                    connection.close()
