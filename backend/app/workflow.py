import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from .errors import AppError
from .knowledge import KnowledgeIndex
from .llm import AdkProvider
from .models import OpenPencilProfile, ReviewCreate, RunStage, RunStatus
from .openpencil import OpenPencilGateway
from .prompts import PromptLibrary
from .store import Store
from .stream import EventStream
from .workflow_analysis import analyze_request
from .workflow_build import build_after_review
from .workflow_review import HumanReviewFlow


class RunService:
    def __init__(
        self,
        store: Store,
        events: EventStream,
        llm: AdkProvider,
        prompts: PromptLibrary,
        openpencil: OpenPencilGateway,
        knowledge: KnowledgeIndex,
    ) -> None:
        self.store = store
        self.events = events
        self.llm = llm
        self.prompts = prompts
        self.openpencil = openpencil
        self.knowledge = knowledge
        self.tasks: dict[UUID, asyncio.Task[None]] = {}
        self.human_review = HumanReviewFlow(self)

    def _spawn(
        self, run_id: UUID, operation: Coroutine[Any, Any, None], name: str
    ) -> None:
        existing = self.tasks.get(run_id)
        if existing and not existing.done():
            existing.cancel()
        task = asyncio.create_task(operation, name=name)
        self.tasks[run_id] = task

        def discard(completed: asyncio.Task[None]) -> None:
            if self.tasks.get(run_id) is completed:
                self.tasks.pop(run_id, None)

        task.add_done_callback(discard)

    def start(self, run_id: UUID, feedback: str = "None") -> None:
        self._spawn(run_id, self.analyze(run_id, feedback), f"analyze:{run_id}")

    async def analyze(self, run_id: UUID, feedback: str = "None") -> None:
        await analyze_request(self, run_id, feedback)

    async def continue_after_review(self, run_id: UUID) -> None:
        await build_after_review(self, run_id)

    async def review(self, run_id: UUID, request: ReviewCreate) -> None:
        await self.human_review.review(run_id, request)

    async def retry(
        self, run_id: UUID, profile: OpenPencilProfile | None = None
    ) -> None:
        await self.human_review.retry(run_id, profile)

    async def cancel(self, run_id: UUID) -> None:
        await self.human_review.cancel(run_id)

    async def _block(self, run_id: UUID, revision: int, error: AppError) -> None:
        run = await self.store.get_run(run_id)
        payload = self._problem(error, run.stage if run else None)
        await self.store.update_run(
            run_id, stage=RunStage.BLOCKED, status=RunStatus.BLOCKED, error=payload
        )
        await self.events.emit(run_id, revision, "action.required", payload)

    async def _fail(self, run_id: UUID, revision: int, error: AppError) -> None:
        run = await self.store.get_run(run_id)
        payload = self._problem(error, run.stage if run else None)
        await self.store.update_run(
            run_id, stage=RunStage.FAILED, status=RunStatus.FAILED, error=payload
        )
        await self.events.emit(run_id, revision, "run.failed", payload)

    @staticmethod
    def _problem(error: AppError, stage: RunStage | None = None) -> dict[str, Any]:
        return {
            "code": error.code,
            "title": error.title,
            "detail": error.detail,
            "retryable": error.retryable,
            "action": error.action,
            "stage": stage.value if stage else None,
        }

    async def shutdown(self) -> None:
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
