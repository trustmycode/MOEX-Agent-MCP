import pytest
from starlette.testclient import TestClient

from risk_analytics_mcp.config import RiskMcpConfig
from risk_analytics_mcp.server import RiskMcpServer


def test_risk_health_and_metrics_routes():
    cfg = RiskMcpConfig(enable_monitoring=True)
    server = RiskMcpServer(cfg)
    app = server.fastmcp.http_app(transport="streamable-http")

    with TestClient(app) as client:
        resp_health = client.get("/health")
        assert resp_health.status_code == 200
        assert resp_health.json() == {"status": "ok"}

        resp_metrics = client.get("/metrics")
        assert resp_metrics.status_code == 200
        assert "risk_analytics_mcp_up" in resp_metrics.text


def test_metrics_route_disabled_returns_placeholder():
    cfg = RiskMcpConfig(enable_monitoring=False)
    server = RiskMcpServer(cfg)
    app = server.fastmcp.http_app(transport="streamable-http")

    with TestClient(app) as client:
        resp_metrics = client.get("/metrics")
        assert resp_metrics.status_code == 200
        assert "# monitoring disabled" in resp_metrics.text


def test_stub_tools_return_payload_and_limits():
    cfg = RiskMcpConfig(max_portfolio_tickers=2, max_lookback_days=30)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_portfolio_risk_basic"].func

    payload = fn(tickers=["sber", "gazp"], lookback_days=7)

    assert payload["metadata"]["tickers"] == ["SBER", "GAZP"]
    assert payload["metadata"]["limits"]["max_portfolio_tickers"] == 2
    assert payload["metadata"]["limits"]["max_lookback_days"] == 30
    assert payload["data"]["status"] == "stub"


def test_stub_tools_enforce_limits():
    cfg = RiskMcpConfig(max_portfolio_tickers=1, max_lookback_days=5)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    with pytest.raises(ValueError):
        fn(tickers=["A", "B"])

    with pytest.raises(ValueError):
        fn(tickers=["A"], lookback_days=10)


def test_stub_tools_normalize_tickers_and_strip_whitespace():
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=10)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    payload = fn(tickers=[" sber ", "GaZp", "   "], lookback_days=3)

    assert payload["metadata"]["tickers"] == ["SBER", "GAZP"]
    assert payload["data"]["status"] == "stub"


def test_stub_tools_error_path_returns_not_implemented(monkeypatch):
    cfg = RiskMcpConfig(enable_monitoring=True)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_portfolio_risk_basic"].func

    # Форсим ошибку в процессе формирования stub-ответа
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "_stub_payload", boom)

    payload = fn(tickers=["SBER"], lookback_days=1)

    assert payload["error"]["error_type"] == "NOT_IMPLEMENTED"
    assert "boom" in payload["error"]["message"]
    metrics_text, _ = server.metrics.render()
    assert 'tool_errors_total{error_type="RuntimeError",tool="compute_portfolio_risk_basic"} 1.0' in metrics_text
