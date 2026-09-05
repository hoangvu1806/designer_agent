from typing import Any

from .models import ComponentBinding, ComponentBindingSet


def validate_bindings(
    requirements: list[dict[str, Any]],
    candidates: list[Any],
    bindings: ComponentBindingSet,
) -> ComponentBindingSet:
    """Canonicalize LLM choices against inspected metadata; never trust copied labels."""
    by_id = {item.component_id: item for item in candidates}
    by_path = {item.canonical_path: item for item in candidates}
    returned = {item.node_id: item for item in bindings.bindings}
    normalized: list[ComponentBinding] = []
    for requirement in requirements:
        node_id = requirement["node_id"]
        binding = returned.get(node_id)
        if binding is None or binding.status != "resolved":
            normalized.append(binding or _unresolved(node_id, "No compatible component selected"))
            continue
        candidate = by_id.get(binding.component_id or "")
        candidate = candidate or by_path.get(binding.canonical_path or "")
        if candidate is None:
            normalized.append(_unresolved(node_id, "Selected component was not inspected"))
            continue
        normalized.append(
            binding.model_copy(
                update={
                    "component_id": candidate.component_id,
                    "library_id": candidate.library_id,
                    "canonical_path": candidate.canonical_path,
                    "selected_variant": candidate.variant_name,
                    "text_values": _text_values(binding.text_values, candidate.text_slots),
                }
            )
        )
    return ComponentBindingSet(bindings=normalized)


def _unresolved(node_id: str, reason: str) -> ComponentBinding:
    return ComponentBinding(node_id=node_id, status="unresolved", reason=reason)


def _text_values(values: dict[str, str], slots: list[str]) -> dict[str, str]:
    if not values or not slots:
        return {}
    result: dict[str, str] = {}
    for key, value in values.items():
        wanted = _normalized(key.removeprefix("text:"))
        matches = [slot for slot in slots if _slot_matches(wanted, slot)]
        if len(matches) == 1:
            result[matches[0]] = value
        elif len(values) == 1 and len(slots) == 1:
            result[slots[0]] = value
    return result


def _slot_matches(wanted: str, slot: str) -> bool:
    normalized = _normalized(slot.removeprefix("text:"))
    leaf = _normalized(slot.rsplit("/", 1)[-1].removeprefix("text:"))
    return wanted in {normalized, leaf}


def _normalized(value: str) -> str:
    return " ".join(part for part in value.lower().replace("/", " ").split() if part)
