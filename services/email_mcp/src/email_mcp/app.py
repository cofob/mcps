from collections.abc import Awaitable, Callable
from typing import cast

from fastmcp import FastMCP
from starlette.applications import Starlette

from email_mcp import __version__
from email_mcp.config import EmailSettings
from email_mcp.guidance import EMAIL_MCP_INSTRUCTIONS, email_usage_skill
from email_mcp.service import EmailService
from email_mcp.tools import AccountTools, MessageTools, SendTools
from mcp_common import (
    SupportsToolRegistration,
    ToolResult,
    ToolSpec,
    build_auth_provider,
    build_http_app,
    build_tool_annotations,
    build_tool_tags,
    register_enabled_tools,
)
from mcp_common.logging import configure_logging


def _tool_spec(method: Callable[..., Awaitable[ToolResult]], name: str, *groups: str) -> ToolSpec:
    group_set = frozenset(groups)
    tags = build_tool_tags(name, group_set)
    annotations = build_tool_annotations(name, group_set)

    def register_tool(mcp: SupportsToolRegistration) -> None:
        mcp.tool(method, name=name, tags=set(tags), annotations=annotations)

    return ToolSpec(
        name=name,
        groups=group_set,
        tags=tags,
        annotations=annotations,
        register=register_tool,
    )


def _make_tool_specs(service: EmailService) -> list[ToolSpec]:
    accounts = AccountTools(service)
    messages = MessageTools(service)
    send = SendTools(service)
    return [
        _tool_spec(accounts.list_accounts, "email_list_accounts", "read", "accounts"),
        _tool_spec(accounts.list_folders, "email_list_folders", "read", "folders"),
        _tool_spec(messages.list_messages, "email_list_messages", "read", "mail"),
        _tool_spec(messages.search_messages, "email_search_messages", "read", "mail", "search"),
        _tool_spec(messages.get_message, "email_get_message", "read", "mail"),
        _tool_spec(messages.get_thread, "email_get_thread", "read", "mail", "thread"),
        _tool_spec(messages.get_attachment, "email_get_attachment", "read", "mail", "attachments"),
        _tool_spec(send.send_message, "email_send_message", "mutate", "mail", "send"),
        _tool_spec(send.reply_message, "email_reply_message", "mutate", "mail", "send", "thread"),
    ]


def _register_usage_skill(mcp: FastMCP) -> None:
    @mcp.resource(
        "skill://email-mcp/usage",
        name="email-mcp-usage",
        title="Email MCP usage skill",
        description="Safe search, reading, sending, attachment, and OpenPGP/MIME usage guidance.",
        mime_type="text/markdown",
        tags={"skill", "email", "safety", "usage"},
    )
    def usage_skill() -> str:
        return email_usage_skill()

    del usage_skill


def create_mcp(settings: EmailSettings) -> FastMCP:
    auth = build_auth_provider(settings.oauth2) if settings.mcp_auth_mode.value == "oauth2" else None
    mcp = FastMCP(name="email-mcp", instructions=EMAIL_MCP_INSTRUCTIONS, auth=auth)
    register_enabled_tools(
        cast(SupportsToolRegistration, mcp),
        _make_tool_specs(EmailService(settings)),
        settings.tools,
    )
    _register_usage_skill(mcp)
    return mcp


def create_app(settings: EmailSettings | None = None) -> Starlette:
    resolved = settings or EmailSettings.from_env()
    configure_logging(resolved.log_level)
    mcp = create_mcp(resolved)
    mcp_app = mcp.http_app(path="/mcp")
    return build_http_app(mcp_app, service_name="email-mcp", version=__version__)
