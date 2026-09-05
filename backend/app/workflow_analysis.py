import json
from typing import Any
from uuid import UUID

from .errors import AppError
from .models import ConversationDecision, RunStage, RunStatus, UiSpecification


def _conversation_context(previous: list[Any]) -> str:
    """Keep follow-up intent without sending entire historical specifications."""
    turns: list[dict[str, Any]] = []
    for item in reversed(previous):
        turn: dict[str, Any] = {
            "user": item.prompt,
            "assistant": item.assistant_message or "",
            "intent": item.intent,
        }
        if item.specification:
            turn["design"] = {
                "screen_name": item.specification.screen_name,
                "platform": item.specification.platform,
                "summary": item.specification.summary,
            }
        turns.append(turn)
    return json.dumps(turns, ensure_ascii=False) if turns else "[]"


async def analyze_request(owner: Any, run_id: UUID, feedback: str) -> None:
    run = await owner.store.get_run(run_id)
    if run is None:
        return
    try:
        await owner.store.update_run(
            run.id, stage=RunStage.REQUIREMENT, status=RunStatus.RUNNING
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "stage.changed",
            {"stage": "requirement", "message": "Understanding your message"},
        )
        previous = [
            item
            for item in await owner.store.list_runs(run.session_id)
            if item.id != run.id
        ][:6]
        history = _conversation_context(previous)
        decision = await owner.llm.structured(
            prompt=owner.prompts.render(
                "router", user_request=run.prompt, conversation_history=history
            ),
            schema=ConversationDecision,
        )
        if decision.intent == "chat":
            await owner.store.update_run(
                run.id,
                stage=RunStage.FINISHED,
                status=RunStatus.COMPLETED,
                intent="chat",
                assistant_message=decision.reply,
            )
            await owner.events.emit(
                run.id, run.revision, "assistant.message", {"message": decision.reply}
            )
            return

        await owner.store.update_run(
            run.id,
            stage=RunStage.SPECIFICATION,
            status=RunStatus.RUNNING,
            intent="design",
            assistant_message=decision.reply,
        )
        await owner.events.emit(
            run.id, run.revision, "assistant.message", {"message": decision.reply}
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "stage.changed",
            {"stage": "specification", "message": "Structuring the UI requirement"},
        )
        prompt = owner.prompts.render(
            "analyzer",
            user_request=run.prompt,
            conversation_history=history,
            screen_name=run.screen_name,
            platform=run.platform,
            revision_feedback=feedback,
        )
        specification = await owner.llm.structured(
            prompt=prompt, schema=UiSpecification
        )
        await owner.store.update_run(
            run.id,
            stage=RunStage.REVIEW_SPEC,
            status=RunStatus.WAITING_REVIEW,
            specification=specification,
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "specification.ready",
            {"specification": specification.model_dump(mode="json")},
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "review.required",
            {
                "checkpoint": "specification",
                "message": "Review the structure before component discovery.",
            },
        )
    except AppError as error:
        await owner._fail(run.id, run.revision, error)
    except Exception as error:
        await owner._fail(
            run.id,
            run.revision,
            AppError("WORKFLOW_FAILED", "Workflow failed", str(error), 500, True),
        )
