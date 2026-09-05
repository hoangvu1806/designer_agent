import base64
import json
import re
from pathlib import Path
from typing import Any

from mcp import ClientSession

from .components import ComponentSource
from .config import Settings
from .errors import AppError
from .jsx import COLOR_TOKENS, compile_jsx, compile_palette_jsx
from .models import (
    ComponentBindingSet,
    ComponentCandidate,
    OpenPencilArtifact,
    OpenPencilProfile,
    UiNode,
    UiSpecification,
)
from .openpencil_client import OpenPencilClient
from .openpencil_components import (
    keep_fallbacks,
    small_instances,
)


class OpenPencilGateway(OpenPencilClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.source = ComponentSource(settings)

    async def components(
        self,
        profile: OpenPencilProfile,
        requirements: list[dict[str, Any]] | None = None,
        knowledge: dict[str, Any] | None = None,
    ) -> list[ComponentCandidate]:
        return await self.source.discover(profile, requirements, knowledge)

    async def assemble(
        self,
        profile: OpenPencilProfile,
        specification: UiSpecification,
        bindings: ComponentBindingSet,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        component_ids = [
            item.component_id for item in bindings.bindings
            if item.status == "resolved" and item.component_id
        ]
        pack = await self.source.pack(profile.source_file, component_ids)
        async with self.session(profile.endpoint) as session:
            (
                document_id,
                local,
                palette_page_id,
                desktop_page_id,
                mobile_page_id,
            ) = await self._prepare_document(
                session, profile, pack, specification.screen_name, specification
            )

            local_bindings = bindings.model_copy(deep=True)
            for binding in local_bindings.bindings:
                if binding.component_id in local:
                    binding.component_id = local[binding.component_id]

            # ----------------------------------------------------
            # PAGE 1: Color Palette
            # ----------------------------------------------------
            await self._call(session, "switch_page", {"page": palette_page_id, "document_id": document_id})
            palette_jsx = compile_palette_jsx(specification.screen_name)
            await self._call(
                session,
                "render",
                {
                    "jsx": palette_jsx,
                    "x": 0,
                    "y": 0,
                    "document_id": document_id,
                    "page_id": palette_page_id,
                },
            )
            try:
                col = await self._call(session, "create_collection", {"name": "Design Tokens", "document_id": document_id})
                col_id = col["id"]
                for token_name, hex_val, _, _ in COLOR_TOKENS:
                    await self._call(session, "create_variable", {
                        "name": token_name,
                        "type": "COLOR",
                        "collection_id": col_id,
                        "value": hex_val,
                        "document_id": document_id,
                    })
            except Exception:
                pass

            # ----------------------------------------------------
            # PAGE 2: Desktop Web (Primary Viewport: 1440px)
            # ----------------------------------------------------
            await self._call(session, "switch_page", {"page": desktop_page_id, "document_id": document_id})
            desktop_jsx = compile_jsx(specification, mode="desktop")
            root_desktop = await self._call(
                session,
                "render",
                {
                    "jsx": desktop_jsx,
                    "x": 0,
                    "y": 0,
                    "document_id": document_id,
                    "page_id": desktop_page_id,
                },
            )
            desktop_instances = await self._insert_instances(session, document_id, desktop_page_id, local_bindings)
            fallback_count = await keep_fallbacks(self, session, document_id, desktop_page_id, local_bindings)
            desktop_photos = await self._apply_stock_photos(session, document_id, desktop_page_id, specification)

            # ----------------------------------------------------
            # PAGE 3: Mobile Mockup (Mobile Viewport: 390px)
            # ----------------------------------------------------
            await self._call(session, "switch_page", {"page": mobile_page_id, "document_id": document_id})
            mobile_jsx = compile_jsx(specification, mode="mobile")
            root_mobile = await self._call(
                session,
                "render",
                {
                    "jsx": mobile_jsx,
                    "x": 0,
                    "y": 0,
                    "document_id": document_id,
                    "page_id": mobile_page_id,
                },
            )
            mobile_instances = await self._insert_instances(session, document_id, mobile_page_id, local_bindings)
            await keep_fallbacks(self, session, document_id, mobile_page_id, local_bindings)
            mobile_photos = await self._apply_stock_photos(session, document_id, mobile_page_id, specification)

            # Switch back to Desktop Web as the default active view
            await self._call(session, "switch_page", {"page": desktop_page_id, "document_id": document_id})

            bounds = await self._call(session, "page_bounds", {
                "document_id": document_id, "page_id": desktop_page_id,
            })
            placeholders = await self._call(
                session,
                "find_nodes",
                {
                    "name": "slot::",
                    "document_id": document_id,
                    "page_id": desktop_page_id,
                },
            )
            overlaps = await self._call(
                session,
                "analyze_overlaps",
                {
                    "page_id": desktop_page_id,
                    "severity": "minor",
                    "limit": 100,
                    "document_id": document_id,
                },
            )
            root_detail = await self._call(
                session,
                "get_node",
                {
                    "id": root_desktop["id"],
                    "depth": 6,
                    "document_id": document_id,
                    "page_id": desktop_page_id,
                },
            )
            # Export preview screenshots via MCP
            desktop_preview = await self._capture_preview(session, document_id, desktop_page_id, root_desktop["id"], scale=0.4)
            mobile_preview = await self._capture_preview(session, document_id, mobile_page_id, root_mobile["id"], scale=0.5)
            # Switch back to desktop view as active
            try:
                await self._call(session, "switch_page", {"page": desktop_page_id, "document_id": document_id})
            except Exception:
                try:
                    await self._call(session, "switch_page", {"page": desktop_page_id})
                except Exception:
                    pass

            preview_urls: dict[str, str] = {}
            if run_id:
                try:
                    previews_dir = Path(__file__).resolve().parent.parent / "data" / "previews"
                    previews_dir.mkdir(parents=True, exist_ok=True)
                    if desktop_preview:
                        raw_bytes, ext = desktop_preview
                        (previews_dir / f"{run_id}_desktop.{ext}").write_bytes(raw_bytes)
                        preview_urls["desktop"] = f"/api/v1/runs/{run_id}/preview?mode=desktop"
                    if mobile_preview:
                        raw_bytes, ext = mobile_preview
                        (previews_dir / f"{run_id}_mobile.{ext}").write_bytes(raw_bytes)
                        preview_urls["mobile"] = f"/api/v1/runs/{run_id}/preview?mode=mobile"
                except Exception:
                    pass

            await self._call(session, "save_file", {
                "path": profile.output_file, "document_id": document_id,
            })

        artifact = OpenPencilArtifact(
            document_id=document_id,
            page_id=desktop_page_id,
            page_name="Desktop Web",
            output_file=profile.output_file,
            root_node_id=str(root_desktop["id"]),
            created_nodes=1 + desktop_instances + mobile_instances,
        )
        return {
            **artifact.model_dump(mode="json"),
            "telemetry": {
                "pages": ["Color Palette", "Desktop Web", "Mobile Mockup"],
                "bounds": bounds,
                "instances": desktop_instances + mobile_instances,
                "fallbacks": fallback_count,
                "stock_photos": desktop_photos + mobile_photos,
                "placeholders": int(placeholders.get("count", 0)),
                "overlaps": overlaps,
                "root_node_id": artifact.root_node_id,
                "small_touch_targets": small_instances(root_detail),
                "previews": preview_urls,
            },
        }

    async def _capture_preview(
        self,
        session: ClientSession,
        document_id: str,
        page_id: str,
        root_node_id: str | None = None,
        scale: float = 0.4,
    ) -> tuple[bytes, str] | None:
        """Capture page or root node preview, returning (bytes, extension) or None."""
        try:
            await self._call(session, "switch_page", {"page": page_id, "document_id": document_id})
        except Exception:
            try:
                await self._call(session, "switch_page", {"page": page_id})
            except Exception:
                pass

        # 1. Try raster image via export_image
        try:
            args: dict[str, Any] = {"format": "JPG", "scale": scale}
            if root_node_id:
                args["ids"] = [root_node_id]
            res = await session.call_tool("export_image", arguments=args)
            for item in res.content:
                if hasattr(item, "data") and item.data:
                    return base64.b64decode(item.data), "jpg"
        except Exception:
            pass

        # 2. Try without ids
        try:
            res = await session.call_tool("export_image", arguments={"format": "JPG", "scale": scale})
            for item in res.content:
                if hasattr(item, "data") and item.data:
                    return base64.b64decode(item.data), "jpg"
        except Exception:
            pass

        # 3. Fallback to vector SVG via export_svg (100% reliable)
        try:
            svg_args: dict[str, Any] = {"document_id": document_id, "page_id": page_id}
            if root_node_id:
                svg_args["ids"] = [root_node_id]
            svg_res = await self._call(session, "export_svg", svg_args)
            if svg_res.get("svg"):
                return svg_res["svg"].encode("utf-8"), "svg"
        except Exception:
            pass

        try:
            svg_res = await self._call(session, "export_svg", {})
            if svg_res.get("svg"):
                return svg_res["svg"].encode("utf-8"), "svg"
        except Exception:
            pass

        return None

    async def _prepare_document(
        self,
        session: ClientSession,
        profile: OpenPencilProfile,
        pack: list[tuple[str, str]],
        screen_name: str = "Design System",
        specification: UiSpecification | None = None,
    ) -> tuple[str, dict[str, str], str, str, str]:
        candidates: list[str] = []
        if screen_name and screen_name.strip().lower() not in ("new screen", "untitled", "screen", "giao diện"):
            candidates.append(screen_name.strip())
        if specification:
            if specification.screen_name and specification.screen_name.strip().lower() not in ("new screen", "untitled", "screen", "giao diện"):
                candidates.append(specification.screen_name.strip())
            if specification.root and specification.root.name and specification.root.name.strip().lower() not in ("page", "root", "frame", "screen", "untitled", "container"):
                candidates.append(specification.root.name.strip())
            if specification.summary:
                first_part = specification.summary.split(" - ")[0].split(":")[0].strip()
                if first_part and first_part.lower() not in ("new screen", "untitled", "screen", "giao diện"):
                    candidates.append(first_part)

        resolved_name = candidates[0] if candidates else "Design System"
        clean_name = re.sub(r"[\W_]+", " ", resolved_name).strip() or "Design System"
        if len(clean_name) > 60:
            clean_name = clean_name[:60].strip()

        doc_filename = f"{clean_name}.fig"
        if not profile.output_file:
            raise AppError(
                "OPENPENCIL_OUTPUT_MISSING",
                "OpenPencil output path is missing",
                "The run must allocate its output file before assembly.",
                409,
            )

        # Every run starts from a blank document and owns its output path.
        try:
            result = await self._call(
                session, "new_document", {"path": profile.output_file}
            )
        except Exception:
            result = await self._call(session, "new_document", {"path": doc_filename})

        document_id, _ = self._target(result)
        if not document_id:
            raise AppError("OPENPENCIL_TARGET_MISSING", "Target document was not created", str(result), 502)

        listed = await self._call(session, "list_pages", {"document_id": document_id})
        existing_pages = listed.get("pages", [])
        page_names = {p["name"]: str(p["id"]) for p in existing_pages}

        if existing_pages:
            palette_page_id = str(existing_pages[0]["id"])
            await self._call(session, "rename_node", {
                "id": palette_page_id,
                "name": "Color Palette",
                "document_id": document_id,
            })
        else:
            p_pal = await self._call(session, "create_page", {"name": "Color Palette", "document_id": document_id})
            palette_page_id = str(p_pal["id"])

        if "Desktop Web" in page_names:
            desktop_page_id = page_names["Desktop Web"]
        else:
            p_web = await self._call(session, "create_page", {"name": "Desktop Web", "document_id": document_id})
            desktop_page_id = str(p_web["id"])

        if "Mobile Mockup" in page_names:
            mobile_page_id = page_names["Mobile Mockup"]
        else:
            p_mobile = await self._call(session, "create_page", {"name": "Mobile Mockup", "document_id": document_id})
            mobile_page_id = str(p_mobile["id"])

        local: dict[str, str] = {}
        if pack:
            if "Components" in page_names:
                comp_page_id = page_names["Components"]
            else:
                p_comp = await self._call(session, "create_page", {"name": "Components", "document_id": document_id})
                comp_page_id = str(p_comp["id"])
            await self._call(session, "switch_page", {"page": comp_page_id, "document_id": document_id})
            for source_id, source_jsx in pack:
                jsx = source_jsx
                for old_id, new_id in local.items():
                    jsx = jsx.replace(old_id, new_id)
                rendered = await self._call(session, "render", {
                    "jsx": jsx, "document_id": document_id, "page_id": comp_page_id,
                })
                local[source_id] = str(rendered["id"])

        await self._call(session, "save_file", {"path": profile.output_file, "document_id": document_id})
        return document_id, local, palette_page_id, desktop_page_id, mobile_page_id

    async def _insert_instances(
        self,
        session: ClientSession,
        document_id: str,
        page_id: str,
        bindings: ComponentBindingSet,
    ) -> int:
        created = 0
        for binding in bindings.bindings:
            if binding.status != "resolved" or not binding.component_id:
                continue
            matches = await self._call(
                session,
                "find_nodes",
                {
                    "name": f"slot::{binding.node_id}",
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            nodes = matches.get("nodes", [])
            if not nodes:
                continue
            placeholder = nodes[0]
            ancestors = await self._call(
                session,
                "node_ancestors",
                {
                    "id": placeholder["id"],
                    "depth": 1,
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            instance = await self._call(
                session,
                "create_instance",
                {
                    "component_id": binding.component_id,
                    "x": placeholder.get("x", 0),
                    "y": placeholder.get("y", 0),
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            parents = ancestors.get("ancestors", [])
            if not instance.get("id") or not parents:
                continue
            await self._call(
                session,
                "reparent_node",
                {
                    "id": instance["id"],
                    "parent_id": parents[0]["id"],
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            await self._call(
                session,
                "update_node",
                {
                    "id": instance["id"],
                    "x": 0,
                    "y": 0,
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            await self._bind_text(session, document_id, page_id, str(instance["id"]), binding.text_values)
            await self._call(
                session,
                "delete_node",
                {
                    "id": placeholder["id"],
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            created += 1
        return created

    async def _bind_text(
        self,
        session: ClientSession,
        document_id: str,
        page_id: str,
        instance_id: str,
        values: dict[str, str],
    ) -> None:
        try:
            tree = await self._call(
                session,
                "node_tree",
                {
                    "id": instance_id,
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
        except Exception:
            return

        # 1. Delete any spacer / guide lines (like " Min Width") inside the instance
        for child in tree.get("children", []):
            if any(g in child.get("name", "").lower() for g in ("min width", "spacer", "guide")):
                try:
                    await self._call(
                        session,
                        "delete_node",
                        {
                            "id": child["id"],
                            "document_id": document_id,
                            "page_id": page_id,
                        },
                    )
                except Exception:
                    pass

        # 2. Re-fetch clean tree
        try:
            tree = await self._call(
                session,
                "node_tree",
                {
                    "id": instance_id,
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
        except Exception:
            return

        # 3. Tint primary CTA buttons with patriotic red #DC2626 instead of cyan
        text_joined = " ".join(values.values()).lower()
        is_primary = any(k in text_joined for k in ("mua", "đặt", "nhận", "thêm vào giỏ", "cart", "buy", "order", "ngay"))
        if is_primary:
            try:
                await self._call(
                    session,
                    "set_fill",
                    {
                        "id": instance_id,
                        "color": "#DC2626",
                        "document_id": document_id,
                        "page_id": page_id,
                    },
                )
            except Exception:
                pass

        text_nodes: list[tuple[str, str, str]] = []

        def collect(node: Any, prefix: str = "") -> None:
            if not isinstance(node, dict):
                return
            name = str(node.get("name", node.get("type", "node")))
            path = f"{prefix}/{name}".strip("/")
            if node.get("type") == "TEXT" and node.get("id"):
                text_nodes.append((str(node["id"]), path, name))
            for child in node.get("children", []):
                collect(child, path)

        collect(tree)
        unused = list(text_nodes)

        for slot, content in values.items():
            normalized = self._normalized(slot.removeprefix("text:"))
            match = next((item for item in unused if self._normalized(item[1]) == normalized), None)
            match = match or next((item for item in unused if self._normalized(item[2]) == normalized), None)
            if match is None and unused:
                # Direct fallback: take the first available text slot
                match = unused[0]
            if match is None:
                continue
            unused.remove(match)
            try:
                await self._call(
                    session,
                    "set_text",
                    {
                        "id": match[0],
                        "text": content,
                        "document_id": document_id,
                        "page_id": page_id,
                    },
                )
            except Exception:
                pass

    @staticmethod
    def _normalized(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.lower()))

    async def _apply_stock_photos(
        self,
        session: ClientSession,
        document_id: str,
        page_id: str,
        specification: UiSpecification,
    ) -> int:
        media_nodes: list[UiNode] = []

        def collect(node: UiNode) -> None:
            if node.kind == "media":
                media_nodes.append(node)
            for child in node.children:
                collect(child)

        collect(specification.root)
        if not media_nodes:
            return 0

        screen_topic = specification.screen_name.lower().replace("landing page", "").strip()
        requests: list[dict[str, Any]] = []

        for node in media_nodes:
            matches = await self._call(
                session,
                "find_nodes",
                {
                    "name": f"photo::{node.id}",
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            nodes = matches.get("nodes", [])
            if not nodes:
                continue

            query_raw = str(
                node.content.get("query")
                or node.content.get("alt")
                or node.content.get("text")
                or node.name
            ).strip()

            q_lower = query_raw.lower()
            if any(k in q_lower for k in ("ban công", "balcony")):
                final_query = "vietnam old town balcony decorated with red flags"
            elif any(k in q_lower for k in ("để bàn", "desk", "văn phòng", "office")):
                final_query = "small vietnam flag on wooden executive desk office"
            elif any(k in q_lower for k in ("sự kiện", "diễu hành", "event", "parade")):
                final_query = "vietnam national parade celebration crowd red flags"
            elif any(k in q_lower for k in ("chất liệu", "vải", "may", "fabric", "material")):
                final_query = "premium red silk fabric textile macro texture"
            elif any(k in q_lower for k in ("avatar", "đại diện", "khách hàng", "reviewer", "person")):
                final_query = "vietnamese young adult friendly smiling face portrait"
            elif any(k in q_lower for k in ("hero", "chính", "banner", "cờ", "flag")):
                final_query = "vietnam national flag waving in blue sky patriotic celebration"
            else:
                clean_query = re.sub(r"[\W_]+", " ", query_raw).strip()
                final_query = f"{screen_topic} {clean_query}".strip()

            if not final_query:
                final_query = "vietnam national flag celebration"

            requests.append({
                "id": str(nodes[0]["id"]),
                "query": final_query,
                "orientation": "landscape",
            })

        if not requests:
            return 0

        try:
            result = await self._call(
                session,
                "stock_photo",
                {
                    "requests": json.dumps(requests),
                    "document_id": document_id,
                    "page_id": page_id,
                },
            )
            return int(result.get("applied", 0))
        except Exception:
            return 0
