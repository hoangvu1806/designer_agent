from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.components import ComponentSource
from app.models import OpenPencilProfile
from app.openpencil import OpenPencilGateway


def settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        design_data_dir=tmp_path,
        openpencil_cli="openpencil",
        mcp_timeout_seconds=10,
        openpencil_mcp_auth_token="",
    )


def profile(source: Path, output: Path) -> OpenPencilProfile:
    return OpenPencilProfile(
        endpoint="http://127.0.0.1:7600/mcp",
        source_file=str(source),
        output_file=str(output),
    )


@pytest.mark.asyncio
async def test_catalog_reads_fig_from_disk_without_mcp(tmp_path: Path) -> None:
    source = tmp_path / "library.fig"
    source.write_bytes(b"fig")
    adapter = ComponentSource(settings(tmp_path))  # type: ignore[arg-type]
    adapter._json = AsyncMock(return_value=[{"id": "1:2", "name": "Button", "page": "Actions"}])  # type: ignore[method-assign]

    result = await adapter.discover(profile(source, tmp_path / "output.fig"), None, None)

    assert result[0].component_id == "1:2"
    assert result[0].canonical_path == "Actions/Button"
    arguments = adapter._json.await_args.args  # type: ignore[attr-defined]
    assert arguments[:2] == ("query", str(source.resolve()))
    assert "//COMPONENT" in arguments


@pytest.mark.asyncio
async def test_component_pack_orders_dependencies_before_parent(tmp_path: Path) -> None:
    source = tmp_path / "library.fig"
    source.write_bytes(b"fig")
    dependency = tmp_path / "dependency.jsx"
    dependency.write_text('<Component name="Icon" />', encoding="utf-8")
    parent = tmp_path / "parent.jsx"
    parent.write_text('<Component name="Button"><Instance componentId="icon:1" /></Component>', encoding="utf-8")
    adapter = ComponentSource(settings(tmp_path))  # type: ignore[arg-type]

    async def exported(_: Path, component_id: str) -> Path:
        return dependency if component_id == "icon:1" else parent

    adapter._jsx = exported  # type: ignore[method-assign]

    result = await adapter.pack(str(source), ["button:1"])

    assert [component_id for component_id, _ in result] == ["icon:1", "button:1"]


@pytest.mark.asyncio
async def test_output_materialization_never_opens_source_file(tmp_path: Path) -> None:
    source = tmp_path / "library.fig"
    output = tmp_path / "output.fig"
    source.write_bytes(b"fig")
    gateway = OpenPencilGateway(settings(tmp_path))  # type: ignore[arg-type]
    calls: list[tuple[str, dict[str, object]]] = []

    async def call(_: object, tool: str, arguments: dict[str, object]) -> dict[str, object]:
        calls.append((tool, arguments))
        responses = {
            "new_document": {"documentId": "doc-1"},
            "list_pages": {"pages": []},
            "create_page": {"id": "page-components"},
            "switch_page": {},
            "render": {"id": "local-component"},
            "save_file": {},
        }
        return responses[tool]

    gateway._call = call  # type: ignore[method-assign]
    document_id, mapping, *_ = await gateway._prepare_document(
        object(), profile(source, output), [("source-component", '<Component name="Button" />')]
    )

    assert document_id == "doc-1"
    assert mapping == {"source-component": "local-component"}
    assert all(tool != "open_file" for tool, _ in calls)
    assert calls[0] == ("new_document", {"path": str(output)})


def test_source_auto_resolves_fuzzy_name(tmp_path: Path) -> None:
    systems_dir = tmp_path / "design-systems"
    systems_dir.mkdir(parents=True)
    real_file = systems_dir / "TapTap Design System - Developers (Community).fig"
    real_file.write_bytes(b"fig")

    adapter = ComponentSource(settings(tmp_path))  # type: ignore[arg-type]

    # Test resolving by name with pipe or dash and no extension
    resolved = adapter._source("TapTap Design System | Developers (Community)")
    assert resolved == real_file.resolve()

    # Test resolving by short keyword
    resolved_short = adapter._source("taptap")
    assert resolved_short == real_file.resolve()
