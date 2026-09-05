from typing import Any

from mcp import ClientSession

from .models import ComponentBindingSet
from .openpencil_client import OpenPencilClient


def small_instances(node: Any) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    if not isinstance(node, dict):
        return values
    if node.get("type") == "INSTANCE":
        width = node.get("width", node.get("w", 0))
        height = node.get("height", node.get("h", 0))
        if isinstance(width, int | float) and isinstance(height, int | float) and (width < 44 or height < 44):
            values.append({"id": node.get("id"), "width": width, "height": height})
    for child in node.get("children", []):
        values.extend(small_instances(child))
    return values


async def keep_fallbacks(
    client: OpenPencilClient,
    session: ClientSession,
    document_id: str,
    page_id: str,
    bindings: ComponentBindingSet,
) -> int:
    kept = 0
    for binding in bindings.bindings:
        if binding.status == "resolved":
            continue
        matches = await client._call(session, "find_nodes", {
            "name": f"slot::{binding.node_id}", "document_id": document_id, "page_id": page_id,
        })
        for node in matches.get("nodes", []):
            await client._call(session, "update_node", {
                "id": node["id"], "name": f"fallback::{binding.node_id}",
                "document_id": document_id, "page_id": page_id,
            })
            kept += 1
    return kept
