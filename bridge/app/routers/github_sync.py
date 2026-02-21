import logging
import re

from fastapi import APIRouter

from app.config import settings
from app.models import GitHubSyncRequest, GitHubSyncResponse
from app.services import github_client, xwiki_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/github", tags=["GitHub Sync"])


def _sanitize_page_name(name: str) -> str:
    """Make repo name safe for XWiki page names."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def _md_to_xwiki(md: str) -> str:
    """Basic Markdown to XWiki 2.1 syntax conversion."""
    text = md

    # Headings: ### text -> === text ===
    text = re.sub(r"^######\s+(.+)$", r"====== \1 ======", text, flags=re.MULTILINE)
    text = re.sub(r"^#####\s+(.+)$", r"===== \1 =====", text, flags=re.MULTILINE)
    text = re.sub(r"^####\s+(.+)$", r"==== \1 ====", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+(.+)$", r"=== \1 ===", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.+)$", r"== \1 ==", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.+)$", r"= \1 =", text, flags=re.MULTILINE)

    # Code blocks: ```lang\ncode\n``` -> {{code language="lang"}}code{{/code}}
    def _replace_code_block(m):
        lang = m.group(1) or ""
        code = m.group(2)
        if lang:
            return f"{{{{code language='{lang}'}}}}\n{code}\n{{{{/code}}}}"
        return f"{{{{code}}}}\n{code}\n{{{{/code}}}}"

    text = re.sub(r"```(\w*)\n(.*?)```", _replace_code_block, text, flags=re.DOTALL)

    # Inline code: `text` -> ##text##
    text = re.sub(r"`([^`]+)`", r"##\1##", text)

    # Bold: **text** -> **text**  (same in xwiki)
    # Italic: *text* -> //text//  (but avoid ** matches)
    text = re.sub(r"(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)", r"//\1//", text)

    # Links: [text](url) -> [[text>>url]]
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[[\1>>\2]]", text)

    # Images: ![alt](url) -> [[image:url||alt="alt"]]
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'[[image:\2||alt="\1"]]', text)

    # Horizontal rule
    text = re.sub(r"^---+$", "----", text, flags=re.MULTILINE)

    return text


def _build_page_content(repo: dict, readme: str | None, languages: dict) -> str:
    """Build XWiki 2.1 page content from repo data."""
    lines = [
        f"= {repo['name']} =",
        "",
        f"**Description:** {repo.get('description') or 'No description'}",
        f"**URL:** [[{repo['html_url']}]]",
        f"**Stars:** {repo.get('stargazers_count', 0)} | "
        f"**Forks:** {repo.get('forks_count', 0)} | "
        f"**Language:** {repo.get('language') or 'N/A'}",
        f"**Last updated:** {repo.get('updated_at', 'unknown')}",
        f"**Default branch:** {repo.get('default_branch', 'main')}",
        "",
    ]

    if languages:
        lines.append("== Languages ==")
        lines.append("")
        total = sum(languages.values())
        for lang, bytes_count in sorted(languages.items(), key=lambda x: -x[1]):
            pct = (bytes_count / total * 100) if total > 0 else 0
            lines.append(f"* **{lang}**: {pct:.1f}%")
        lines.append("")

    if readme:
        lines.append("----")
        lines.append("")
        lines.append("== README ==")
        lines.append("")
        lines.append(_md_to_xwiki(readme))

    return "\n".join(lines)


@router.post("/sync", response_model=GitHubSyncResponse)
async def sync_repos(request: GitHubSyncRequest | None = None):
    """Sync GitHub repos to XWiki pages under 'GitHub' space."""
    synced = []
    errors = []

    if request and request.repos:
        repos_data = []
        for repo_name in request.repos:
            try:
                info = await github_client.get_repo_info(settings.github_user, repo_name)
                repos_data.append(info)
            except Exception as e:
                errors.append(f"{repo_name}: {e}")
    else:
        repos_data = await github_client.list_repos()

    for repo in repos_data:
        name = repo["name"]
        try:
            readme = await github_client.get_readme(settings.github_user, name)
            languages = await github_client.get_repo_languages(settings.github_user, name)
            content = _build_page_content(repo, readme, languages)
            page_name = _sanitize_page_name(name)
            await xwiki_client.put_page("GitHub", page_name, name, content)
            synced.append(name)
            logger.info("Synced repo: %s", name)
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.error("Failed to sync %s: %s", name, e)

    return GitHubSyncResponse(synced=synced, errors=errors, total=len(synced))
