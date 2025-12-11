import os
import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient

from moex_iss_mcp.config import McpConfig
from moex_iss_mcp.server import McpServer
from moex_iss_sdk.models import SecuritySnapshot, OhlcvBar
from moex_iss_sdk.exceptions import InvalidTickerError, DateRangeTooLargeError


def test_mcp_config_from_env(monkeypatch):
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("MOEX_ISS_BASE_URL", "http://example/")
    monkeypatch.setenv("MOEX_ISS_RATE_LIMIT_RPS", "7")
    monkeypatch.setenv("MOEX_ISS_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("ENABLE_MONITORING", "true")
    cfg = McpConfig.from_env()
    assert cfg.port == 9000
    assert cfg.host == "127.0.0.1"
    assert cfg.moex_iss_base_url == "http://example/"
    assert cfg.moex_iss_rate_limit_rps == 7.0
    assert cfg.moex_iss_timeout_seconds == 5.0
    assert cfg.enable_monitoring is True


def test_health_and_metrics_routes():
    cfg = McpConfig(enable_monitoring=True)
    server = McpServer(cfg)
    app = server.fastmcp.http_app(transport="streamable-http")

    with TestClient(app) as client:
        resp_health = client.get("/health")
        assert resp_health.status_code == 200
        assert resp_health.json() == {"status": "ok"}

        resp_metrics = client.get("/metrics")
        assert resp_metrics.status_code == 200
        assert "moex_iss_mcp_up" in resp_metrics.text


def test_stateful_streamable_session_and_call(monkeypatch):
    cfg = McpConfig(enable_monitoring=True)
    server = McpServer(cfg)

    def fake_snapshot(ticker: str, board: str | None = None):
        return SecuritySnapshot(
            ticker=ticker,
            board=board or "TQBR",
            as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_price=100.0,
            price_change_abs=1.0,
            price_change_pct=1.0,
            open_price=99.0,
            high_price=101.0,
            low_price=98.0,
            volume=1000.0,
            value=100000.0,
        )

    monkeypatch.setattr(server.iss_client, "get_security_snapshot", fake_snapshot)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=False, json_response=True)
    init_payload = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "pytest", "version": "1.0"}, "capabilities": {}},
    }
    call_payload = {
        "jsonrpc": "2.0",
        "id": "snap-1",
        "method": "tools/call",
        "params": {"name": "get_security_snapshot", "arguments": {"ticker": "SBER", "board": "TQBR"}},
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
        assert structured["metadata"]["ticker"] == "SBER"


def test_invalid_ticker_maps_error_http(monkeypatch):
    cfg = McpConfig()
    server = McpServer(cfg)

    def boom(*args, **kwargs):
        raise InvalidTickerError("bad ticker")

    monkeypatch.setattr(server.iss_client, "get_security_snapshot", boom)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    payload = {
        "jsonrpc": "2.0",
        "id": "snap-invalid",
        "method": "tools/call",
        "params": {"name": "get_security_snapshot", "arguments": {"ticker": "BAD", "board": "TQBR"}},
    }

    with TestClient(app) as client:
        resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload)
        body = resp.json()["result"]["structuredContent"]
        assert body["error"]["error_type"] == "INVALID_TICKER"


def test_ohlcv_limits_error_http(monkeypatch):
    cfg = McpConfig()
    server = McpServer(cfg)

    def too_wide(*args, **kwargs):
        raise DateRangeTooLargeError("too wide")

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", too_wide)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    payload = {
        "jsonrpc": "2.0",
        "id": "ohlcv-limit",
        "method": "tools/call",
        "params": {
            "name": "get_ohlcv_timeseries",
            "arguments": {"ticker": "SBER", "board": "TQBR", "from_date": "2024-01-01", "to_date": "2024-02-10", "interval": "1d"},
        },
    }

    with TestClient(app) as client:
        resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload)
        body = resp.json()["result"]["structuredContent"]
        assert body["error"]["error_type"] == "DATE_RANGE_TOO_LARGE"


def test_default_dates_and_metrics_increment(monkeypatch):
    cfg = McpConfig(enable_monitoring=True)
    server = McpServer(cfg)

    def fake_bars(*args, **kwargs):
        return [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=101.0, high=101.0, low=101.0, close=101.0),
        ]

    monkeypatch.setattr(server.iss_client, "get_ohlcv_series", fake_bars)

    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    payload = {
        "jsonrpc": "2.0",
        "id": "ohlcv-default",
        "method": "tools/call",
        "params": {"name": "get_ohlcv_timeseries", "arguments": {"ticker": "SBER", "board": "TQBR"}},
    }

    with TestClient(app) as client:
        metrics_before = client.get("/metrics").text
        resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload)
        assert resp.status_code == 200
        body = resp.json()["result"]["structuredContent"]
        assert body["error"] is None
        assert body["data"]
        metrics_after = client.get("/metrics").text
        assert 'tool_calls_total{tool="get_ohlcv_timeseries"}' in metrics_after
        assert metrics_after != metrics_before


@pytest.mark.skipif(not os.getenv("ENABLE_ISS_SMOKE"), reason="ENABLE_ISS_SMOKE not set")
def test_smoke_live_security_snapshot():
    cfg = McpConfig()
    server = McpServer(cfg)
    app = server.fastmcp.http_app(transport="streamable-http", stateless_http=True, json_response=True)
    payload = {
        "jsonrpc": "2.0",
        "id": "snap-live",
        "method": "tools/call",
        "params": {"name": "get_security_snapshot", "arguments": {"ticker": "SBER", "board": "TQBR"}},
    }

    with TestClient(app) as client:
        resp = client.post("/mcp", headers={"Content-Type": "application/json", "Accept": "application/json"}, json=payload)
        body = resp.json()["result"]["structuredContent"]
        assert body["error"] is None
