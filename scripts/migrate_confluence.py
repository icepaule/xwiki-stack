#!/usr/bin/env python3
"""
Confluence → XWiki Migration Script

Reads all pages from a Confluence space via REST API and creates
corresponding XWiki pages via XWiki REST API.

Usage:
    python3 migrate_confluence.py
    python3 migrate_confluence.py --space NETOPS --dry-run

Environment variables (or CLI args):
    CONFLUENCE_URL, CONFLUENCE_USER, CONFLUENCE_PASSWORD, CONFLUENCE_SPACE
    XWIKI_EXTERNAL_URL, XWIKI_ADMIN_USER, XWIKI_ADMIN_PASSWORD
"""
import argparse
import html
import os
import re
import sys
from xml.etree import ElementTree as ET

import httpx


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class ConfluenceClient:
    def __init__(self, base_url: str, user: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (user, password)
        self.client = httpx.Client(timeout=30, auth=self.auth)

    def get_space_pages(self, space_key: str) -> list[dict]:
        """Get all pages in a space with pagination."""
        pages = []
        start = 0
        limit = 50
        while True:
            resp = self.client.get(
                f"{self.base_url}/rest/api/content",
                params={
                    "spaceKey": space_key,
                    "type": "page",
                    "start": start,
                    "limit": limit,
                    "expand": "body.storage,ancestors,metadata.labels",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            pages.extend(results)
            if data.get("size", 0) < limit:
                break
            start += limit
        return pages

    def get_page_attachments(self, page_id: str) -> list[dict]:
        """Get attachments for a page."""
        resp = self.client.get(
            f"{self.base_url}/rest/api/content/{page_id}/child/attachment",
            params={"expand": "version"},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def download_attachment(self, download_url: str) -> bytes:
        """Download attachment content."""
        url = f"{self.base_url}{download_url}"
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp.content


class XWikiClient:
    def __init__(self, base_url: str, user: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (user, password)
        self.client = httpx.Client(timeout=30, auth=self.auth)

    def put_page(self, space: str, page_name: str, title: str,
                 content: str, syntax: str = "xwiki/2.1"):
        """Create or update an XWiki page."""
        page_xml = self._build_xml(title, content, syntax)
        url = f"{self.base_url}/xwiki/rest/wikis/xwiki/spaces/{space}/pages/{page_name}"
        resp = self.client.put(
            url,
            content=page_xml,
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()
        return resp.status_code

    def upload_attachment(self, space: str, page: str, filename: str,
                         data: bytes, content_type: str = "application/octet-stream"):
        url = (
            f"{self.base_url}/xwiki/rest/wikis/xwiki/spaces/{space}"
            f"/pages/{page}/attachments/{filename}"
        )
        resp = self.client.put(
            url, content=data,
            headers={"Content-Type": content_type},
        )
        resp.raise_for_status()

    def _build_xml(self, title: str, content: str, syntax: str) -> bytes:
        page = ET.Element("page", xmlns="http://www.xwiki.org")
        ET.SubElement(page, "title").text = title
        ET.SubElement(page, "syntax").text = syntax
        ET.SubElement(page, "content").text = content
        return ET.tostring(page, encoding="unicode").encode("utf-8")


def confluence_storage_to_xwiki(storage_html: str) -> str:
    """Convert Confluence storage format (XHTML) to XWiki 2.1 syntax.

    This handles common elements. Complex macros may need manual review.
    """
    text = storage_html

    # Remove CDATA and XML declarations
    text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.DOTALL)

    # Headings: <h1>text</h1> → = text =
    for i in range(1, 7):
        eq = "=" * i
        text = re.sub(
            rf"<h{i}[^>]*>(.*?)</h{i}>",
            rf"\n{eq} \1 {eq}\n",
            text, flags=re.DOTALL,
        )

    # Bold: <strong>text</strong> → **text**
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.DOTALL)
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.DOTALL)

    # Italic: <em>text</em> → //text//
    text = re.sub(r"<em>(.*?)</em>", r"//\1//", text, flags=re.DOTALL)
    text = re.sub(r"<i>(.*?)</i>", r"//\1//", text, flags=re.DOTALL)

    # Code blocks: <ac:structured-macro ac:name="code">...<ac:plain-text-body>CODE</ac:plain-text-body>...
    text = re.sub(
        r'<ac:structured-macro[^>]*ac:name="code"[^>]*>.*?'
        r"<ac:plain-text-body>(.*?)</ac:plain-text-body>.*?</ac:structured-macro>",
        r"\n{{code}}\n\1\n{{/code}}\n",
        text, flags=re.DOTALL,
    )

    # Inline code: <code>text</code> → ##text##
    text = re.sub(r"<code>(.*?)</code>", r"##\1##", text, flags=re.DOTALL)

    # Links: <a href="url">text</a> → [[text>>url]]
    text = re.sub(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        r"[[\2>>\1]]",
        text, flags=re.DOTALL,
    )

    # Confluence links: <ac:link><ri:page ri:content-title="PageTitle"/>...
    text = re.sub(
        r'<ac:link><ri:page ri:content-title="([^"]*)"[^/]*/>'
        r"(?:<ac:plain-text-link-body>(.*?)</ac:plain-text-link-body>)?"
        r"</ac:link>",
        lambda m: f"[[{m.group(2) or m.group(1)}>>{m.group(1)}]]",
        text, flags=re.DOTALL,
    )

    # Unordered lists: <ul><li>text</li></ul>
    text = re.sub(r"<ul[^>]*>", "", text)
    text = re.sub(r"</ul>", "", text)
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"* \1", text, flags=re.DOTALL)

    # Ordered lists
    text = re.sub(r"<ol[^>]*>", "", text)
    text = re.sub(r"</ol>", "", text)

    # Tables
    text = re.sub(r"<table[^>]*>", "", text)
    text = re.sub(r"</table>", "", text)
    text = re.sub(r"<tbody[^>]*>", "", text)
    text = re.sub(r"</tbody>", "", text)
    text = re.sub(r"<tr[^>]*>", "", text)
    text = re.sub(r"</tr>", "\n", text)
    text = re.sub(r"<th[^>]*>(.*?)</th>", r"|=\1", text, flags=re.DOTALL)
    text = re.sub(r"<td[^>]*>(.*?)</td>", r"|\1", text, flags=re.DOTALL)

    # Line breaks
    text = re.sub(r"<br\s*/?>", "\n", text)

    # Paragraphs
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n", text, flags=re.DOTALL)

    # Images (Confluence attachments)
    text = re.sub(
        r'<ac:image[^>]*>.*?<ri:attachment ri:filename="([^"]*)"[^/]*/>.*?</ac:image>',
        r"[[image:\1]]",
        text, flags=re.DOTALL,
    )

    # Info/warning/note macros
    for macro in ["info", "warning", "note", "tip"]:
        text = re.sub(
            rf'<ac:structured-macro[^>]*ac:name="{macro}"[^>]*>.*?'
            rf"<ac:rich-text-body>(.*?)</ac:rich-text-body>.*?</ac:structured-macro>",
            rf"\n{{{{{macro}}}}}\n\1\n{{{{{macro}}}}}\n",
            text, flags=re.DOTALL,
        )

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = html.unescape(text)

    # Clean up excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def sanitize_page_name(title: str) -> str:
    """Convert page title to safe XWiki page name."""
    name = re.sub(r"[^a-zA-Z0-9_\- ]", "", title)
    name = name.replace(" ", "_")
    return name[:100]  # Limit length


def build_page_tree(pages: list[dict]) -> dict[str, list[dict]]:
    """Build parent→children mapping from Confluence page ancestors."""
    tree: dict[str, list[dict]] = {}
    for page in pages:
        ancestors = page.get("ancestors", [])
        parent_id = ancestors[-1]["id"] if ancestors else "root"
        tree.setdefault(parent_id, []).append(page)
    return tree


def migrate(args):
    confluence = ConfluenceClient(args.confluence_url, args.confluence_user, args.confluence_password)
    xwiki = XWikiClient(args.xwiki_url, args.xwiki_user, args.xwiki_password)

    print(f"Fetching pages from Confluence space '{args.space}'...")
    pages = confluence.get_space_pages(args.space)
    print(f"Found {len(pages)} pages")

    xwiki_space = f"Confluence_{args.space}"
    migrated = 0
    errors = []

    for page in pages:
        title = page.get("title", "Untitled")
        page_id = page.get("id", "")
        storage_body = page.get("body", {}).get("storage", {}).get("value", "")

        page_name = sanitize_page_name(title)
        if not page_name:
            page_name = f"Page_{page_id}"

        print(f"  Migrating: {title} → {xwiki_space}/{page_name}")

        if args.dry_run:
            migrated += 1
            continue

        try:
            # Convert content
            xwiki_content = confluence_storage_to_xwiki(storage_body)

            # Add migration metadata header
            header = (
                "{{info}}\n"
                f"Migrated from Confluence space **{args.space}**, page ID {page_id}.\n"
                "{{/info}}\n\n"
            )
            xwiki_content = header + xwiki_content

            # Create page
            xwiki.put_page(xwiki_space, page_name, title, xwiki_content)

            # Migrate attachments
            attachments = confluence.get_page_attachments(page_id)
            for att in attachments:
                att_title = att.get("title", "")
                download_link = att.get("_links", {}).get("download", "")
                if download_link and att_title:
                    try:
                        att_data = confluence.download_attachment(download_link)
                        media_type = att.get("metadata", {}).get("mediaType", "application/octet-stream")
                        xwiki.upload_attachment(xwiki_space, page_name, att_title, att_data, media_type)
                        print(f"    Attachment: {att_title}")
                    except Exception as e:
                        print(f"    Attachment error ({att_title}): {e}")

            migrated += 1
        except Exception as e:
            errors.append(f"{title}: {e}")
            print(f"    ERROR: {e}")

    print(f"\nMigration complete: {migrated}/{len(pages)} pages")
    if errors:
        print(f"Errors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")


def main():
    parser = argparse.ArgumentParser(description="Confluence → XWiki Migration")
    parser.add_argument("--confluence-url", default=get_env("CONFLUENCE_URL", "http://localhost:8090"))
    parser.add_argument("--confluence-user", default=get_env("CONFLUENCE_USER", "admin"))
    parser.add_argument("--confluence-password", default=get_env("CONFLUENCE_PASSWORD", ""))
    parser.add_argument("--xwiki-url", default=get_env("XWIKI_EXTERNAL_URL", "http://localhost:8085"))
    parser.add_argument("--xwiki-user", default=get_env("XWIKI_ADMIN_USER", "admin"))
    parser.add_argument("--xwiki-password", default=get_env("XWIKI_ADMIN_PASSWORD", ""))
    parser.add_argument("--space", default=get_env("CONFLUENCE_SPACE", "NETOPS"))
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without doing it")
    args = parser.parse_args()

    if not args.confluence_password:
        print("Error: CONFLUENCE_PASSWORD not set", file=sys.stderr)
        sys.exit(1)
    if not args.xwiki_password:
        print("Error: XWIKI_ADMIN_PASSWORD not set", file=sys.stderr)
        sys.exit(1)

    migrate(args)


if __name__ == "__main__":
    main()
