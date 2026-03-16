from pydantic import BaseModel


class SlskdDownloadRequest(BaseModel):
    filename: str
    size: int


class SlskdSearchFile(BaseModel):
    username: str
    filename: str
    directory: str
    size: int

