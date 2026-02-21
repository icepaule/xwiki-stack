import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def analyze(scan_type: str, data: dict) -> str:
    """Analyze scan results using Ollama and return a summary."""
    data_str = json.dumps(data, indent=2, default=str)
    # Truncate if too long for context
    if len(data_str) > 8000:
        data_str = data_str[:8000] + "\n... (truncated)"

    prompt = (
        f"Analyze these {scan_type} scan results from a homelab environment. "
        f"Provide:\n"
        f"1. A brief summary of what was found\n"
        f"2. Any potential issues or security concerns\n"
        f"3. Recommendations for improvement\n\n"
        f"Scan data:\n{data_str}"
    )

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "system": "You are an infrastructure documentation expert analyzing scan results. Be concise and actionable.",
                    "stream": False,
                },
            )
            resp.raise_for_status()
        return resp.json()["response"]
    except Exception as e:
        logger.error("Ollama analysis failed: %s", e)
        return f"(AI analysis unavailable: {e})"
