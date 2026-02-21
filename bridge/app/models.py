from pydantic import BaseModel


class GitHubSyncRequest(BaseModel):
    repos: list[str] | None = None  # None = all repos


class GitHubSyncResponse(BaseModel):
    synced: list[str]
    errors: list[str]
    total: int


class AIRequest(BaseModel):
    text: str
    context: str | None = None


class AIResponse(BaseModel):
    result: str
    model: str


class RAGIngestRequest(BaseModel):
    space: str | None = None
    page: str | None = None
    workspace: str = "xwiki"


class RAGIngestResponse(BaseModel):
    ingested: int
    workspace: str


class WordImportRequest(BaseModel):
    space: str = "Imported"
    title: str | None = None


class WordImportResponse(BaseModel):
    page_url: str
    title: str
