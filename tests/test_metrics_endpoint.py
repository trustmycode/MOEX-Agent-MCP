import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from starlette.testclient import TestClient

from moex_iss_mcp.config import McpConfig
from moex_iss_mcp.server import McpServer
from moex_iss_sdk.exceptions import InvalidTickerError


def _sample_snapshot() -> SimpleNamespace:
    return SimpleNamespace(
        ticker="SBER",
        board="TQBR",
        as_of=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_price=100.0,
        price_change_abs=1.5,
        price_change_pct=1.2,
        open_price=98.0,
        high_price=101.0,
        low_price=97.0,
        volume=1000.0,
        value=100000.0,
    )


def test_prometheus_metrics_exposed_and_incremented():
    cfg = McpConfig(enable_monitoring=True)
    server = McpServer(cfg)
    app = server.fastmcp.http_app(transport="streamable-http")

    with TestClient(app) as client:
        with patch.object(
            server.iss_client, "get_security_snapshot", return_value=_sample_snapshot()
        ):
            asyncio.run(
                server.fastmcp._tool_manager._tools["get_security_snapshot"].fn(
                    ticker="SBER", board="TQBR"
                )
            )

        with patch.object(
            server.iss_client,
            "get_security_snapshot",
            side_effect=InvalidTickerError("bad ticker"),
        ):
            result = asyncio.run(
                server.fastmcp._tool_manager._tools["get_security_snapshot"].fn(
                    ticker="BAD", board="TQBR"
                )
            ).structured_content
            assert result["error"]["error_type"] == "INVALID_TICKER"

        resp = client.get("/metrics")
        assert resp.status_code == 200
        body = resp.text

        assert 'tool_calls_total{tool="get_security_snapshot"} 2.0' in body
        assert 'tool_errors_total{error_type="INVALID_TICKER",tool="get_security_snapshot"} 1.0' in body
        assert 'mcp_http_latency_seconds_count{tool="get_security_snapshot"}' in body
        assert "moex_iss_mcp_up 1.0" in body or "moex_iss_mcp_up 1" in body
