"""FastAPI application entry point."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.agent.graph import create_agent
from app.api import routes
from app.config import settings
from app.observability import emit_metric, setup_structured_logging
from app.rag.retriever import FormattedRetriever
from app.rag.store import load_vector_store
from app.storage.orders import initialize_order_store

setup_structured_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load FAISS index and initialize agent on startup."""
    import os

    logger.info(
        "startup_env_check",
        extra={
            "ORDER_SEED_ON_STARTUP_env": os.getenv("ORDER_SEED_ON_STARTUP"),
            "order_seed_on_startup_setting": settings.order_seed_on_startup,
        },
    )
    initialize_order_store()
    logger.info("Order store initialized")

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


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    """Emit baseline request logs and latency metrics for all API endpoints."""
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception(
            "http_request_failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "latency_ms": latency_ms,
            },
        )
        emit_metric(
            "HttpRequestLatency",
            latency_ms,
            unit="Milliseconds",
            dimensions={"Path": request.url.path, "Method": request.method},
            properties={"status_code": 500},
        )
        emit_metric(
            "HttpServerError",
            1,
            dimensions={"Path": request.url.path, "Method": request.method},
        )
        raise

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    status_code = response.status_code
    logger.info(
        "http_request_completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "latency_ms": latency_ms,
        },
    )
    emit_metric(
        "HttpRequestLatency",
        latency_ms,
        unit="Milliseconds",
        dimensions={"Path": request.url.path, "Method": request.method},
        properties={"status_code": status_code},
    )
    emit_metric(
        "HttpRequestCount",
        1,
        dimensions={"Path": request.url.path, "Method": request.method},
        properties={"status_code": status_code},
    )
    if status_code >= 500:
        emit_metric(
            "HttpServerError",
            1,
            dimensions={"Path": request.url.path, "Method": request.method},
            properties={"status_code": status_code},
        )

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(routes.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
