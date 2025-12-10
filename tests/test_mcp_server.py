from starlette.testclient import TestClient

from moex_iss_mcp.config import McpConfig
from moex_iss_mcp.server import McpServer


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
