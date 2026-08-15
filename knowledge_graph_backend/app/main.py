from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import router
from .config import get_settings
from .database import create_schema
from .runtime import get_graph_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_schema()
    yield
    get_graph_repository().close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Career Prism Knowledge Graph API",
        version=__version__,
        description="Evidence-backed, versioned job-skill knowledge graph backend.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-Admin-Key", "X-Request-Id"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-Id") or f"req_{uuid.uuid4().hex}"
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.include_router(router)
    return app


app = create_app()

