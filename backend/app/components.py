import asyncio
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import AppError
from .models import ComponentCandidate, OpenPencilProfile


class ComponentSource:
    """Read immutable component libraries by path through the OpenPencil CLI."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._fingerprints: dict[Path, tuple[int, int, str]] = {}

    async def discover(
        self,
        profile: OpenPencilProfile,
        requirements: list[dict[str, Any]] | None,
        knowledge: dict[str, Any] | None,
    ) -> list[ComponentCandidate]:
        source = self._source(profile.source_file)
        hints = list((knowledge or {}).get("matches", []))
        candidates: dict[str, ComponentCandidate] = {}

        if requirements and hints:
            selected: list[dict[str, Any]] = []
            counts: dict[str, int] = {}
            for hint in hints:
                node_id = str(hint.get("node_id", ""))
                if counts.get(node_id, 0) < 4:
                    selected.append(hint)
                    counts[node_id] = counts.get(node_id, 0) + 1

            for hint in selected:
                component_id = str(hint.get("component_id", ""))
                if not component_id or component_id in candidates:
                    continue
                name = str(hint.get("name") or component_id)
                page = str(hint.get("page") or "")
                text_slots = list(hint.get("text_slots", []))
                candidates[component_id] = ComponentCandidate(
                    component_id=component_id,
                    library_id=str(source),
                    name=name,
                    path=page,
                    canonical_path=str(hint.get("canonical_path", f"{page}/{name}".strip("/"))),
                    width=self._number(hint.get("width")),
                    height=self._number(hint.get("height")),
                    text_slots=text_slots,
                    variant_name=name if "=" in name else None,
                    knowledge_score=int(hint.get("knowledge_score", 0)),
                )

        if not candidates:
            limit = "50" if requirements else "500"
            summaries = self._items(await self._json(
                "query", str(source), "//COMPONENT", "--limit", limit, "--json"
            ))
            hints_by_id = {str(item.get("component_id", "")): item for item in hints}
            for summary in summaries:
                component_id = str(summary.get("id", ""))
                if not component_id or component_id in candidates:
                    continue
                hint = hints_by_id.get(component_id, {})
                name = str(summary.get("name") or hint.get("name") or component_id)
                page = str(summary.get("page") or hint.get("page") or "")
                candidates[component_id] = ComponentCandidate(
                    component_id=component_id,
                    library_id=str(source),
                    name=name,
                    path=page,
                    canonical_path=f"{page}/{name}".strip("/"),
                    width=self._number(summary.get("width")),
                    height=self._number(summary.get("height")),
                    text_slots=list(hint.get("text_slots", [])),
                    variant_name=name if "=" in name else None,
                    knowledge_score=int(hint.get("knowledge_score", 0)),
                )

        return list(candidates.values())

    async def pack(self, source_file: str, component_ids: list[str]) -> list[tuple[str, str]]:
        source = self._source(source_file)
        ordered: list[tuple[str, str]] = []
        visited: set[str] = set()

        async def collect(component_id: str) -> None:
            if component_id in visited:
                return
            visited.add(component_id)
            if len(visited) > 40:
                raise AppError(
                    "COMPONENT_GRAPH_TOO_LARGE", "Component graph is too large", component_id, 409,
                    action="Choose a simpler component variant.",
                )
            jsx = (await self._jsx(source, component_id)).read_text(encoding="utf-8")
            for dependency in re.findall(r'componentId=["{]([^"}]+)', jsx):
                await collect(dependency)
            ordered.append((component_id, jsx))

        for component_id in dict.fromkeys(component_ids):
            await collect(component_id)
        return ordered

    async def _resolve(self, source: Path, hint: dict[str, Any]) -> dict[str, Any]:
        component_id = str(hint.get("component_id", ""))
        if component_id:
            try:
                items = self._items(await self._json("node", str(source), "--id", component_id, "--json"))
                if items:
                    return {**hint, **items[0]}
            except AppError:
                pass
        name = str(hint.get("name", ""))
        items = self._items(await self._json(
            "find", str(source), "--name", name, "--type", "COMPONENT", "--limit", "4", "--json"
        ))
        exact = next((item for item in items if str(item.get("name", "")).casefold() == name.casefold()), None)
        return {**hint, **(exact or items[0])} if items else {}

    async def _jsx(self, source: Path, component_id: str) -> Path:
        folder = self.settings.design_data_dir / "cache" / self._fingerprint(source) / "components"
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / f"{self._safe(component_id)}.jsx"
        if not output.is_file() or not output.stat().st_size:
            await self._run(
                "export", str(source), "--format", "jsx", "--node", component_id,
                "--output", str(output), "--style", "openpencil",
            )
        if not output.is_file() or not output.stat().st_size:
            raise AppError("COMPONENT_EXPORT_FAILED", "Component export failed", component_id, 502, True)
        return output

    async def _json(self, *arguments: str) -> Any:
        output = await self._run(*arguments)
        start = min((index for index in (output.find("["), output.find("{")) if index >= 0), default=-1)
        try:
            value, _ = json.JSONDecoder().raw_decode(output[start:] if start >= 0 else output)
            return value
        except json.JSONDecodeError as error:
            raise AppError(
                "COMPONENT_SOURCE_INVALID", "Component source returned invalid data", output[-500:], 502
            ) from error

    async def _run(self, *arguments: str) -> str:
        configured = Path(self.settings.openpencil_cli)
        script = configured if configured.suffix == ".ts" and configured.is_file() else None
        executable = shutil.which("bun" if script else self.settings.openpencil_cli)
        if not executable:
            raise AppError(
                "COMPONENT_CLI_MISSING", "OpenPencil CLI is unavailable", self.settings.openpencil_cli, 409,
                action="Install or configure OPENPENCIL_CLI, then retry.",
            )
        try:
            async with asyncio.timeout(self.settings.mcp_timeout_seconds):
                process = await asyncio.create_subprocess_exec(
                    executable, *((str(script), *arguments) if script else arguments),
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    cwd=script.parents[3] if script else None,
                )
                stdout, stderr = await process.communicate()
        except TimeoutError as error:
            raise AppError(
                "COMPONENT_CLI_TIMEOUT",
                "Component inspection timed out",
                arguments[0],
                504,
                True,
            ) from error
        if process.returncode:
            detail = stderr.decode(errors="replace") or stdout.decode(errors="replace")
            raise AppError("COMPONENT_CLI_FAILED", "Component inspection failed", detail[-1000:], 502, True)
        return stdout.decode(errors="replace")

    @staticmethod
    def _items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("node"), dict):
            return [payload["node"]]
        for key in ("nodes", "results", "components"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
        return [payload] if payload.get("id") else []

    def _source(self, value: str) -> Path:
        raw = value.strip().strip('"').strip("'")
        if not raw:
            raise AppError(
                "COMPONENT_SOURCE_MISSING",
                "Component source path is empty",
                raw,
                409,
                action="Choose an installed Design System or enter a .fig path in Settings.",
            )
        direct = Path(raw)
        if direct.is_file():
            return direct.resolve()

        design_dir = getattr(self.settings, "design_data_dir", None)
        if design_dir and Path(design_dir).is_dir():
            root = Path(design_dir)
            systems_dir = root / "design-systems"
            search_dirs = [systems_dir, root] if systems_dir.is_dir() else [root]
            for folder in search_dirs:
                if (folder / raw).is_file():
                    return (folder / raw).resolve()
                if (folder / f"{raw}.fig").is_file():
                    return (folder / f"{raw}.fig").resolve()

            norm_query = re.sub(r"[^a-z0-9]+", "", raw.lower())
            if norm_query:
                fig_files = list(root.rglob("*.fig"))
                # 1. Exact normalized match
                for fig in fig_files:
                    norm_name = re.sub(r"[^a-z0-9]+", "", fig.stem.lower())
                    if norm_query == norm_name:
                        return fig.resolve()
                # 2. Substring match
                for fig in fig_files:
                    norm_name = re.sub(r"[^a-z0-9]+", "", fig.stem.lower())
                    if norm_query in norm_name or norm_name in norm_query:
                        return fig.resolve()

        raise AppError(
            "COMPONENT_SOURCE_MISSING",
            "Component source was not found",
            str(direct),
            409,
            action="Choose an installed Design System or enter the full path to an existing .fig file in Settings.",
        )

    def _fingerprint(self, source: Path) -> str:
        stat = source.stat()
        cached = self._fingerprints.get(source)
        if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            return cached[2]
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        fingerprint = digest.hexdigest()
        self._fingerprints[source] = (stat.st_mtime_ns, stat.st_size, fingerprint)
        return fingerprint

    @staticmethod
    def _safe(value: str) -> str:
        return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "component"

    @staticmethod
    def _number(value: Any) -> float | None:
        return float(value) if isinstance(value, int | float) else None
