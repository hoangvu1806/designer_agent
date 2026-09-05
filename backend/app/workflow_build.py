import json
from typing import Any
from uuid import UUID

from .binding import validate_bindings
from .errors import AppError
from .layout import deterministic_layout_review, merge_layout_reviews
from .models import (
    ComponentBindingSet,
    LayoutReview,
    OpenPencilArtifact,
    RunStage,
    RunStatus,
    UiNode,
)


def component_requirements(node: UiNode) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    if node.kind == "component" and node.requirement:
        values.append({"node_id": node.id, **node.requirement.model_dump(mode="json")})
    for child in node.children:
        values.extend(component_requirements(child))
    return values


async def build_after_review(owner: Any, run_id: UUID) -> None:
    run = await owner.store.get_run(run_id)
    if not run or not run.specification or not run.mcp_profile:
        return
    try:
        requirements = component_requirements(run.specification.root)
        libraries = list(run.library_ids)
        if run.mcp_profile.knowledge_id != "auto":
            libraries.append(run.mcp_profile.knowledge_id)
        knowledge = owner.knowledge.shortlist(
            requirements, libraries, run.mcp_profile.source_file
        )
        await owner.store.set_artifact(
            run.id, run.revision, "knowledge_snapshot", knowledge
        )
        await owner.store.update_run(
            run.id, stage=RunStage.COMPONENTS, status=RunStatus.RUNNING
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "stage.changed",
            {"stage": "components", "message": "Inspecting the OpenPencil component source"},
        )
        candidates = await owner.openpencil.components(
            run.mcp_profile, requirements, knowledge
        )
        candidate_data = [item.model_dump(mode="json") for item in candidates]
        await owner.store.set_artifact(
            run.id, run.revision, "component_candidates", candidate_data
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "components.discovered",
            {
                "count": len(candidates),
                "source_file": run.mcp_profile.source_file,
                "knowledge_libraries": knowledge["libraries"],
            },
        )
        if requirements and not candidates:
            raise AppError(
                "COMPONENT_DISCOVERY_EMPTY",
                "No matching components were found",
                "The selected OpenPencil source returned no components.",
                409,
                retryable=True,
                action="Choose another source file or revise the component requirements.",
            )

        bindings = ComponentBindingSet(bindings=[])
        if requirements:
            prompt = owner.prompts.render(
                "resolver",
                user_request=run.prompt,
                ui_specification=run.specification.model_dump_json(),
                component_candidates=json.dumps(candidate_data, ensure_ascii=False),
                library_snapshots=json.dumps(knowledge, ensure_ascii=False),
            )
            bindings = await owner.llm.structured(
                prompt=prompt, schema=ComponentBindingSet
            )
            bindings = validate_bindings(requirements, candidates, bindings)
        await owner.store.set_artifact(
            run.id,
            run.revision,
            "component_bindings",
            bindings.model_dump(mode="json"),
        )
        unresolved = [item.node_id for item in bindings.bindings if item.status == "unresolved"]

        await owner.store.update_run(
            run.id, stage=RunStage.BINDING, status=RunStatus.RUNNING
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "bindings.ready",
            {
                "resolved": len(bindings.bindings) - len(unresolved),
                "unresolved": len(unresolved),
                "fallback": unresolved,
            },
        )
        await owner.store.update_run(
            run.id, stage=RunStage.ASSEMBLY, status=RunStatus.RUNNING
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "stage.changed",
            {"stage": "assembly", "message": "Creating an independent OpenPencil design file"},
        )
        result = await owner.openpencil.assemble(
            run.mcp_profile, run.specification, bindings, run_id=str(run.id)
        )
        artifact = OpenPencilArtifact.model_validate(result)
        await owner.store.set_artifact(
            run.id, run.revision, "openpencil_artifact", result
        )
        await owner.events.emit(
            run.id,
            run.revision,
            "openpencil.assembled",
            {**artifact.model_dump(mode="json"), "message": "OpenPencil file created and saved"},
        )
        await review_layout(owner, run.id, run.revision, run, bindings, result)
    except AppError as error:
        if error.code.startswith(("MCP_", "OPENPENCIL_", "COMPONENT", "TARGET_")):
            await owner._block(run.id, run.revision, error)
        else:
            await owner._fail(run.id, run.revision, error)
    except Exception as error:
        await owner._fail(
            run.id,
            run.revision,
            AppError("WORKFLOW_FAILED", "Workflow failed", str(error), 500, True),
        )


async def review_layout(
    owner: Any,
    run_id: UUID,
    revision: int,
    run: Any,
    bindings: ComponentBindingSet,
    result: dict[str, Any],
) -> None:
    await owner.store.update_run(
        run_id, stage=RunStage.LAYOUT_CHECK, status=RunStatus.RUNNING
    )
    prompt = owner.prompts.render(
        "layout-review",
        user_request=run.prompt,
        ui_specification=run.specification.model_dump_json(),
        component_bindings=bindings.model_dump_json(),
        layout_telemetry=json.dumps(result.get("telemetry", {})),
        viewport=f"{run.specification.viewport_width}x{run.specification.viewport_height}",
    )
    deterministic = deterministic_layout_review(
        run.specification,
        result.get("telemetry", {}),
        len([item for item in bindings.bindings if item.status == "resolved"]),
    )
    semantic = await owner.llm.structured(prompt=prompt, schema=LayoutReview)
    review = merge_layout_reviews(deterministic, semantic)
    await owner.store.set_artifact(
        run_id, revision, "layout_review", review.model_dump(mode="json")
    )
    await owner.store.update_run(
        run_id, stage=RunStage.REVIEW_FINAL, status=RunStatus.WAITING_REVIEW
    )
    await owner.events.emit(
        run_id, revision, "layout.checked", review.model_dump(mode="json")
    )
    await owner.events.emit(
        run_id,
        revision,
        "review.required",
        {"checkpoint": "final", "message": "Review the saved OpenPencil design."},
    )
    screen_title = run.specification.screen_name if run.specification else "Giao diện"
    preview_info = result.get("telemetry", {}).get("previews", {})
    desktop_img = preview_info.get("desktop", f"/api/v1/runs/{run_id}/preview?mode=desktop")
    mobile_img = preview_info.get("mobile", f"/api/v1/runs/{run_id}/preview?mode=mobile")

    msg = (
        f"🎉 **Đã hoàn thành thiết kế giao diện cho: {screen_title}!**\n\n"
        f"Giao diện đã được tạo đầy đủ với 3 artboards chuẩn trên OpenPencil Studio:\n"
        f"- 🎨 **Trang 1: Color Palette** — Hệ thống màu sắc thương hiệu và Design Tokens chuẩn hóa.\n"
        f"- 💻 **Trang 2: Desktop Web (1440px)** — Bố cục 2 cột cân đối, typography rõ ràng, không bị tràn chữ.\n"
        f"- 📱 **Trang 3: Mobile Mockup (390px)** — Tối ưu cho thiết bị di động với menu điều hướng gọn gàng.\n\n"
        f"### 💻 Ảnh chụp Mockup Web Desktop (1440px):\n"
        f"![Desktop Web Mockup]({desktop_img})\n\n"
        f"### 📱 Ảnh chụp Mockup Mobile (390px):\n"
        f"![Mobile Mockup]({mobile_img})\n\n"
        f"👉 File thiết kế đã được lưu tại: `{result.get('output_file')}`\n"
        f"Bạn có thể kiểm tra trực tiếp trên OpenPencil Studio hoặc nhấn **Accept Design** ở bảng bên phải để phê duyệt hoàn tất!"
    )
    await owner.store.update_run(run_id, assistant_message=msg)
    await owner.events.emit(run_id, revision, "assistant.message", {"message": msg})
