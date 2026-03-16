from typing import Literal

from pydantic import BaseModel


class CatalogItem(BaseModel):
    entity_type: Literal["artist", "album", "track", "playlist"]
    id: str
    name: str
    artist_name: str | None = None
    album_name: str | None = None
    year: int | None = None
    genre: str | None = None
    rating: int | None = None
    liked: bool | None = None


class PlaylistItem(BaseModel):
    id: str
    name: str
    song_count: int | None = None
    public: bool | None = None
    owner: str | None = None
