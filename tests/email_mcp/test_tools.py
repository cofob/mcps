import pytest
from pydantic import SecretStr

from email_mcp.app import create_mcp
from email_mcp.config import EmailAccountSettings, EmailSettings
from email_mcp.guidance import EMAIL_MCP_INSTRUCTIONS


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
    for tool_name in (
        "email_list_accounts",
        "email_list_folders",
        "email_list_messages",
        "email_search_messages",
    ):
        assert "directly request" in (tools[tool_name].description or "")
    send_tool = tools["email_send_message"]
    assert send_tool.annotations is not None
    assert send_tool.annotations.readOnlyHint is False
    assert send_tool.annotations.idempotentHint is False
    assert send_tool.annotations.destructiveHint is False
    assert send_tool.tags >= {"mutate", "write", "remote-service", "open-world"}
    assert "explicit confirmation" in (send_tool.description or "")
    assert "complete bodies" in (send_tool.description or "")


@pytest.mark.asyncio
async def test_email_server_exposes_mandatory_usage_instructions() -> None:
    mcp = create_mcp(make_settings())

    assert mcp.instructions == EMAIL_MCP_INSTRUCTIONS
    assert "complete text and HTML message bodies" in mcp.instructions
    assert "email_list_accounts" in mcp.instructions
    assert "only when the user" in mcp.instructions
    assert "skill://email-mcp/usage" in mcp.instructions


@pytest.mark.asyncio
async def test_email_server_exposes_usage_skill_resource() -> None:
    mcp = create_mcp(make_settings())

    resources = {str(resource.uri): resource for resource in await mcp.list_resources()}
    resource = resources["skill://email-mcp/usage"]
    assert resource.mime_type == "text/markdown"
    assert resource.tags >= {"skill", "email", "safety", "usage"}

    result = await mcp.read_resource("skill://email-mcp/usage")
    content = result.contents[0].content
    assert "name: email-mcp-usage" in content
    assert "## Search strategy" in content
    assert "## Mandatory confirmation before sending" in content
    assert "complete plain-text body" in content
    assert "## OpenPGP/MIME signing" in content
