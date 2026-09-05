import asyncio
import json
import re
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID, uuid4

from .models import (
    OpenPencilProfile,
    RunCreate,
    RunStage,
    RunStatus,
    RunView,
    SessionView,
    UiSpecification,
    WorkflowEvent,
    utc_now,
)
from .store_schema import initialize_schema

T = TypeVar("T")


def output_file_for_run(screen_name: str, run_id: UUID) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", screen_name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if name.lower().endswith(".fig"):
        name = name[:-4].rstrip(" .")
    name = (name[:100].rstrip(" .") or "Untitled") + ".fig"
    return f"generated/{run_id}/{name}"


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._event_lock = asyncio.Lock()

    async def initialize(self) -> None:
        await self._call(self._initialize)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            initialize_schema(db)

    async def create_session(self, title: str) -> SessionView:
        now = utc_now()
        session = SessionView(id=uuid4(), title=title, created_at=now, updated_at=now)
        await self._execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (str(session.id), session.title, now.isoformat(), now.isoformat()),
        )
        return session

    async def list_sessions(self) -> list[SessionView]:
        rows = await self._fetchall("SELECT * FROM sessions ORDER BY updated_at DESC")
        return [SessionView.model_validate(dict(row)) for row in rows]

    async def get_session(self, session_id: UUID) -> SessionView | None:
        row = await self._fetchone("SELECT * FROM sessions WHERE id = ?", (str(session_id),))
        return SessionView.model_validate(dict(row)) if row else None

    async def create_run(self, session_id: UUID, request: RunCreate) -> RunView:
        now = utc_now()
        run_id = uuid4()
        profile = request.mcp_profile
        if profile:
            profile = profile.model_copy(
                update={
                    "output_file": output_file_for_run(request.screen_name, run_id),
                    "target_mode": "new_file",
                }
            )
        run = RunView(
            id=run_id,
            session_id=session_id,
            revision=1,
            prompt=request.prompt,
            screen_name=request.screen_name,
            platform=request.platform,
            stage=RunStage.REQUIREMENT,
            status=RunStatus.QUEUED,
            library_ids=request.library_ids,
            mcp_profile=profile,
            created_at=now,
            updated_at=now,
        )
        await self._execute(
            "INSERT INTO runs (id, session_id, revision, prompt, screen_name, platform, "
            "stage, status, library_ids, mcp_profile, specification, error, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(run.id),
                str(run.session_id),
                run.revision,
                run.prompt,
                run.screen_name,
                run.platform,
                run.stage,
                run.status,
                json.dumps(run.library_ids),
                profile.model_dump_json() if profile else None,
                None,
                None,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        return run

    async def list_runs(self, session_id: UUID) -> list[RunView]:
        rows = await self._fetchall(
            "SELECT * FROM runs WHERE session_id=? ORDER BY created_at DESC", (str(session_id),)
        )
        return [self._run_from_row(row) for row in rows]

    async def get_run(self, run_id: UUID) -> RunView | None:
        row = await self._fetchone("SELECT * FROM runs WHERE id = ?", (str(run_id),))
        return self._run_from_row(row) if row else None

    async def update_run(
        self,
        run_id: UUID,
        *,
        stage: RunStage | None = None,
        status: RunStatus | None = None,
        specification: UiSpecification | None = None,
        error: dict[str, Any] | None = None,
        intent: str | None = None,
        assistant_message: str | None = None,
    ) -> RunView:
        now = utc_now().isoformat()
        await self._execute(
            "UPDATE runs SET stage=COALESCE(?, stage), status=COALESCE(?, status), specification=COALESCE(?, specification), "
            "error=?, intent=COALESCE(?, intent), assistant_message=COALESCE(?, assistant_message), "
            "updated_at=? WHERE id=?",
            (
                stage,
                status,
                specification.model_dump_json(by_alias=True) if specification else None,
                json.dumps(error) if error else None,
                intent,
                assistant_message,
                now,
                str(run_id),
            ),
        )
        run = await self.get_run(run_id)
        if run is None:
            raise LookupError(str(run_id))
        return run

    async def bump_revision(self, run_id: UUID) -> RunView:
        await self._execute(
            "UPDATE runs SET revision=revision+1, stage=?, status=?, error=NULL, updated_at=? WHERE id=?",
            (RunStage.SPECIFICATION, RunStatus.QUEUED, utc_now().isoformat(), str(run_id)),
        )
        run = await self.get_run(run_id)
        if run is None:
            raise LookupError(str(run_id))
        return run

    async def update_mcp_profile(
        self,
        run_id: UUID,
        profile: OpenPencilProfile,
    ) -> RunView:
        run = await self.get_run(run_id)
        if run is None:
            raise LookupError(str(run_id))
        profile = profile.model_copy(
            update={
                "output_file": output_file_for_run(run.screen_name, run.id),
                "target_mode": "new_file",
            }
        )
        await self._execute(
            "UPDATE runs SET mcp_profile=?, updated_at=? WHERE id=?",
            (profile.model_dump_json(), utc_now().isoformat(), str(run_id)),
        )
        run = await self.get_run(run_id)
        if run is None:
            raise LookupError(str(run_id))
        return run

    async def add_event(self, run_id: UUID, revision: int, event_type: str, payload: dict[str, Any]) -> WorkflowEvent:
        async with self._event_lock:
            for attempt in range(5):
                try:
                    row = await self._fetchone(
                        "SELECT COALESCE(MAX(sequence), 0) AS value FROM events WHERE run_id = ?",
                        (str(run_id),),
                    )
                    event = WorkflowEvent(
                        run_id=run_id,
                        revision=revision,
                        sequence=int(row["value"]) + 1,
                        type=event_type,
                        payload=payload,
                    )
                    await self._execute(
                        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(event.id),
                            str(run_id),
                            revision,
                            event.sequence,
                            event.type,
                            json.dumps(payload),
                            event.time.isoformat(),
                        ),
                    )
                    return event
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e) and attempt < 4:
                        await asyncio.sleep(0.05 * (attempt + 1))
                        continue
                    raise
            raise RuntimeError("Failed to allocate event sequence after retries")

    async def list_events(self, run_id: UUID, after: int = 0) -> list[WorkflowEvent]:
        rows = await self._fetchall(
            "SELECT * FROM events WHERE run_id=? AND sequence>? ORDER BY sequence",
            (str(run_id), after),
        )
        return [
            WorkflowEvent(
                id=row["id"],
                run_id=row["run_id"],
                revision=row["revision"],
                sequence=row["sequence"],
                type=row["event_type"],
                time=row["created_at"],
                payload=json.loads(row["payload"]),
            )
            for row in rows
        ]

    async def add_review(self, run_id: UUID, revision: int, checkpoint: str, decision: str, feedback: str) -> None:
        await self._execute(
            "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                str(run_id),
                revision,
                checkpoint,
                decision,
                feedback,
                utc_now().isoformat(),
            ),
        )

    async def set_artifact(self, run_id: UUID, revision: int, key: str, value: dict[str, Any] | list[Any]) -> None:
        await self._execute(
            "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(run_id, revision, artifact_key) DO UPDATE SET value=excluded.value",
            (str(run_id), revision, key, json.dumps(value), utc_now().isoformat()),
        )

    async def get_artifact(self, run_id: UUID, revision: int, key: str) -> Any | None:
        row = await self._fetchone(
            "SELECT value FROM artifacts WHERE run_id=? AND revision=? AND artifact_key=?",
            (str(run_id), revision, key),
        )
        return json.loads(row["value"]) if row else None

    async def list_artifacts(self, run_id: UUID, revision: int) -> dict[str, Any]:
        rows = await self._fetchall(
            "SELECT artifact_key, value FROM artifacts WHERE run_id=? AND revision=?",
            (str(run_id), revision),
        )
        return {row["artifact_key"]: json.loads(row["value"]) for row in rows}

    def _run_from_row(self, row: sqlite3.Row) -> RunView:
        value = dict(row)
        value["library_ids"] = json.loads(value["library_ids"])
        value["mcp_profile"] = json.loads(value["mcp_profile"]) if value["mcp_profile"] else None
        value["specification"] = json.loads(value["specification"]) if value["specification"] else None
        value["error"] = json.loads(value["error"]) if value["error"] else None
        return RunView.model_validate(value)

    async def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        def execute() -> None:
            with self._connect() as db:
                db.execute(sql, params)

        await self._call(execute)

    async def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        def fetch() -> sqlite3.Row | None:
            with self._connect() as db:
                return db.execute(sql, params).fetchone()

        return await self._call(fetch)

    async def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        def fetch() -> list[sqlite3.Row]:
            with self._connect() as db:
                return db.execute(sql, params).fetchall()

        return await self._call(fetch)

    async def _call(self, function: Callable[[], T]) -> T:
        return await asyncio.to_thread(function)
