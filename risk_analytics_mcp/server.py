from __future__ import annotations

import logging
import time
from types import SimpleNamespace
from typing import Any, Dict, List

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from moex_iss_mcp.error_mapper import ErrorMapper
from moex_iss_sdk import IssClient

from .config import RiskMcpConfig
from .telemetry import McpMetrics, McpTracing, NullMetrics, NullTracing
from .tools import compute_correlation_matrix_tool, compute_portfolio_risk_basic_tool

logger = logging.getLogger(__name__)


class RiskMcpServer:
    """
    Обёртка над FastMCP для risk-analytics-mcp.

    Реализует compute_portfolio_risk_basic и compute_correlation_matrix.
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
        self._register_tools()

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

    def _register_tools(self) -> None:
        """
        Зарегистрировать инструменты MCP.
        """

        def compute_portfolio_risk_basic(
            positions: List[Dict[str, Any]] | None = None,
            from_date: str | None = None,
            to_date: str | None = None,
            rebalance: str = "buy_and_hold",
            aggregates: Dict[str, Any] | None = None,
            stress_scenarios: List[str] | None = None,
            var_config: Dict[str, Any] | None = None,
        ) -> Dict[str, Any]:
            tool_name = "compute_portfolio_risk_basic"
            start_ts = time.perf_counter()
            self.metrics.inc_tool_call(tool_name)
            with self.tracing.start_span(tool_name):
                try:
                    payload = {
                        "positions": positions or [],
                        "from_date": from_date,
                        "to_date": to_date,
                        "rebalance": rebalance,
                    }
                    if aggregates is not None:
                        payload["aggregates"] = aggregates
                    if stress_scenarios is not None:
                        payload["stress_scenarios"] = stress_scenarios
                    if var_config is not None:
                        payload["var_config"] = var_config
                    output = compute_portfolio_risk_basic_tool(
                        payload,
                        self.iss_client,
                        max_tickers=self.config.max_portfolio_tickers,
                        max_lookback_days=self.config.max_lookback_days,
                    )
                    if output.get("error"):
                        self.metrics.inc_tool_error(tool_name, output["error"].get("error_type", "UNKNOWN"))
                    return output
                except Exception as exc:
                    error_type = ErrorMapper.get_error_type_for_exception(exc)
                    self.metrics.inc_tool_error(tool_name, error_type)
                    logger.exception("Error in compute_portfolio_risk_basic for payload=%s", positions)
                    return {
                        "metadata": {"tool": tool_name},
                        "data": None,
                        "error": {
                            "error_type": error_type,
                            "message": str(exc) or "Unexpected error",
                            "details": {"exception_type": type(exc).__name__},
                        },
                    }
                finally:
                    self.metrics.observe_latency(tool_name, time.perf_counter() - start_ts)

        def compute_correlation_matrix(
            tickers: List[str] | None = None,
            from_date: str | None = None,
            to_date: str | None = None,
        ) -> Dict[str, Any]:
            tool_name = "compute_correlation_matrix"
            start_ts = time.perf_counter()
            self.metrics.inc_tool_call(tool_name)
            with self.tracing.start_span(tool_name):
                try:
                    payload = {
                        "tickers": tickers or [],
                        "from_date": from_date,
                        "to_date": to_date,
                    }
                    output = compute_correlation_matrix_tool(
                        payload,
                        self.iss_client,
                        max_tickers=self.config.max_correlation_tickers,
                        max_lookback_days=self.config.max_lookback_days,
                    )
                    if output.get("error"):
                        self.metrics.inc_tool_error(tool_name, output["error"].get("error_type", "UNKNOWN"))
                    return output
                except Exception as exc:
                    error_type = ErrorMapper.get_error_type_for_exception(exc)
                    self.metrics.inc_tool_error(tool_name, error_type)
                    logger.exception("Error in compute_correlation_matrix for tickers=%s", tickers)
                    return {
                        "metadata": {
                            "tool": tool_name,
                            "tickers": tickers or [],
                            "from_date": from_date,
                            "to_date": to_date,
                            "iss_base_url": self.iss_client.settings.base_url,
                        },
                        "tickers": tickers or [],
                        "matrix": [],
                        "error": {
                            "error_type": error_type,
                            "message": str(exc) or "Unexpected error",
                            "details": {"exception_type": type(exc).__name__},
                        },
                    }
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
