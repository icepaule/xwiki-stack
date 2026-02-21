import logging

from docx import Document
from fastapi import APIRouter, File, Form, UploadFile

from app.models import WordImportResponse
from app.services import xwiki_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/import", tags=["Import"])


def _docx_to_xwiki(doc: Document) -> str:
    """Convert DOCX content to XWiki syntax."""
    lines = []
    for para in doc.paragraphs:
        style = para.style.name.lower() if para.style else ""
        text = para.text.strip()
        if not text:
            lines.append("")
            continue

        if "heading 1" in style:
            lines.append(f"= {text} =")
        elif "heading 2" in style:
            lines.append(f"== {text} ==")
        elif "heading 3" in style:
            lines.append(f"=== {text} ===")
        elif "list" in style:
            lines.append(f"* {text}")
        else:
            # Handle bold/italic runs
            parts = []
            for run in para.runs:
                t = run.text
                if not t:
                    continue
                if run.bold and run.italic:
                    parts.append(f"**//{ t }//***")
                elif run.bold:
                    parts.append(f"**{t}**")
                elif run.italic:
                    parts.append(f"//{t}//")
                else:
                    parts.append(t)
            lines.append("".join(parts) if parts else text)

    return "\n".join(lines)


@router.post("/word", response_model=WordImportResponse)
async def import_word(
    file: UploadFile = File(...),
    space: str = Form("Imported"),
    title: str = Form(None),
):
    """Import a Word (.docx) file as an XWiki page."""
    content = await file.read()
    from io import BytesIO
    doc = Document(BytesIO(content))

    page_title = title or file.filename.rsplit(".", 1)[0]
    page_name = page_title.replace(" ", "_")

    xwiki_content = _docx_to_xwiki(doc)
    page_url = await xwiki_client.put_page(space, page_name, page_title, xwiki_content)

    logger.info("Imported Word doc '%s' to %s/%s", file.filename, space, page_name)
    return WordImportResponse(page_url=page_url, title=page_title)
