from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .errors import AppError
from .knowledge import KnowledgeIndex
from .llm import AdkProvider
from .models import Problem
from .openpencil import OpenPencilGateway
from .prompts import PromptLibrary
from .routes import router
from .store import Store
from .stream import EventStream
from .workflow import RunService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    store = Store(settings.sqlite_path)
    await store.initialize()
    events = EventStream(store)
    openpencil = OpenPencilGateway(settings)
    runs = RunService(
        store,
        events,
        AdkProvider(settings),
        PromptLibrary(),
        openpencil,
        KnowledgeIndex(),
    )
    app.state.settings = settings
    app.state.store = store
    app.state.events = events
    app.state.runs = runs
    app.state.openpencil = openpencil
    yield
    await runs.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Agentic Designer API",
        version="2.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, error: AppError) -> JSONResponse:
        problem = Problem(
            code=error.code,
            title=error.title,
            detail=error.detail,
            retryable=error.retryable,
            action=error.action,
        )
        return JSONResponse(
            status_code=error.status_code,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    return app


app = create_app()
