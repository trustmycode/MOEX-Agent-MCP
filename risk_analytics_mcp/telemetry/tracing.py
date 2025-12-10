from __future__ import annotations

from contextlib import nullcontext
from typing import Optional

try:  # Optional OTEL support
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except Exception:  # pragma: no cover - OTEL является необязательным
    trace = None  # type: ignore[assignment]


class NullTracing:
    """Заглушка, когда OTEL не настроен."""

    def start_span(self, name: str):
        return nullcontext()


class McpTracing(NullTracing):
    """
    Минимальная OTEL-интеграция: создаёт tracer, если заданы endpoint и service_name.
    При отсутствии зависимостей/конфига работает как no-op.
    """

    def __init__(self, *, service_name: Optional[str], otel_endpoint: Optional[str]) -> None:
        self._tracer = None
        if trace and service_name and otel_endpoint:
            resource = Resource.create({"service.name": service_name})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=otel_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(service_name)

    def start_span(self, name: str):
        if not self._tracer:
            return super().start_span(name)
        return self._tracer.start_as_current_span(name)
