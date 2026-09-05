from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl

from .errors import not_found
from .llm import STRUCTURED_PARSER_VERSION
from .models import (
    DesignSystemView,
    OpenPencilProfile,
    ReviewCreate,
    RunArtifacts,
    RunCreate,
    RunRetry,
    RunView,
    SessionCreate,
    SessionView,
)
from .openpencil_client import OpenPencilCapability

router = APIRouter(prefix="/api/v1")


class McpProbeRequest(BaseModel):
    endpoint: HttpUrl


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "llmConfigured": bool(settings.api_key and settings.base_url),
        "model": settings.llm_model,
        "structuredParser": STRUCTURED_PARSER_VERSION,
        "apiVersion": "v1",
    }


@router.post("/sessions", response_model=SessionView, status_code=status.HTTP_201_CREATED)
async def create_session(request: Request, body: SessionCreate) -> SessionView:
    return await request.app.state.store.create_session(body.title.strip() or "Untitled session")


@router.get("/sessions", response_model=list[SessionView])
async def list_sessions(request: Request) -> list[SessionView]:
    return await request.app.state.store.list_sessions()


@router.get("/sessions/{session_id}/runs", response_model=list[RunView])
async def list_runs(request: Request, session_id: UUID) -> list[RunView]:
    if not await request.app.state.store.get_session(session_id):
        raise not_found("Session")
    return await request.app.state.store.list_runs(session_id)


@router.post(
    "/sessions/{session_id}/runs",
    response_model=RunView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_run(request: Request, session_id: UUID, body: RunCreate) -> RunView:
    if not await request.app.state.store.get_session(session_id):
        raise not_found("Session")
    run = await request.app.state.store.create_run(session_id, body)
    await request.app.state.events.emit(
        run.id,
        run.revision,
        "run.created",
        {"stage": run.stage, "message": "Request accepted"},
    )
    request.app.state.runs.start(run.id)
    return run


@router.get("/runs/{run_id}", response_model=RunView)
async def get_run(request: Request, run_id: UUID) -> RunView:
    run = await request.app.state.store.get_run(run_id)
    if run is None:
        raise not_found("Run")
    return run


@router.get("/runs/{run_id}/artifacts", response_model=RunArtifacts)
async def get_run_artifacts(request: Request, run_id: UUID) -> RunArtifacts:
    run = await request.app.state.store.get_run(run_id)
    if run is None:
        raise not_found("Run")
    values = await request.app.state.store.list_artifacts(run.id, run.revision)
    return RunArtifacts.model_validate(values)


@router.get("/runs/{run_id}/preview")
async def get_run_preview(request: Request, run_id: UUID, mode: str = "desktop") -> Response:
    clean_mode = "mobile" if mode == "mobile" else "desktop"
    previews_dir = Path(__file__).resolve().parent.parent / "data" / "previews"

    for ext, media_type in [
        ("jpg", "image/jpeg"),
        ("png", "image/png"),
        ("svg", "image/svg+xml"),
    ]:
        target = previews_dir / f"{run_id}_{clean_mode}.{ext}"
        if target.is_file():
            return Response(
                content=target.read_bytes(),
                media_type=media_type,
                headers={"Cache-Control": "public, max-age=3600"},
            )

    candidates = list(previews_dir.glob(f"{run_id}*.*"))
    if candidates:
        target_file = candidates[0]
        ext = target_file.suffix.lower().lstrip(".")
        media_type = "image/svg+xml" if ext == "svg" else f"image/{ext}"
        return Response(
            content=target_file.read_bytes(),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    raise not_found("Preview image")


@router.get("/runs/{run_id}/events")
async def stream_events(
    request: Request,
    run_id: UUID,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    if not await request.app.state.store.get_run(run_id):
        raise not_found("Run")
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    return StreamingResponse(
        request.app.state.events.subscribe(run_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/reviews", status_code=status.HTTP_202_ACCEPTED)
async def review_run(request: Request, run_id: UUID, body: ReviewCreate) -> dict[str, str]:
    await request.app.state.runs.review(run_id, body)
    return {"status": "accepted"}


@router.post("/runs/{run_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_run(
    request: Request,
    run_id: UUID,
    body: RunRetry | None = None,
) -> dict[str, str]:
    await request.app.state.runs.retry(run_id, body.mcp_profile if body else None)
    return {"status": "accepted"}


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_run(request: Request, run_id: UUID) -> dict[str, str]:
    await request.app.state.runs.cancel(run_id)
    return {"status": "accepted"}


@router.post("/integrations/openpencil/probe", response_model=OpenPencilCapability)
async def probe_mcp(request: Request, body: McpProbeRequest) -> OpenPencilCapability:
    return await request.app.state.openpencil.probe(str(body.endpoint))


@router.post("/integrations/openpencil/components")
async def openpencil_components(
    request: Request,
    profile: OpenPencilProfile,
) -> list[dict[str, object]]:
    components = await request.app.state.openpencil.components(profile)
    return [component.model_dump(mode="json") for component in components]


@router.get("/design-systems", response_model=list[DesignSystemView])
async def list_design_systems(request: Request) -> list[DesignSystemView]:
    settings = request.app.state.settings
    folder = settings.design_data_dir / "design-systems"
    results: list[DesignSystemView] = []
    if not folder.is_dir():
        return results

    for fig in sorted(folder.glob("*.fig")):
        stem = fig.stem.lower()
        if "taptap" in stem or "tap tap" in stem:
            sys_id = "taptap"
            name = "TapTap Design System"
            knowledge_id = "taptap"
        elif "shadcn" in stem:
            sys_id = "shadcn-ui"
            name = "shadcn/ui Design System"
            knowledge_id = "shadcn-ui"
        elif "material" in stem:
            sys_id = "material-ui"
            name = "Material UI (MUI)"
            knowledge_id = "auto"
        elif "v0.3" in stem or "v0" in stem:
            sys_id = "design-system-v0.3"
            name = "Design System v0.3"
            knowledge_id = "auto"
        else:
            sys_id = "custom"
            name = fig.stem
            knowledge_id = "auto"

        results.append(
            DesignSystemView(
                id=sys_id,
                name=name,
                path=str(fig.resolve()),
                knowledge_id=knowledge_id,
            )
        )
    return results
