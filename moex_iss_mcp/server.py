from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from fastmcp import FastMCP
from moex_iss_sdk import IssClient
from moex_iss_sdk.utils import TTLCache, utc_now

from .config import McpConfig
from .mcp_instance import mcp
from .telemetry import McpMetrics, McpTracing, NullMetrics, NullTracing

# Импортируем инструменты для их регистрации через @mcp.tool
from .tools import (  # noqa: F401
    get_index_constituents_metrics,
    get_ohlcv_timeseries,
    get_security_snapshot,
)

logger = logging.getLogger(__name__)


class McpServer:
    """
    Обёртка над FastMCP для moex-iss-mcp.

    Управляет конфигурацией, зависимостями и маршрутами сервера.
    Инструменты регистрируются автоматически через декораторы @mcp.tool.
    """

    def __init__(self, config: McpConfig) -> None:
        self.config = config
        self.iss_client = IssClient(config.to_iss_settings())
        self._index_cache = TTLCache(max_size=16, ttl_seconds=60 * 60 * 24)  # 24h кэш для маппинга индексов
        self.metrics = McpMetrics() if config.enable_monitoring else NullMetrics()
        self.tracing = McpTracing(
            service_name=config.otel_service_name,
            otel_endpoint=config.otel_endpoint,
        )

        # Инициализируем зависимости для инструментов
        from .tools.get_security_snapshot import init_tool_dependencies as init_security_snapshot
        from .tools.get_ohlcv_timeseries import init_tool_dependencies as init_ohlcv
        from .tools.get_index_constituents_metrics import init_tool_dependencies as init_index

        init_security_snapshot(self.iss_client, self.metrics, self.tracing)
        init_ohlcv(self.iss_client, self.metrics, self.tracing)
        init_index(self.iss_client, self.metrics, self.tracing, self._index_cache)

        self._register_routes()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """
        Запустить FastMCP сервер с transport="streamable-http".
        """
        print("=" * 60)
        print("🌐 ЗАПУСК MCP СЕРВЕРА: moex-iss-mcp")
        print("=" * 60)
        print(f"🚀 MCP Server: http://{self.config.host}:{self.config.port}/mcp")
        print("=" * 60)

        logger.info("Starting moex-iss-mcp on %s:%s", self.config.host, self.config.port)
        mcp.run(
            transport="streamable-http",
            host=self.config.host,
            port=self.config.port,
            stateless_http=True,
        )

    @property
    def fastmcp(self) -> FastMCP:
        """Свойство для обратной совместимости с тестами."""
        return mcp

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _register_routes(self) -> None:
        # Сохраняем ссылки на self для использования в замыканиях
        config = self.config
        metrics = self.metrics

        # Сбрасываем ранее добавленные маршруты при повторных инициализациях
        mcp._additional_http_routes = [
            route for route in getattr(mcp, "_additional_http_routes", []) if getattr(route, "path", None) not in {"/health", "/metrics"}
        ]

        @mcp.custom_route("/health", methods=["GET"])
        async def health(_: Request) -> JSONResponse:  # pragma: no cover - simple response
            return JSONResponse({"status": "ok"})

        @mcp.custom_route("/metrics", methods=["GET"])
        async def metrics_route(_: Request) -> PlainTextResponse:  # pragma: no cover - simple response
            if not config.enable_monitoring:
                body = (
                    "# monitoring disabled\n"
                    f"# TYPE {mcp.name}_up gauge\n"
                    f"{mcp.name}_up 1.0\n"
                )
                return PlainTextResponse(body, media_type="text/plain")
            body, content_type = metrics.render()
            return PlainTextResponse(body, media_type=content_type)
