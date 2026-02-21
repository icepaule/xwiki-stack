import logging

from fastapi import APIRouter

from app.models import RAGIngestRequest, RAGIngestResponse
from app.services import anythingllm_client, xwiki_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["RAG"])


@router.post("/ingest-space", response_model=RAGIngestResponse)
async def ingest_space(request: RAGIngestRequest):
    """Ingest all pages from an XWiki space into AnythingLLM."""
    space = request.space or "Main"
    workspace_slug = await anythingllm_client.ensure_workspace(request.workspace)

    pages = await xwiki_client.list_pages(space)
    ingested = 0

    for page_name in pages:
        try:
            page_data = await xwiki_client.get_page(space, page_name)
            if page_data:
                content = page_data.get("content", "")
                title = page_data.get("title", page_name)
                if content.strip():
                    await anythingllm_client.ingest_text(
                        workspace_slug, f"{space}/{title}", content
                    )
                    ingested += 1
        except Exception as e:
            logger.error("Failed to ingest %s/%s: %s", space, page_name, e)

    return RAGIngestResponse(ingested=ingested, workspace=workspace_slug)


@router.post("/ingest-page", response_model=RAGIngestResponse)
async def ingest_page(request: RAGIngestRequest):
    """Ingest a single XWiki page into AnythingLLM."""
    if not request.space or not request.page:
        raise ValueError("Both space and page are required")

    workspace_slug = await anythingllm_client.ensure_workspace(request.workspace)

    page_data = await xwiki_client.get_page(request.space, request.page)
    if not page_data:
        raise ValueError(f"Page {request.space}/{request.page} not found")

    content = page_data.get("content", "")
    title = page_data.get("title", request.page)
    await anythingllm_client.ingest_text(
        workspace_slug, f"{request.space}/{title}", content
    )

    return RAGIngestResponse(ingested=1, workspace=workspace_slug)
