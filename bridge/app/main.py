import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import ai_endpoints, anythingllm, github_sync, word_import

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.getLogger(__name__).info("XWiki Bridge starting up")
    yield
    logging.getLogger(__name__).info("XWiki Bridge shutting down")


app = FastAPI(
    title="XWiki Bridge",
    description="Bridge between XWiki, GitHub, Ollama, and AnythingLLM",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(github_sync.router)
app.include_router(word_import.router)
app.include_router(ai_endpoints.router)
app.include_router(anythingllm.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "xwiki-bridge"}
