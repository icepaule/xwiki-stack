import base64
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


async def list_repos(user: str | None = None) -> list[dict]:
    """List all repos for a user with pagination (handles 300+ repos)."""
    user = user or settings.github_user
    repos: list[dict] = []
    page = 1

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            resp = await client.get(
                f"{GITHUB_API}/users/{user}/repos",
                params={"per_page": 100, "page": page, "sort": "updated"},
                headers=_headers(),
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            page += 1

    logger.info("Found %d repos for %s", len(repos), user)
    return repos


async def get_readme(owner: str, repo: str) -> str | None:
    """Fetch README content (decoded from base64)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/readme",
            headers=_headers(),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

    data = resp.json()
    content_b64 = data.get("content", "")
    return base64.b64decode(content_b64).decode("utf-8", errors="replace")


async def get_repo_info(owner: str, repo: str) -> dict:
    """Get repo metadata."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}",
            headers=_headers(),
        )
        resp.raise_for_status()
    return resp.json()


async def get_repo_languages(owner: str, repo: str) -> dict[str, int]:
    """Get language breakdown for a repo."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/languages",
            headers=_headers(),
        )
        resp.raise_for_status()
    return resp.json()
