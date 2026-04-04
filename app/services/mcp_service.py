from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from core.config import Settings


logger = logging.getLogger(__name__)


@dataclass
class CachedTools:
    tools: list[Any]
    loaded_at: float


class McpToolRegistry:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._cache: CachedTools | None = None
        self._last_failure_at = 0.0

    async def get_tools(self, settings: Settings) -> list[Any]:
        if not settings.mcp_server_enabled:
            return []

        async with self._lock:
            if self._cache is not None:
                return list(self._cache.tools)

            now = time.monotonic()
            if now - self._last_failure_at < settings.mcp_retry_cooldown_seconds:
                return []

            try:
                tools = await self._load_tools(settings)
            except Exception as exc:
                self._last_failure_at = now
                logger.warning("MCP server unavailable, falling back to no-tools mode: %s", exc)
                return []

            self._cache = CachedTools(tools=list(tools), loaded_at=now)
            logger.info("Loaded %s MCP tool(s) from %s", len(tools), settings.mcp_server_url)
            return list(tools)

    async def _load_tools(self, settings: Settings) -> list[Any]:
        client = MultiServerMCPClient(
            {
                # 只使用一个 MCP 服务器，key 可以是任意值，这里用服务器名称方便调试
                # settings是整个进程共享的
                settings.mcp_server_name: {
                    "transport": "streamable_http",
                    "url": settings.mcp_server_url,
                }
            }
        )
        return list(await client.get_tools())

    async def clear_cache(self) -> None:
        async with self._lock:
            self._cache = None
            self._last_failure_at = 0.0


MCP_TOOL_REGISTRY = McpToolRegistry()


async def get_mcp_tools(settings: Settings) -> list[Any]:
    return await MCP_TOOL_REGISTRY.get_tools(settings)
