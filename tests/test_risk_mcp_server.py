import os
import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient

from moex_iss_sdk.exceptions import InvalidTickerError
from moex_iss_sdk.models import OhlcvBar
from risk_analytics_mcp.config import RiskMcpConfig
from risk_analytics_mcp.server import RiskMcpServer
from risk_analytics_mcp.tools import compute_portfolio_risk_basic_core
from risk_analytics_mcp.tools import compute_correlation_matrix_core


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


def test_compute_portfolio_risk_basic_accepts_extended_fields(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30)
    server = RiskMcpServer(cfg)
    fn = server.fastmcp._tools["compute_portfolio_risk_basic"].func

    def fake_ohlcv(ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        base = 100.0 if ticker == "AAA" else 200.0
        return [_bar(1, base), _bar(2, base * 1.02), _bar(3, base * 1.03)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    payload = fn(
        positions=[{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}],
        from_date="2024-01-01",
        to_date="2024-01-03",
        aggregates={"asset_class_weights": {"equity": 1.0}, "fx_exposure_weights": {"USD": 0.2, "RUB": 0.8}},
        stress_scenarios=["equity_-10_fx_+20", "rates_+300bp"],
        var_config={"confidence_level": 0.9, "horizon_days": 1},
    )

    assert payload["error"] is None
    assert {item["id"] for item in payload["stress_results"]} == {"equity_-10_fx_+20", "rates_+300bp"}
    assert payload["var_light"] is not None
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


def test_http_streamable_accepts_extended_portfolio_payload(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30)
    server = RiskMcpServer(cfg)

    def fake_ohlcv(ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        base = 100.0 if ticker == "AAA" else 50.0
        return [_bar(1, base), _bar(2, base * 1.01), _bar(3, base * 1.02)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    # stateless + json_response simplify HTTP call without session handshake
    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)

    payload = {
        "jsonrpc": "2.0",
        "id": "risk-http-1",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-03",
                "rebalance": "buy_and_hold",
                "aggregates": {
                    "asset_class_weights": {"equity": 1.0},
                    "fx_exposure_weights": {"USD": 0.2, "RUB": 0.8},
                },
                "stress_scenarios": ["equity_-10_fx_+20", "rates_+300bp"],
                "var_config": {"confidence_level": 0.9, "horizon_days": 1},
            },
        },
    }

    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json=payload,
        )
        assert resp.status_code == 200
        body = resp.json()
        structured = body["result"]["structuredContent"]
        assert structured["error"] is None
        assert {item["id"] for item in structured["stress_results"]} == {"equity_-10_fx_+20", "rates_+300bp"}
        assert structured["var_light"] is not None


def test_stateful_session_handshake_and_call(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30)
    server = RiskMcpServer(cfg)

    def fake_ohlcv(ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        base = 100.0 if ticker == "AAA" else 50.0
        return [_bar(1, base), _bar(2, base * 1.01), _bar(3, base * 1.02)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=False, json_response=True)
    init_payload = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "pytest", "version": "1.0"}, "capabilities": {}},
    }
    call_payload = {
        "jsonrpc": "2.0",
        "id": "risk-http-stateful-1",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-03",
            },
        },
    }

    with TestClient(app) as client:
        init_resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=init_payload)
        assert init_resp.status_code == 200
        session_id = init_resp.headers.get("mcp-session-id")
        assert session_id

        call_resp = client.post(
            "/mcp",
            headers={"Content-Type": "application/json", "Accept": "application/json", "mcp-session-id": session_id},
            json=call_payload,
        )
        assert call_resp.status_code == 200
        structured = call_resp.json()["result"]["structuredContent"]
        assert structured["error"] is None
        assert structured["stress_results"]


def test_invalid_fields_return_validation_error(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30)
    server = RiskMcpServer(cfg)

    def fake_ohlcv(*args, **kwargs):
        return [_bar(1, 100.0), _bar(2, 101.0)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    payload = {
        "jsonrpc": "2.0",
        "id": "risk-invalid",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 1.0}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-02",
                "stress_scenarios": ["unknown_scenario"],
                "var_config": {"confidence_level": 0.95, "horizon_days": "bad"},
            },
        },
    }

    with TestClient(app) as client:
        resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload)
        assert resp.status_code == 200
        result = resp.json()["result"]["structuredContent"]
        assert result["error"]["error_type"] == "VALIDATION_ERROR"


def test_limits_enforced_via_http(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=1, max_lookback_days=2)
    server = RiskMcpServer(cfg)

    def fake_ohlcv(*args, **kwargs):
        return [_bar(1, 100.0), _bar(2, 101.0), _bar(3, 102.0)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    too_many_payload = {
        "jsonrpc": "2.0",
        "id": "risk-limit-1",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-02",
            },
        },
    }
    too_long_payload = {
        "jsonrpc": "2.0",
        "id": "risk-limit-2",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 1.0}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-10",
            },
        },
    }

    with TestClient(app) as client:
        resp_many = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=too_many_payload)
        assert resp_many.status_code == 200
        assert resp_many.json()["result"]["structuredContent"]["error"]["error_type"] == "TOO_MANY_TICKERS"

        resp_range = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=too_long_payload)
        assert resp_range.status_code == 200
        assert resp_range.json()["result"]["structuredContent"]["error"]["error_type"] == "DATE_RANGE_TOO_LARGE"


def test_default_aggregates_and_stress_scenarios(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30)
    server = RiskMcpServer(cfg)

    def fake_ohlcv(*args, **kwargs):
        return [_bar(1, 100.0), _bar(2, 101.0), _bar(3, 102.0)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    payload = {
        "jsonrpc": "2.0",
        "id": "risk-default-stress",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 1.0}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-03",
            },
        },
    }

    with TestClient(app) as client:
        resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload)
        assert resp.status_code == 200
        structured = resp.json()["result"]["structuredContent"]
        assert structured["error"] is None
        assert structured["stress_results"]  # defaults applied


def test_http_stress_credit_and_rates_with_duration(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30)
    server = RiskMcpServer(cfg)

    def fake_ohlcv(*args, **kwargs):
        return [_bar(1, 100.0), _bar(2, 102.0), _bar(3, 101.0)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    payload = {
        "jsonrpc": "2.0",
        "id": "risk-credit-dur",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-03",
                "aggregates": {
                    "asset_class_weights": {"fixed_income": 1.0},
                    "fixed_income_duration_years": 5.0,
                    "credit_spread_duration_years": 4.0,
                },
                "stress_scenarios": ["equity_-10_fx_+20", "rates_+300bp", "credit_spreads_+150bp"],
            },
        },
    }

    with TestClient(app) as client:
        resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload)
        assert resp.status_code == 200
        structured = resp.json()["result"]["structuredContent"]
        assert structured["error"] is None
        stress_map = {item["id"]: item for item in structured["stress_results"]}
        assert "credit_spreads_+150bp" in stress_map
        assert stress_map["rates_+300bp"]["pnl_pct"] == pytest.approx(-15.0)
        assert stress_map["credit_spreads_+150bp"]["pnl_pct"] == pytest.approx(-6.0)


@pytest.mark.skipif(not os.getenv("ENABLE_RISK_ISS_SMOKE"), reason="ENABLE_RISK_ISS_SMOKE not set")
def test_compute_portfolio_risk_basic_live_iss():
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30)
    server = RiskMcpServer(cfg)
    payload = {
        "positions": [{"ticker": "SBER", "weight": 1.0}],
        "from_date": "2024-12-02",
        "to_date": "2024-12-06",
    }
    result = compute_portfolio_risk_basic_core(payload, server.iss_client, max_tickers=cfg.max_portfolio_tickers, max_lookback_days=cfg.max_lookback_days)
    assert result.error is None


@pytest.mark.skipif(not os.getenv("ENABLE_RISK_CORR_ISS_SMOKE"), reason="ENABLE_RISK_CORR_ISS_SMOKE not set")
def test_compute_correlation_matrix_live_iss():
    """
    E2E‑smoke: расчёт матрицы корреляций на живых данных ISS.
    """
    cfg = RiskMcpConfig(max_correlation_tickers=3, max_lookback_days=90)
    server = RiskMcpServer(cfg)
    payload = {
        "tickers": ["SBER", "GAZP"],
        "from_date": "2024-09-01",
        "to_date": "2024-12-01",
    }
    result = compute_correlation_matrix_core(
        payload,
        server.iss_client,
        max_tickers=cfg.max_correlation_tickers,
        max_lookback_days=cfg.max_lookback_days,
    )
    assert result.error is None
    assert result.tickers == ["SBER", "GAZP"]
    assert len(result.matrix) == 2
    assert all(len(row) == 2 for row in result.matrix)


def test_metrics_increment_on_http_call(monkeypatch):
    cfg = RiskMcpConfig(max_portfolio_tickers=3, max_lookback_days=30, enable_monitoring=True)
    server = RiskMcpServer(cfg)

    def fake_ohlcv(*args, **kwargs):
        return [_bar(1, 100.0), _bar(2, 102.0)]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_ohlcv)
    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)

    call_payload = {
        "jsonrpc": "2.0",
        "id": "risk-metrics-1",
        "method": "tools/call",
        "params": {
            "name": "compute_portfolio_risk_basic",
            "arguments": {
                "positions": [{"ticker": "AAA", "weight": 1.0}],
                "from_date": "2024-01-01",
                "to_date": "2024-01-02",
            },
        },
    }

    with TestClient(app) as client:
        metrics_before = client.get("/metrics").text
        client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=call_payload)
        metrics_after = client.get("/metrics").text

        assert 'tool_calls_total{tool="compute_portfolio_risk_basic"}' in metrics_after
        assert metrics_after != metrics_before
