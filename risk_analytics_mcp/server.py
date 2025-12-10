from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import Any, Dict, List

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from moex_iss_sdk import IssClient

from .config import RiskMcpConfig
from .telemetry import McpMetrics, McpTracing, NullMetrics, NullTracing

logger = logging.getLogger(__name__)


class RiskMcpServer:
    """
    Обёртка над FastMCP для risk-analytics-mcp.

    На этом этапе реализованы только базовые endpoint'ы и регистрация
    заглушек инструментов; бизнес-логика будет добавлена в следующих задачах.
    """

    def __init__(self, config: RiskMcpConfig) -> None:
        self.config = config
        self.iss_client: IssClient = config.create_iss_client()
        self.metrics = McpMetrics() if config.enable_monitoring else NullMetrics()
        self.tracing = McpTracing(
            service_name=config.otel_service_name,
            otel_endpoint=config.otel_endpoint,
        )
        self.fastmcp = FastMCP(name="risk-analytics-mcp", instructions="Risk analytics MCP for MOEX portfolios.")
        self._register_routes()
        self._register_stub_tools()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(self) -> None:
        """
        Запустить FastMCP сервер с transport="streamable-http".
        """
        logger.info("Starting risk-analytics-mcp on %s:%s", self.config.host, self.config.port)
        self.fastmcp.run(
            transport="streamable-http",
            host=self.config.host,
            port=self.config.port,
            show_banner=False,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _register_routes(self) -> None:
        @self.fastmcp.custom_route("/health", methods=["GET"])
        async def health(_: Request) -> JSONResponse:  # pragma: no cover - simple response
            return JSONResponse({"status": "ok"})

        @self.fastmcp.custom_route("/metrics", methods=["GET"])
        async def metrics(_: Request) -> PlainTextResponse:  # pragma: no cover - simple response
            if not self.config.enable_monitoring:
                return PlainTextResponse("# monitoring disabled\n", media_type="text/plain")
            body, content_type = self.metrics.render()
            return PlainTextResponse(body, media_type=content_type)

    def _register_stub_tools(self) -> None:
        """
        Зарегистрировать инструменты MCP.
        """

        def compute_portfolio_risk_basic(
            tickers: List[str] | None = None, lookback_days: int | None = None
        ) -> Dict[str, Any]:
            tool_name = "compute_portfolio_risk_basic"
            start_ts = time.perf_counter()
            self.metrics.inc_tool_call(tool_name)
            with self.tracing.start_span(tool_name):
                try:
                    normalized_tickers = self._normalize_tickers(tickers)
                    self._enforce_limits(normalized_tickers, lookback_days)
                    return self._stub_payload(
                        tool_name,
                        normalized_tickers,
                        lookback_days,
                        message="Portfolio risk calculations are not implemented yet.",
                    )
                except Exception as exc:
                    self.metrics.inc_tool_error(tool_name, type(exc).__name__)
                    if isinstance(exc, ValueError):
                        raise
                    logger.exception("Error in compute_portfolio_risk_basic for tickers=%s", tickers)
                    return self._not_implemented_payload(tool_name, normalized_tickers, lookback_days, error=str(exc))
                finally:
                    self.metrics.observe_latency(tool_name, time.perf_counter() - start_ts)

        def compute_correlation_matrix(
            tickers: List[str] | None = None, lookback_days: int | None = None
        ) -> Dict[str, Any]:
            tool_name = "compute_correlation_matrix"
            start_ts = time.perf_counter()
            self.metrics.inc_tool_call(tool_name)
            with self.tracing.start_span(tool_name):
                try:
                    normalized_tickers = self._normalize_tickers(tickers)
                    self._enforce_limits(normalized_tickers, lookback_days)
                    return self._stub_payload(
                        tool_name,
                        normalized_tickers,
                        lookback_days,
                        message="Correlation matrix calculation is not implemented yet.",
                    )
                except Exception as exc:
                    self.metrics.inc_tool_error(tool_name, type(exc).__name__)
                    if isinstance(exc, ValueError):
                        raise
                    logger.exception("Error in compute_correlation_matrix for tickers=%s", tickers)
                    return self._not_implemented_payload(tool_name, normalized_tickers, lookback_days, error=str(exc))
                finally:
                    self.metrics.observe_latency(tool_name, time.perf_counter() - start_ts)

        # Регистрируем функции в FastMCP
        self.fastmcp.tool(compute_portfolio_risk_basic)
        self.fastmcp.tool(compute_correlation_matrix)

        # Экспонируем зарегистрированные функции для тестов, ожидающих _tools
        self.fastmcp._tools = {
            "compute_portfolio_risk_basic": SimpleNamespace(func=compute_portfolio_risk_basic),
            "compute_correlation_matrix": SimpleNamespace(func=compute_correlation_matrix),
        }

    def _enforce_limits(self, tickers: List[str], lookback_days: int | None) -> None:
        """
        Проверить лимиты по количеству тикеров и глубине истории.
        """
        if tickers and len(tickers) > self.config.max_portfolio_tickers:
            raise ValueError(f"Too many tickers: {len(tickers)} > {self.config.max_portfolio_tickers}")
        if lookback_days is not None:
            if lookback_days <= 0:
                raise ValueError("lookback_days must be positive")
            if lookback_days > self.config.max_lookback_days:
                raise ValueError(f"lookback_days exceeds limit {self.config.max_lookback_days}")

    def _normalize_tickers(self, tickers: List[str] | None) -> List[str]:
        if not tickers:
            return []
        return [t.strip().upper() for t in tickers if t and t.strip()]

    def _stub_payload(
        self,
        tool_name: str,
        tickers: List[str],
        lookback_days: int | None,
        *,
        message: str,
    ) -> Dict[str, Any]:
        """
        Общий ответ-заглушка для инструментов до появления бизнес-логики.
        """
        return {
            "metadata": {
                "tool": tool_name,
                "tickers": tickers,
                "lookback_days": lookback_days,
                "iss_base_url": self.iss_client.settings.base_url,
                "limits": {
                    "max_portfolio_tickers": self.config.max_portfolio_tickers,
                    "max_lookback_days": self.config.max_lookback_days,
                },
            },
            "data": {
                "status": "stub",
                "message": message,
            },
            "error": None,
        }

    def _not_implemented_payload(
        self,
        tool_name: str,
        tickers: List[str],
        lookback_days: int | None,
        *,
        error: str,
    ) -> Dict[str, Any]:
        return {
            "metadata": {
                "tool": tool_name,
                "tickers": tickers,
                "lookback_days": lookback_days,
                "iss_base_url": self.iss_client.settings.base_url,
            },
            "data": None,
            "error": {"error_type": "NOT_IMPLEMENTED", "message": error},
        }
