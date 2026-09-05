import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import BaseModel, Field

from .config import Settings
from .errors import AppError


class OpenPencilCapability(BaseModel):
    reachable: bool
    endpoint: str
    tools: list[str] = Field(default_factory=list)
    file_operations: bool = False
    message: str


class OpenPencilClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @asynccontextmanager
    async def session(self, endpoint: str) -> AsyncIterator[ClientSession]:
        url = endpoint.strip()
        if not url:
            raise AppError(
                "MCP_PROFILE_REQUIRED",
                "OpenPencil endpoint is required",
                "Configure the MCP endpoint in frontend Settings.",
                409,
            )
        headers = {}
        if self.settings.openpencil_mcp_auth_token:
            headers["Authorization"] = f"Bearer {self.settings.openpencil_mcp_auth_token}"
        try:
            async with streamablehttp_client(url, headers=headers) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        except AppError:
            raise
        except Exception as error:
            nested = self._find_app_error(error)
            if nested:
                raise nested from error
            raise AppError(
                "OPENPENCIL_MCP_UNAVAILABLE",
                "OpenPencil MCP is unavailable",
                self._exception_detail(error),
                502,
                retryable=True,
                action="Start OpenPencil and its HTTP MCP runtime, then retry.",
            ) from error

    async def probe(self, endpoint: str) -> OpenPencilCapability:
        url = endpoint.strip()
        health = await self._health_status(url)
        if health == "no_app":
            return OpenPencilCapability(
                reachable=False,
                endpoint=url,
                message=(
                    "MCP server is running, but the OpenPencil app bridge is disconnected. "
                    "Refresh the OpenPencil browser tab."
                ),
            )
        try:
            async with asyncio.timeout(self.settings.mcp_timeout_seconds):
                async with self.session(url) as session:
                    result = await session.list_tools()
                    tools = sorted(tool.name for tool in result.tools)
        except (AppError, TimeoutError) as error:
            return OpenPencilCapability(
                reachable=False,
                endpoint=url,
                message=getattr(error, "detail", "OpenPencil MCP timed out."),
            )
        required = {
            "open_file",
            "new_document",
            "save_file",
            "create_page",
            "switch_page",
            "render",
            "list_pages",
            "get_node",
            "create_instance",
            "find_nodes",
            "node_ancestors",
            "reparent_node",
            "delete_node",
            "node_tree",
            "set_text",
            "page_bounds",
            "update_node",
            "analyze_overlaps",
        }
        available = required.issubset(tools)
        return OpenPencilCapability(
            reachable=True,
            endpoint=url,
            tools=tools,
            file_operations=available,
            message=(
                f"OpenPencil MCP connected ({len(tools)} tools available)."
                if available
                else "Connected, but required file tools are missing."
            ),
        )

    async def _require_app(self, endpoint: str) -> None:
        if await self._health_status(endpoint) != "no_app":
            return
        raise AppError(
            "OPENPENCIL_APP_DISCONNECTED",
            "OpenPencil app is disconnected",
            "The MCP server is running, but no browser editor is connected.",
            409,
            retryable=True,
            action="Refresh the OpenPencil browser tab, then retry.",
        )

    async def _health_status(self, endpoint: str) -> str | None:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        netloc = parsed.netloc
        if parsed.hostname == "localhost":
            netloc = f"127.0.0.1:{parsed.port}" if parsed.port else "127.0.0.1"
        health_url = urlunsplit((parsed.scheme, netloc, "/health", "", ""))

        def fetch() -> str | None:
            headers = {}
            if self.settings.openpencil_mcp_auth_token:
                headers["Authorization"] = (
                    f"Bearer {self.settings.openpencil_mcp_auth_token}"
                )
            with urlopen(Request(health_url, headers=headers), timeout=3) as response:
                value = json.loads(response.read().decode("utf-8"))
            return str(value.get("status")) if isinstance(value, dict) else None

        try:
            return await asyncio.wait_for(asyncio.to_thread(fetch), timeout=4)
        except Exception:
            return None

    async def _call(
        self,
        session: ClientSession,
        tool: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            async with asyncio.timeout(self.settings.mcp_timeout_seconds):
                response = await session.call_tool(tool, arguments=arguments)
        except TimeoutError as error:
            raise AppError(
                "OPENPENCIL_MCP_TIMEOUT",
                "OpenPencil MCP timed out",
                tool,
                504,
                True,
            ) from error
        text = "\n".join(item.text for item in response.content if getattr(item, "text", None))
        if getattr(response, "isError", False):
            if tool == "open_file":
                raise AppError(
                    "OPENPENCIL_SOURCE_UNAVAILABLE",
                    "OpenPencil could not open the component source",
                    text,
                    409,
                    True,
                    action=(
                        "Choose an existing component source in frontend Settings. "
                        "If OpenPencil was already running, restart it to load runtime changes."
                    ),
                )
            raise AppError(
                "OPENPENCIL_TOOL_FAILED",
                f"OpenPencil tool {tool} failed",
                text,
                502,
                True,
            )
        try:
            value = json.loads(text) if text else {}
        except json.JSONDecodeError as error:
            raise AppError(
                "OPENPENCIL_INVALID_RESULT",
                "OpenPencil returned invalid JSON",
                text,
                502,
            ) from error
        if isinstance(value, dict) and "result" in value and isinstance(value["result"], dict):
            value = value["result"]
        if not isinstance(value, dict) or value.get("error"):
            raise AppError(
                "OPENPENCIL_TOOL_FAILED",
                f"OpenPencil tool {tool} failed",
                str(value),
                502,
                True,
            )
        return value

    @staticmethod
    def _target(value: Any) -> tuple[str, str]:
        if isinstance(value, dict):
            target = value.get("target", value)
            document_id = target.get("document_id") or target.get("documentId") or ""
            page_id = target.get("page_id") or target.get("pageId") or ""
            if document_id:
                return str(document_id), str(page_id)
            for nested in value.values():
                found = OpenPencilClient._target(nested)
                if found[0]:
                    return found
        if isinstance(value, list):
            for nested in value:
                found = OpenPencilClient._target(nested)
                if found[0]:
                    return found
        return "", ""

    @staticmethod
    def _exception_detail(error: BaseException) -> str:
        nested = getattr(error, "exceptions", None)
        if nested:
            details = [OpenPencilClient._exception_detail(item) for item in nested]
            return "; ".join(dict.fromkeys(detail for detail in details if detail))
        return str(error) or error.__class__.__name__

    @staticmethod
    def _find_app_error(error: BaseException) -> AppError | None:
        if isinstance(error, AppError):
            return error
        for nested in getattr(error, "exceptions", ()):
            found = OpenPencilClient._find_app_error(nested)
            if found:
                return found
        return None
