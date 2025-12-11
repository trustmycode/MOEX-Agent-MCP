from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from fastmcp import FastMCP
from moex_iss_sdk import IssClient

from .config import RiskMcpConfig
from .mcp_instance import mcp
from .telemetry import McpMetrics, McpTracing, NullMetrics, NullTracing

# Импортируем инструменты для их регистрации через @mcp.tool
from .tools import (  # noqa: F401
    compute_correlation_matrix,
    compute_portfolio_risk_basic,
    issuer_peers_compare,
    suggest_rebalance,
)

logger = logging.getLogger(__name__)


class RiskMcpServer:
    """
    Обёртка над FastMCP для risk-analytics-mcp.

    Управляет конфигурацией, зависимостями и маршрутами сервера.
    Инструменты регистрируются автоматически через декораторы @mcp.tool.
    """

    def __init__(self, config: RiskMcpConfig) -> None:
        self.config = config
        self.iss_client: IssClient = config.create_iss_client()
        from .providers import MoexIssFundamentalsProvider

        self.metrics = McpMetrics() if config.enable_monitoring else NullMetrics()
        self.tracing = McpTracing(
            service_name=config.otel_service_name,
            otel_endpoint=config.otel_endpoint,
        )
        self.fundamentals_provider = MoexIssFundamentalsProvider(self.iss_client)

        # Инициализируем зависимости для инструментов
        from .tools.correlation_matrix import init_tool_dependencies as init_correlation
        from .tools.portfolio_risk import init_tool_dependencies as init_portfolio
        from .tools.issuer_peers_compare import init_tool_dependencies as init_peers
        from .tools.suggest_rebalance import init_tool_dependencies as init_rebalance

        init_correlation(
            self.iss_client,
            self.metrics,
            self.tracing,
            config.max_correlation_tickers,
            config.max_lookback_days,
        )
        init_portfolio(
            self.iss_client,
            self.metrics,
            self.tracing,
            config.max_portfolio_tickers,
            config.max_lookback_days,
        )
        init_peers(
            self.iss_client,
            self.fundamentals_provider,
            self.metrics,
            self.tracing,
            config.max_peers,
            config.default_index_ticker,
        )
        init_rebalance(
            self.metrics,
            self.tracing,
        )

        self._register_routes()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """
        Запустить FastMCP сервер с transport="streamable-http".
        """
        print("=" * 60)
        print("🌐 ЗАПУСК MCP СЕРВЕРА: risk-analytics-mcp")
        print("=" * 60)
        print(f"🚀 MCP Server: http://{self.config.host}:{self.config.port}/mcp")
        print("=" * 60)

        logger.info("Starting risk-analytics-mcp on %s:%s", self.config.host, self.config.port)
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

        # Очищаем предыдущие регистрации, если сервер создаётся повторно в тестах
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
