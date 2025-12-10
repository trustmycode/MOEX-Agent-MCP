from risk_analytics_mcp.telemetry.metrics import McpMetrics, NullMetrics
from risk_analytics_mcp.telemetry.tracing import McpTracing, NullTracing


def test_mcp_metrics_counters_and_render():
    metrics = McpMetrics()
    metrics.inc_tool_call("compute_portfolio_risk_basic")
    metrics.inc_tool_error("compute_portfolio_risk_basic", "RUNTIME")
    metrics.observe_latency("compute_portfolio_risk_basic", 0.123)

    body, content_type = metrics.render()

    assert content_type.startswith("text/plain")
    assert 'tool_calls_total{tool="compute_portfolio_risk_basic"} 1.0' in body
    assert 'tool_errors_total{error_type="RUNTIME",tool="compute_portfolio_risk_basic"} 1.0' in body
    assert "risk_analytics_mcp_up" in body


def test_null_metrics_is_noop():
    metrics = NullMetrics()
    metrics.inc_tool_call("x")
    metrics.inc_tool_error("x", "err")
    metrics.observe_latency("x", 0.1)
    body, content_type = metrics.render()
    assert "# monitoring disabled" in body
    assert content_type == "text/plain"


def test_tracing_noop_and_otlp_toggle(monkeypatch):
    tracing = NullTracing()
    with tracing.start_span("noop"):
        pass  # should not raise

    # OTEL dependencies may be absent; the class should degrade gracefully
    tracing2 = McpTracing(service_name=None, otel_endpoint=None)
    with tracing2.start_span("noop2"):
        pass  # should not raise
