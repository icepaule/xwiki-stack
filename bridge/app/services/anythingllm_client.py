import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.anythingllm_api_key}",
        "Content-Type": "application/json",
    }


async def create_workspace(name: str) -> dict:
    """Create a new workspace in AnythingLLM."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.anythingllm_url}/api/v1/workspace/new",
            json={"name": name},
            headers=_headers(),
        )
        resp.raise_for_status()
    data = resp.json()
    logger.info("Created workspace: %s", name)
    return data


async def get_workspaces() -> list[dict]:
    """List all workspaces."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.anythingllm_url}/api/v1/workspaces",
            headers=_headers(),
        )
        resp.raise_for_status()
    return resp.json().get("workspaces", [])


async def ingest_text(workspace_slug: str, title: str, text: str) -> dict:
    """Ingest raw text into a workspace."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.anythingllm_url}/api/v1/document/raw-text",
            json={
                "textContent": text,
                "metadata": {"title": title, "source": "xwiki-bridge"},
            },
            headers=_headers(),
        )
        resp.raise_for_status()
        doc_data = resp.json()

    doc_location = doc_data.get("documents", [{}])[0].get("location", "")
    if doc_location:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.anythingllm_url}/api/v1/workspace/{workspace_slug}/update-embeddings",
                json={"adds": [doc_location]},
                headers=_headers(),
            )
            resp.raise_for_status()

    logger.info("Ingested '%s' into workspace '%s'", title, workspace_slug)
    return doc_data


async def ensure_workspace(name: str) -> str:
    """Get or create workspace, return slug."""
    workspaces = await get_workspaces()
    for ws in workspaces:
        if ws.get("name", "").lower() == name.lower():
            return ws["slug"]

    result = await create_workspace(name)
    return result.get("workspace", {}).get("slug", name.lower())
