"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import create_agent
from app.api import routes
from app.config import settings
from app.rag.retriever import FormattedRetriever
from app.rag.store import load_vector_store

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load FAISS index and initialize agent on startup."""
    logger.info("Loading FAISS index...")
    vectorstore = load_vector_store(settings.faiss_index_path)
    logger.info("FAISS index loaded")

    retriever = FormattedRetriever(vectorstore, k=4)
    agent = create_agent(retriever)

    routes.set_agent(agent)
    logger.info("Agent initialized")

    yield


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
