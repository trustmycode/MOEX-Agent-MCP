import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient

from moex_iss_sdk.exceptions import InvalidTickerError
from moex_iss_sdk.models import OhlcvBar
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


def _bar(day: int, close: float) -> OhlcvBar:
    return OhlcvBar(
        ts=datetime(2024, 1, day, tzinfo=timezone.utc),
        open=close,
        high=close,
        low=close,
        close=close,
    )


def test_compute_portfolio_risk_basic_returns_metrics(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30, enable_monitoring=True)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_portfolio_risk_basic"].func

    def fake_ohlcv(ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        base = 100.0 if ticker == "SBER" else 50.0
        return [_bar(1, base), _bar(2, base * 1.01), _bar(3, base * 1.02)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    payload = fn(
        positions=[{"ticker": "SBER", "weight": 0.6}, {"ticker": "GAZP", "weight": 0.4}],
        from_date="2024-01-01",
        to_date="2024-01-03",
        rebalance="buy_and_hold",
    )

    assert payload["error"] is None
    assert len(payload["per_instrument"]) == 2
    assert payload["portfolio_metrics"]["total_return_pct"] is not None
    assert payload["concentration_metrics"]["top1_weight_pct"] == pytest.approx(60.0)
    assert payload["metadata"]["rebalance"] == "buy_and_hold"

    metrics_text, _ = server.metrics.render()
    assert 'tool_calls_total{tool="compute_portfolio_risk_basic"} 1.0' in metrics_text


def test_compute_portfolio_risk_basic_maps_errors(monkeypatch):
    cfg = RiskMcpConfig(enable_monitoring=True)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_portfolio_risk_basic"].func

    def boom(*args, **kwargs):
        raise InvalidTickerError("bad ticker")

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", boom)

    payload = fn(
        positions=[{"ticker": "BAD", "weight": 1.0}],
        from_date="2024-01-01",
        to_date="2024-01-05",
    )

    assert payload["error"]["error_type"] == "INVALID_TICKER"
    metrics_text, _ = server.metrics.render()
    assert 'tool_errors_total{error_type="INVALID_TICKER",tool="compute_portfolio_risk_basic"} 1.0' in metrics_text
def test_compute_correlation_matrix_success(monkeypatch):
    cfg = RiskMcpConfig(max_correlation_tickers=3, max_lookback_days=30, enable_monitoring=True)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    def fake_ohlcv(ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        base = 100.0 if ticker == "AAA" else 50.0
        return [_bar(1, base), _bar(2, base * 1.01), _bar(3, base * 0.99)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    payload = fn(tickers=["AAA", "BBB"], from_date="2024-01-01", to_date="2024-01-03")

    assert payload["error"] is None
    assert payload["tickers"] == ["AAA", "BBB"]
    assert payload["metadata"]["num_observations"] == 2
    matrix = payload["matrix"]
    assert len(matrix) == 2 and all(len(row) == 2 for row in matrix)
    assert matrix[0][0] == pytest.approx(1.0)
    assert matrix[0][1] == pytest.approx(matrix[1][0])


def test_compute_correlation_matrix_enforces_ticker_limit():
    cfg = RiskMcpConfig(max_correlation_tickers=1, max_lookback_days=5)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    payload = fn(tickers=["A", "B"], from_date="2024-01-01", to_date="2024-01-02")
    assert payload["error"]["error_type"] == "TOO_MANY_TICKERS"
    assert payload["matrix"] == []


def test_compute_correlation_matrix_maps_sdk_errors(monkeypatch):
    cfg = RiskMcpConfig(max_correlation_tickers=3, enable_monitoring=True)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    def boom(*args, **kwargs):
        raise InvalidTickerError("bad ticker")

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", boom)

    payload = fn(tickers=["BAD", "OK"], from_date="2024-01-01", to_date="2024-01-05")

    assert payload["error"]["error_type"] == "INVALID_TICKER"
    metrics_text, _ = server.metrics.render()
    assert 'tool_errors_total{error_type="INVALID_TICKER",tool="compute_correlation_matrix"} 1.0' in metrics_text


def test_compute_correlation_matrix_handles_insufficient_data(monkeypatch):
    cfg = RiskMcpConfig(max_correlation_tickers=2, max_lookback_days=30)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    def short_series(*args, **kwargs):
        return [_bar(1, 100.0)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", short_series)

    payload = fn(tickers=["AAA", "BBB"], from_date="2024-01-01", to_date="2024-01-05")
    assert payload["error"]["error_type"] == "INSUFFICIENT_DATA"
    assert payload["matrix"] == []


def test_compute_correlation_matrix_rejects_invalid_date_order():
    cfg = RiskMcpConfig(max_correlation_tickers=2)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    payload = fn(tickers=["AAA", "BBB"], from_date="2024-02-10", to_date="2024-02-01")
    assert payload["error"]["error_type"] == "VALIDATION_ERROR"
    assert payload["matrix"] == []


def test_compute_correlation_matrix_rejects_date_range_too_large():
    cfg = RiskMcpConfig(max_correlation_tickers=2, max_lookback_days=2)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    payload = fn(tickers=["AAA", "BBB"], from_date="2024-01-01", to_date="2024-01-10")
    assert payload["error"]["error_type"] == "DATE_RANGE_TOO_LARGE"
    assert payload["matrix"] == []


def test_compute_correlation_matrix_zero_variance(monkeypatch):
    cfg = RiskMcpConfig(max_correlation_tickers=2)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_correlation_matrix"].func

    def flat_series(*args, **kwargs):
        return [_bar(1, 100.0), _bar(2, 100.0), _bar(3, 100.0)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", flat_series)

    payload = fn(tickers=["AAA", "BBB"], from_date="2024-01-01", to_date="2024-01-05")
    assert payload["error"]["error_type"] == "INSUFFICIENT_DATA"
    assert payload["matrix"] == []
