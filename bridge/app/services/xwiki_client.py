import logging
from xml.etree import ElementTree as ET

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

XWIKI_REST = f"{settings.xwiki_url}/rest"


def _auth() -> tuple[str, str]:
    return (settings.xwiki_admin_user, settings.xwiki_admin_password)


def _page_url(space: str, page: str) -> str:
    return f"{XWIKI_REST}/wikis/xwiki/spaces/{space}/pages/{page}"


async def get_page(space: str, page: str) -> dict | None:
    """Get a page from XWiki. Returns None if not found."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            _page_url(space, page),
            auth=_auth(),
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


async def put_page(space: str, page: str, title: str, content: str,
                   syntax: str = "xwiki/2.1") -> str:
    """Create or update a page. Returns the page URL."""
    xml = _build_page_xml(title, content, syntax)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            _page_url(space, page),
            auth=_auth(),
            content=xml,
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()
    page_url = f"{settings.xwiki_url}/bin/view/{space}/{page}"
    logger.info("Put page %s/%s -> %s", space, page, resp.status_code)
    return page_url


async def list_pages(space: str) -> list[str]:
    """List all page names in a space."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{XWIKI_REST}/wikis/xwiki/spaces/{space}/pages",
            auth=_auth(),
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
    pages = data.get("pageSummaries", [])
    return [p.get("name", "") for p in pages]


async def upload_attachment(space: str, page: str, filename: str,
                            data: bytes, content_type: str) -> str:
    """Upload an attachment to a page."""
    url = f"{_page_url(space, page)}/attachments/{filename}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.put(
            url,
            auth=_auth(),
            content=data,
            headers={"Content-Type": content_type},
        )
        resp.raise_for_status()
    return url


def _build_page_xml(title: str, content: str, syntax: str) -> bytes:
    """Build XWiki REST page XML."""
    page = ET.Element("page", xmlns="http://www.xwiki.org")
    ET.SubElement(page, "title").text = title
    ET.SubElement(page, "syntax").text = syntax
    ET.SubElement(page, "content").text = content
    return ET.tostring(page, encoding="unicode").encode("utf-8")
