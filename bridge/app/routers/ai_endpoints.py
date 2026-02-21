import logging

from fastapi import APIRouter

from app.config import settings
from app.models import AIRequest, AIResponse
from app.services import ollama_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.post("/summarize", response_model=AIResponse)
async def summarize(request: AIRequest):
    """Summarize text using Ollama."""
    result = await ollama_client.summarize(request.text)
    return AIResponse(result=result, model=settings.ollama_model)


@router.post("/runbook", response_model=AIResponse)
async def generate_runbook(request: AIRequest):
    """Generate a runbook from text using Ollama."""
    result = await ollama_client.generate_runbook(request.text)
    return AIResponse(result=result, model=settings.ollama_model)


@router.post("/classify", response_model=AIResponse)
async def classify(request: AIRequest):
    """Classify text into infrastructure categories."""
    result = await ollama_client.classify(request.text)
    return AIResponse(result=result, model=settings.ollama_model)
