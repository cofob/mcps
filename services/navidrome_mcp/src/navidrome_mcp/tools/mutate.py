from navidrome_mcp.client import NavidromeClient
from navidrome_mcp.formatters import format_mutation_summary


class MutationTools:
    def __init__(self, client: NavidromeClient) -> None:
        self._client = client

    async def rate(self, item_type: str, item_id: str, rating: int) -> str:
        """Set a Navidrome rating for one artist, album, or track."""
        if rating < 0 or rating > 5:
            raise ValueError("rating must be between 0 and 5")
        await self._client.call("setRating", params={"id": item_id, "rating": rating})
        return format_mutation_summary(f"Set {item_type} {item_id} rating to {rating}.")

    async def like(self, item_type: str, item_ids: list[str]) -> str:
        """Mark one or more Navidrome artists, albums, or tracks as liked."""
        key = {"artist": "artistId", "album": "albumId", "track": "id"}[item_type]
        for item_id in item_ids:
            await self._client.call("star", params={key: item_id})
        return format_mutation_summary(f"Marked {len(item_ids)} {item_type} item(s) as liked.")

    async def unlike(self, item_type: str, item_ids: list[str]) -> str:
        """Remove the liked mark from one or more Navidrome items."""
        key = {"artist": "artistId", "album": "albumId", "track": "id"}[item_type]
        for item_id in item_ids:
            await self._client.call("unstar", params={key: item_id})
        return format_mutation_summary(f"Removed like from {len(item_ids)} {item_type} item(s).")
