from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from moex_iss_sdk import IssClient, IssClientSettings, MAX_LOOKBACK_DAYS

# Приоритетно загружаем .env.risk (если есть), затем .env.mcp, .env и .env.sdk.
load_dotenv(dotenv_path=".env.risk")
load_dotenv(dotenv_path=".env.mcp")
load_dotenv()
load_dotenv(dotenv_path=".env.sdk")


def _get_bool(value: Optional[str], *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


DEFAULT_PORT = int(os.getenv("RISK_MCP_PORT", os.getenv("PORT", "8010")))
DEFAULT_HOST = os.getenv("RISK_MCP_HOST", os.getenv("HOST", "0.0.0.0"))
DEFAULT_MAX_PORTFOLIO_TICKERS = int(os.getenv("RISK_MAX_PORTFOLIO_TICKERS", "50"))
DEFAULT_MAX_CORRELATION_TICKERS = int(os.getenv("RISK_MAX_CORRELATION_TICKERS", "20"))
DEFAULT_MAX_LOOKBACK_DAYS = int(
    os.getenv("RISK_MAX_LOOKBACK_DAYS", os.getenv("MOEX_ISS_MAX_LOOKBACK_DAYS", str(MAX_LOOKBACK_DAYS)))
)
DEFAULT_ENABLE_MONITORING = _get_bool(os.getenv("RISK_ENABLE_MONITORING") or os.getenv("ENABLE_MONITORING"))
DEFAULT_OTEL_ENDPOINT = os.getenv("RISK_OTEL_ENDPOINT") or os.getenv("OTEL_ENDPOINT")
DEFAULT_OTEL_SERVICE_NAME = os.getenv("RISK_OTEL_SERVICE_NAME") or os.getenv("OTEL_SERVICE_NAME")


@dataclass
class RiskMcpConfig:
    """
    Хранит параметры MCP-сервера риск-аналитики и настройки доступа к MOEX ISS.
    """

    port: int = DEFAULT_PORT
    host: str = DEFAULT_HOST
    max_portfolio_tickers: int = DEFAULT_MAX_PORTFOLIO_TICKERS
    max_correlation_tickers: int = DEFAULT_MAX_CORRELATION_TICKERS
    max_lookback_days: int = DEFAULT_MAX_LOOKBACK_DAYS
    enable_monitoring: bool = DEFAULT_ENABLE_MONITORING
    otel_endpoint: Optional[str] = DEFAULT_OTEL_ENDPOINT
    otel_service_name: Optional[str] = DEFAULT_OTEL_SERVICE_NAME
    iss_settings: IssClientSettings = field(default_factory=IssClientSettings.from_env)

    def __post_init__(self) -> None:
        if self.max_portfolio_tickers <= 0:
            raise ValueError("max_portfolio_tickers must be positive")
        if self.max_correlation_tickers <= 0:
            raise ValueError("max_correlation_tickers must be positive")
        if self.max_lookback_days <= 0:
            raise ValueError("max_lookback_days must be positive")

    @classmethod
    def from_env(cls) -> "RiskMcpConfig":
        """
        Построить конфигурацию из переменных окружения.
        """
        return cls(
            port=int(os.getenv("RISK_MCP_PORT", os.getenv("PORT", str(DEFAULT_PORT)))),
            host=os.getenv("RISK_MCP_HOST", os.getenv("HOST", DEFAULT_HOST)),
            max_portfolio_tickers=int(
                os.getenv("RISK_MAX_PORTFOLIO_TICKERS", str(DEFAULT_MAX_PORTFOLIO_TICKERS))
            ),
            max_correlation_tickers=int(
                os.getenv("RISK_MAX_CORRELATION_TICKERS", str(DEFAULT_MAX_CORRELATION_TICKERS))
            ),
            max_lookback_days=int(
                os.getenv("RISK_MAX_LOOKBACK_DAYS", os.getenv("MOEX_ISS_MAX_LOOKBACK_DAYS", str(DEFAULT_MAX_LOOKBACK_DAYS)))
            ),
            enable_monitoring=_get_bool(
                os.getenv("RISK_ENABLE_MONITORING") or os.getenv("ENABLE_MONITORING"),
                default=DEFAULT_ENABLE_MONITORING,
            ),
            otel_endpoint=os.getenv("RISK_OTEL_ENDPOINT") or os.getenv("OTEL_ENDPOINT"),
            otel_service_name=os.getenv("RISK_OTEL_SERVICE_NAME") or os.getenv("OTEL_SERVICE_NAME") or "risk-analytics-mcp",
            iss_settings=IssClientSettings.from_env(),
        )

    def create_iss_client(self) -> IssClient:
        """
        Сконструировать экземпляр IssClient c учётом текущих настроек.
        """
        return IssClient(self.iss_settings)
