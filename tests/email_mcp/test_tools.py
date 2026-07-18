import pytest
from pydantic import SecretStr

from email_mcp.app import create_mcp
from email_mcp.config import EmailAccountSettings, EmailSettings


def make_settings() -> EmailSettings:
    return EmailSettings(
        EMAIL_ACCOUNTS={
            "work": EmailAccountSettings(
                imap_host="imap.example.com",
                smtp_host="smtp.example.com",
                username="alice@example.com",
                password=SecretStr("secret"),
                from_address="alice@example.com",
            )
        }
    )


@pytest.mark.asyncio
async def test_email_tools_expose_expected_metadata() -> None:
    tools = {tool.name: tool for tool in await create_mcp(make_settings()).list_tools()}

    assert set(tools) == {
        "email_get_attachment",
        "email_get_message",
        "email_list_accounts",
        "email_list_folders",
        "email_list_messages",
        "email_search_messages",
        "email_send_message",
    }
    read_tool = tools["email_get_message"]
    assert read_tool.annotations is not None
    assert read_tool.annotations.readOnlyHint is True
    assert read_tool.annotations.openWorldHint is True
    assert read_tool.tags >= {"read", "read-only", "remote-service", "open-world"}
    send_tool = tools["email_send_message"]
    assert send_tool.annotations is not None
    assert send_tool.annotations.readOnlyHint is False
    assert send_tool.annotations.idempotentHint is False
    assert send_tool.annotations.destructiveHint is False
    assert send_tool.tags >= {"mutate", "write", "remote-service", "open-world"}
