import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def generate(prompt: str, system: str | None = None) -> str:
    """Call Ollama /api/generate and return the response text."""
    payload: dict = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.ollama_url}/api/generate",
            json=payload,
        )
        resp.raise_for_status()
    return resp.json()["response"]


async def embeddings(text: str) -> list[float]:
    """Get embeddings for text via Ollama."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.ollama_url}/api/embeddings",
            json={
                "model": settings.ollama_embed_model,
                "prompt": text,
            },
        )
        resp.raise_for_status()
    return resp.json()["embedding"]


async def summarize(text: str) -> str:
    """Summarize text using Ollama."""
    return await generate(
        prompt=f"Summarize the following text concisely:\n\n{text}",
        system="You are a technical documentation assistant. Provide clear, concise summaries.",
    )


async def generate_runbook(text: str) -> str:
    """Generate a runbook from text using Ollama."""
    return await generate(
        prompt=f"Create a step-by-step operational runbook from this information:\n\n{text}",
        system="You are an infrastructure documentation expert. Generate clear, actionable runbooks with numbered steps, prerequisites, and rollback procedures.",
    )


async def classify(text: str) -> str:
    """Classify text into categories using Ollama."""
    return await generate(
        prompt=f"Classify this text into one or more categories (Network, Security, Storage, Compute, Application, Monitoring, Other) and explain why:\n\n{text}",
        system="You are a technical content classifier. Return a JSON object with 'categories' (list) and 'reasoning' (string).",
    )
