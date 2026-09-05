import asyncio
import json
from typing import Any
from uuid import UUID

from .errors import AppError, not_found
from .models import OpenPencilProfile, ReviewCreate, RunStage, RunStatus, UiSpecification


class HumanReviewFlow:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.store = owner.store
        self.events = owner.events
        self.llm = owner.llm
        self.prompts = owner.prompts

    async def review(self, run_id: UUID, request: ReviewCreate) -> None:
        run = await self.store.get_run(run_id)
        if run is None:
            raise not_found("Run")
        if request.revision != run.revision:
            raise AppError("STALE_REVISION", "Review is stale", "Reload the current revision.", 409)
        expected = (
            "specification"
            if run.stage == RunStage.REVIEW_SPEC
            else "final"
            if run.stage == RunStage.REVIEW_FINAL
            else None
        )
        if request.checkpoint != expected or run.status != RunStatus.WAITING_REVIEW:
            raise AppError(
                "INVALID_REVIEW_CHECKPOINT",
                "Review is not available",
                f"Run is currently at {run.stage} ({run.status}).",
                409,
            )
        if request.checkpoint == "specification" and request.mcp_profile:
            run = await self.store.update_mcp_profile(run.id, request.mcp_profile)
        await self.store.add_review(
            run.id,
            run.revision,
            request.checkpoint,
            request.decision,
            request.feedback,
        )
        if request.decision == "approved" and request.checkpoint == "specification":
            await self._approve_specification(run)
        elif request.decision == "approved":
            await self._approve_final(run, request)
        elif request.decision == "changes_requested":
            await self._request_changes(run, request)
        else:
            await self.store.update_run(
                run.id,
                stage=RunStage.BLOCKED,
                status=RunStatus.CANCELLED,
            )
            await self.events.emit(
                run.id,
                run.revision,
                "run.cancelled",
                {
                    "message": "The current design was rejected.",
                },
            )

    async def _approve_specification(self, run: Any) -> None:
        await self.store.update_run(
            run.id,
            stage=run.stage,
            status=RunStatus.RUNNING,
        )
        await self.events.emit(
            run.id,
            run.revision,
            "review.accepted",
            {
                "checkpoint": "specification",
            },
        )
        if not run.mcp_profile:
            await self.owner._block(
                run.id,
                run.revision,
                AppError(
                    "MCP_CONTEXT_REQUIRED",
                    "OpenPencil context is required",
                    "Configure the MCP endpoint and component source before continuing.",
                    409,
                    action="Open Settings, complete OpenPencil configuration, then approve again.",
                ),
            )
            return
        capability = await self.owner.openpencil.probe(run.mcp_profile.endpoint)
        if not capability.reachable or not capability.file_operations:
            await self.owner._block(
                run.id,
                run.revision,
                AppError(
                    "OPENPENCIL_MCP_UNAVAILABLE",
                    "OpenPencil MCP is not ready",
                    f"{capability.message} Endpoint: {run.mcp_profile.endpoint}",
                    502,
                    retryable=True,
                    action="Open Connections, test the current endpoint, then retry this stage.",
                ),
            )
            return
        self.owner._spawn(
            run.id,
            self.owner.continue_after_review(run.id),
            f"continue:{run.id}",
        )

    async def _approve_final(self, run: Any, request: ReviewCreate) -> None:
        layout = await self.store.get_artifact(run.id, run.revision, "layout_review")
        if request.checkpoint == "final" and (not layout or layout.get("status") != "valid"):
            raise AppError(
                "LAYOUT_NOT_VALID",
                "Layout cannot be approved yet",
                "Blocking layout findings must be corrected before final approval.",
                409,
                action="Request changes and address the layout findings.",
            )
        await self.store.update_run(
            run.id,
            stage=RunStage.FINISHED,
            status=RunStatus.COMPLETED,
        )
        artifact = await self.store.get_artifact(
            run.id,
            run.revision,
            "openpencil_artifact",
        )
        await self.events.emit(
            run.id,
            run.revision,
            "run.finished",
            {
                "message": "Final design approved.",
                "artifact": artifact,
            },
        )
        out_file = artifact.get("output_file") if isinstance(artifact, dict) else getattr(artifact, "output_file", "")
        approved_msg = (
            f"✅ **Thiết kế đã được phê duyệt thành công!**\n\n"
            f"File OpenPencil đã được lưu hoàn tất tại:\n`{out_file}`\n\n"
            f"Bạn có thể mở trực tiếp trong OpenPencil Studio để xem, chỉnh sửa hoặc xuất mã nguồn bất cứ lúc nào."
        )
        await self.store.update_run(run.id, assistant_message=approved_msg)
        await self.events.emit(run.id, run.revision, "assistant.message", {"message": approved_msg})

    async def _request_changes(self, run: Any, request: ReviewCreate) -> None:
        await self.events.emit(
            run.id,
            run.revision,
            "review.changes_requested",
            {
                "checkpoint": request.checkpoint,
                "feedback": request.feedback,
            },
        )
        await self.store.bump_revision(run.id)
        self.owner._spawn(
            run.id,
            self.revise(run.id, request.feedback, request.checkpoint),
            f"revise:{run.id}",
        )

    async def retry(
        self,
        run_id: UUID,
        profile: OpenPencilProfile | None = None,
    ) -> None:
        run = await self.store.get_run(run_id)
        if run is None:
            raise not_found("Run")
        if run.status not in {RunStatus.FAILED, RunStatus.BLOCKED}:
            raise AppError(
                "RUN_NOT_RETRYABLE",
                "Run cannot be retried",
                f"Current status is {run.status}.",
                409,
            )
        if profile:
            run = await self.store.update_mcp_profile(run.id, profile)
        failed_stage = str((run.error or {}).get("stage", ""))
        build_stages = {"components", "binding", "assembly", "layout_check"}
        resume_build = (
            run.specification is not None
            and run.mcp_profile is not None
            and failed_stage in build_stages
        )
        stage = RunStage.COMPONENTS if resume_build else RunStage.REQUIREMENT
        await self.store.update_run(run.id, stage=stage, status=RunStatus.QUEUED)
        await self.events.emit(
            run.id,
            run.revision,
            "run.retrying",
            {
                "stage": stage,
                "message": "Retrying the last recoverable workflow section",
            },
        )
        if resume_build:
            self.owner._spawn(
                run.id,
                self.owner.continue_after_review(run.id),
                f"retry:{run.id}",
            )
        else:
            self.owner.start(run.id)

    async def cancel(self, run_id: UUID) -> None:
        run = await self.store.get_run(run_id)
        if run is None:
            raise not_found("Run")
        task = self.owner.tasks.pop(run.id, None)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self.store.update_run(
            run.id,
            stage=RunStage.BLOCKED,
            status=RunStatus.CANCELLED,
        )
        await self.events.emit(
            run.id,
            run.revision,
            "run.cancelled",
            {
                "message": "Run cancelled by the user.",
            },
        )

    async def revise(self, run_id: UUID, feedback: str, checkpoint: str) -> None:
        run = await self.store.get_run(run_id)
        if not run or not run.specification:
            return
        try:
            await self.store.update_run(
                run.id,
                stage=RunStage.SPECIFICATION,
                status=RunStatus.RUNNING,
            )
            await self.events.emit(
                run.id,
                run.revision,
                "stage.changed",
                {
                    "stage": "specification",
                    "message": "Applying review feedback",
                },
            )
            bindings = await self.store.get_artifact(
                run.id,
                max(1, run.revision - 1),
                "component_bindings",
            )
            layout = await self.store.get_artifact(
                run.id,
                max(1, run.revision - 1),
                "layout_review",
            )
            prompt = self.prompts.render(
                "revision",
                feedback=feedback or "No written notes were provided.",
                ui_specification=run.specification.model_dump_json(),
                checkpoint=checkpoint,
                findings=json.dumps(layout or {}, ensure_ascii=False),
                immutable_bindings=json.dumps(bindings or {}, ensure_ascii=False),
            )
            specification = await self.llm.structured(prompt=prompt, schema=UiSpecification)
            await self.store.update_run(
                run.id,
                stage=RunStage.REVIEW_SPEC,
                status=RunStatus.WAITING_REVIEW,
                specification=specification,
            )
            await self.events.emit(
                run.id,
                run.revision,
                "specification.ready",
                {
                    "specification": specification.model_dump(mode="json"),
                    "revision": run.revision,
                },
            )
            await self.events.emit(
                run.id,
                run.revision,
                "review.required",
                {
                    "checkpoint": "specification",
                    "message": "Review the revised structure before rebuilding.",
                },
            )
        except AppError as error:
            await self.owner._fail(run.id, run.revision, error)
        except Exception as error:
            await self.owner._fail(
                run.id,
                run.revision,
                AppError(
                    "REVISION_FAILED",
                    "Revision failed",
                    str(error),
                    500,
                    True,
                ),
            )
