from __future__ import annotations

from typing import Optional

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
except ImportError as exc:  # pragma: no cover - defensive guardrail
    raise RuntimeError(
        "prometheus_client is required for telemetry. Please add it to dependencies."
    ) from exc


class BaseMetrics:
    """Интерфейс метрик MCP-инструментов."""

    def inc_tool_call(self, tool: str) -> None:
        raise NotImplementedError

    def inc_tool_error(self, tool: str, error_type: str) -> None:
        raise NotImplementedError

    def observe_latency(self, tool: str, seconds: float) -> None:
        raise NotImplementedError

    def render(self) -> tuple[str, str]:
        """
        Вернуть сериализованные метрики и MIME-тип.
        """
        raise NotImplementedError


class NullMetrics(BaseMetrics):
    """Пустая реализация, когда мониторинг выключен."""

    def inc_tool_call(self, tool: str) -> None:  # pragma: no cover - простая заглушка
        return None

    def inc_tool_error(self, tool: str, error_type: str) -> None:  # pragma: no cover - простая заглушка
        return None

    def observe_latency(self, tool: str, seconds: float) -> None:  # pragma: no cover - простая заглушка
        return None

    def render(self) -> tuple[str, str]:
        return "# monitoring disabled\n", "text/plain"


class McpMetrics(BaseMetrics):
    """
    Prometheus-метрики для risk-analytics-mcp.

    Экспортирует:
    - tool_calls_total{tool}
    - tool_errors_total{tool,error_type}
    - mcp_http_latency_seconds{tool}
    - risk_analytics_mcp_up (gauge)
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.tool_calls_total = Counter(
            "tool_calls_total",
            "Total number of MCP tool calls.",
            ["tool"],
            registry=self.registry,
        )
        self.tool_errors_total = Counter(
            "tool_errors_total",
            "Total number of MCP tool errors by type.",
            ["error_type", "tool"],
            registry=self.registry,
        )
        self.mcp_http_latency_seconds = Histogram(
            "mcp_http_latency_seconds",
            "Latency of MCP tool handlers in seconds.",
            ["tool"],
            registry=self.registry,
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
        )
        self.up_gauge = Gauge(
            "risk_analytics_mcp_up",
            "Synthetic metric indicating the server is running.",
            registry=self.registry,
        )
        self.up_gauge.set(1)

    def inc_tool_call(self, tool: str) -> None:
        self.tool_calls_total.labels(tool=tool).inc()

    def inc_tool_error(self, tool: str, error_type: str) -> None:
        self.tool_errors_total.labels(tool=tool, error_type=error_type).inc()

    def observe_latency(self, tool: str, seconds: float) -> None:
        self.mcp_http_latency_seconds.labels(tool=tool).observe(seconds)

    def render(self) -> tuple[str, str]:
        body = generate_latest(self.registry).decode("utf-8")
        return body, CONTENT_TYPE_LATEST
