from uuid import UUID

from mcp_common import expect_array, expect_object, get_str
from slskd_mcp.client import SlskdClient
from slskd_mcp.formatters import (
    format_search_created,
    format_search_list,
    format_search_results,
    format_simple_summary,
)
from slskd_mcp.normalize import normalize_search_results


class SearchTools:
    def __init__(self, client: SlskdClient) -> None:
        self._client = client

    async def create_search(  # noqa: PLR0913
        self,
        search_text: str,
        response_limit: int = 100,
        file_limit: int = 10000,
        search_timeout: int = 15,
        filter_responses: bool = True,
        minimum_response_file_count: int = 1,
        maximum_peer_queue_length: int = 1000000,
        minimum_peer_upload_speed: int = 0,
    ) -> str:
        """Start a new slskd search and return its id."""
        payload = await self._client.request(
            "POST",
            "/api/v0/searches",
            json_body={
                "searchText": search_text,
                "responseLimit": response_limit,
                "fileLimit": file_limit,
                "searchTimeout": search_timeout,
                "filterResponses": filter_responses,
                "minimumResponseFileCount": minimum_response_file_count,
                "maximumPeerQueueLength": maximum_peer_queue_length,
                "minimumPeerUploadSpeed": minimum_peer_upload_speed,
            },
        )
        search = expect_object(payload, context="create_search")
        search_id_value = get_str(search, "id") or get_str(search, "Id") or "unknown"
        return format_search_created(search_id_value)

    async def list_searches(self) -> str:
        """List active or recent slskd searches."""
        payload = await self._client.request("GET", "/api/v0/searches")
        search_items = [
            expect_object(item, context="list_searches")
            for item in expect_array(payload, context="list_searches")
        ]
        return format_search_list(search_items)

    async def get_search(self, search_id: UUID) -> str:
        """Get the current status and summary of one slskd search."""
        payload = await self._client.request("GET", f"/api/v0/searches/{search_id}")
        search = expect_object(payload, context="get_search")
        return format_simple_summary(
            f"Search {get_str(search, 'id') or get_str(search, 'Id') or 'unknown'}: "
            f"{get_str(search, 'searchText') or get_str(search, 'SearchText') or ''}"
        )

    async def get_search_results(
        self,
        search_id: UUID,
        search_type: str = "all",
        output_format: str = "both",
        limit: int = 50,
    ) -> str:
        """Show readable results for one slskd search."""
        del search_type, output_format
        payload = await self._client.request("GET", f"/api/v0/searches/{search_id}/responses")
        response_items = [
            expect_object(item, context="get_search_results")
            for item in expect_array(payload, context="get_search_results")
        ]
        results = normalize_search_results(response_items)
        return format_search_results(str(search_id), results, limit=limit)

    async def cancel_search(self, search_id: UUID) -> str:
        """Stop a running slskd search by id."""
        await self._client.request("PUT", f"/api/v0/searches/{search_id}")
        return format_simple_summary(f"Cancelled search {search_id}.")

    async def delete_search(self, search_id: UUID) -> str:
        """Delete a completed or no-longer-needed slskd search by id."""
        await self._client.request("DELETE", f"/api/v0/searches/{search_id}")
        return format_simple_summary(f"Deleted search {search_id}.")
