import asyncio
from time import monotonic
from uuid import UUID

from mcp_common import JsonObject, expect_array, expect_object, get_bool, get_object_list, get_str
from slskd_mcp.client import SlskdClient
from slskd_mcp.formatters import (
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
        limit: int = 50,
    ) -> str:
        """Start a slskd music search, wait for completion, and return readable results.

        Guidance: use concise filename-style keywords rather than long phrases.
        Include only terms likely present in file names (e.g. artist, album, track).
        Example: "Gesaffelstein enter the gamma"
        (Gesaffelstein = artist, Enter the Gamma = album).
        """
        payload = await self._client.request(
            "POST",
            "/api/v0/searches",
            json_body={
                "searchText": search_text,
                "responseLimit": response_limit,
                "fileLimit": file_limit,
                "searchTimeout": search_timeout * 1000,
                "filterResponses": filter_responses,
                "minimumResponseFileCount": minimum_response_file_count,
                "maximumPeerQueueLength": maximum_peer_queue_length,
                "minimumPeerUploadSpeed": minimum_peer_upload_speed,
            },
        )
        search = expect_object(payload, context="create_search")
        search_id_value = get_str(search, "id") or get_str(search, "Id") or "unknown"
        response_items = await self._wait_for_search_results(search_id_value, search, search_timeout)
        results = normalize_search_results(response_items)
        return format_search_results(search_id_value, results, limit=limit)

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

    async def _wait_for_search_results(
        self,
        search_id: str,
        initial_search: JsonObject,
        search_timeout: int,
    ) -> list[JsonObject]:
        search = initial_search
        deadline = monotonic() + max(float(search_timeout) + 5.0, self._client.timeout_seconds)
        latest_results = _extract_inline_responses(search)
        completed_empty_polls = 0

        while True:
            if latest_results and _is_search_complete(search):
                return latest_results
            if monotonic() >= deadline:
                return latest_results

            response_payload = await self._client.request("GET", f"/api/v0/searches/{search_id}/responses")
            response_items = [
                expect_object(item, context="create_search")
                for item in expect_array(response_payload, context="create_search")
            ]
            if response_items:
                latest_results = response_items

            if _is_search_complete(search):
                if latest_results:
                    return latest_results
                completed_empty_polls += 1
                if completed_empty_polls >= 3:
                    return []
            else:
                completed_empty_polls = 0

            await asyncio.sleep(self._client.search_poll_interval_seconds)
            payload = await self._client.request("GET", f"/api/v0/searches/{search_id}")
            search = expect_object(payload, context="create_search")


def _extract_inline_responses(search: JsonObject) -> list[JsonObject]:
    if "responses" in search:
        return get_object_list(search, "responses", context="create_search")
    if "Responses" in search:
        return get_object_list(search, "Responses", context="create_search")
    return []


def _is_search_complete(search: JsonObject) -> bool:
    if get_bool(search, "isComplete") is True or get_bool(search, "IsComplete") is True:
        return True
    if get_str(search, "endedAt") or get_str(search, "EndedAt"):
        return True
    state = (
        get_str(search, "state")
        or get_str(search, "State")
        or get_str(search, "status")
        or get_str(search, "Status")
    )
    if state is None:
        return False
    return state.lower() in {
        "complete",
        "completed",
        "done",
        "finished",
        "cancelled",
        "canceled",
        "timedout",
        "timed_out",
        "timeout",
    }
