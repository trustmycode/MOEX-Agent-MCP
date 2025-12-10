import pytest

from moex_iss_sdk import IssClient, IssClientSettings
from risk_analytics_mcp.config import RiskMcpConfig


def test_risk_mcp_config_from_env(monkeypatch):
    monkeypatch.setenv("RISK_MCP_PORT", "8100")
    monkeypatch.setenv("RISK_MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("RISK_MAX_PORTFOLIO_TICKERS", "15")
    monkeypatch.setenv("RISK_MAX_LOOKBACK_DAYS", "120")
    monkeypatch.setenv("RISK_ENABLE_MONITORING", "true")
    monkeypatch.setenv("RISK_OTEL_ENDPOINT", "http://otel.local:4318")
    monkeypatch.setenv("RISK_OTEL_SERVICE_NAME", "risk-mcp")
    monkeypatch.setenv("MOEX_ISS_BASE_URL", "http://example-iss/")
    monkeypatch.setenv("MOEX_ISS_RATE_LIMIT_RPS", "9")

    cfg = RiskMcpConfig.from_env()

    assert cfg.port == 8100
    assert cfg.host == "127.0.0.1"
    assert cfg.max_portfolio_tickers == 15
    assert cfg.max_lookback_days == 120
    assert cfg.enable_monitoring is True
    assert cfg.otel_endpoint == "http://otel.local:4318"
    assert cfg.otel_service_name == "risk-mcp"
    assert cfg.iss_settings.base_url == "http://example-iss/"
    assert cfg.iss_settings.rate_limit_rps == 9


def test_risk_mcp_config_validation_errors():
    with pytest.raises(ValueError):
        RiskMcpConfig(max_portfolio_tickers=0)
    with pytest.raises(ValueError):
        RiskMcpConfig(max_lookback_days=0)


def test_create_iss_client_uses_settings():
    settings = IssClientSettings(base_url="http://stub-iss/", rate_limit_rps=1.0, timeout_seconds=2)
    cfg = RiskMcpConfig(
        port=9001,
        host="127.0.0.1",
        max_portfolio_tickers=5,
        max_lookback_days=10,
        iss_settings=settings,
    )

    client = cfg.create_iss_client()

    assert isinstance(client, IssClient)
    assert client.settings.base_url == "http://stub-iss/"
    assert client.settings.rate_limit_rps == 1.0
