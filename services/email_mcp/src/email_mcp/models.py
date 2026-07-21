import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

MIME_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")


class AttachmentDisposition(StrEnum):
    ATTACHMENT = "attachment"
    INLINE = "inline"


class OutgoingAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    content_type: str = "application/octet-stream"
    content_base64: str
    disposition: AttachmentDisposition = AttachmentDisposition.ATTACHMENT
    content_id: str | None = None

    @field_validator("filename", "content_type", "content_id")
    @classmethod
    def validate_header_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Expected a non-empty value.")
        if "\r" in stripped or "\n" in stripped:
            raise ValueError("MIME values must not contain newlines.")
        return stripped

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        if MIME_TYPE_PATTERN.fullmatch(value) is None:
            raise ValueError("Expected a MIME type in type/subtype form without parameters.")
        return value


@dataclass(frozen=True)
class MailboxFolder:
    name: str
    delimiter: str | None
    flags: tuple[str, ...]


@dataclass(frozen=True)
class MessageSummary:
    uid: int
    subject: str
    sender: str
    recipients: str
    date: str | None
    message_id: str | None
    flags: tuple[str, ...]
    size_bytes: int


@dataclass(frozen=True)
class Attachment:
    index: int
    filename: str
    content_type: str
    disposition: str
    content_id: str | None
    data: bytes

    @property
    def size_bytes(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class ParsedMessage:
    summary: MessageSummary
    cc: str
    body: str
    body_format: str
    attachments: tuple[Attachment, ...]
    reply_to: str = ""
    in_reply_to: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecodedAttachment:
    filename: str
    content_type: str
    disposition: AttachmentDisposition
    content_id: str | None
    data: bytes
