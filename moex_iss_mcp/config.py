from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import find_dotenv, load_dotenv

from moex_iss_sdk import IssClientSettings
from moex_iss_sdk import endpoints as iss_endpoints

# Приоритетно загружаем .env.mcp, затем общий .env и .env.sdk (для MOEX-параметров)
load_dotenv(find_dotenv(filename=".env.mcp", raise_error_if_not_found=False))
load_dotenv(find_dotenv())
load_dotenv(find_dotenv(filename=".env.sdk", raise_error_if_not_found=False))

# Значения по умолчанию из окружения, чтобы избежать хардкода.
DEFAULT_PORT = int(os.getenv("PORT", "8000"))
DEFAULT_HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_MOEX_ISS_RATE_LIMIT_RPS = float(os.getenv("MOEX_ISS_RATE_LIMIT_RPS", "3"))
DEFAULT_MOEX_ISS_TIMEOUT_SECONDS = float(os.getenv("MOEX_ISS_TIMEOUT_SECONDS", "10"))
DEFAULT_ENABLE_MONITORING = False if os.getenv("ENABLE_MONITORING") is None else os.getenv("ENABLE_MONITORING", "false").lower() == "true"


def _get_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class McpConfig:
    """
    Хранит параметры MCP-сервера и настройки доступа к MOEX ISS.
    """

    port: int = DEFAULT_PORT
    host: str = DEFAULT_HOST
    moex_iss_base_url: str = iss_endpoints.DEFAULT_BASE_URL
    moex_iss_rate_limit_rps: float = DEFAULT_MOEX_ISS_RATE_LIMIT_RPS
    moex_iss_timeout_seconds: float = DEFAULT_MOEX_ISS_TIMEOUT_SECONDS
    enable_monitoring: bool = DEFAULT_ENABLE_MONITORING
    otel_endpoint: Optional[str] = None
    otel_service_name: Optional[str] = None

    @classmethod
    def from_env(cls) -> "McpConfig":
        """
        Построить конфигурацию из переменных окружения.
        """
        return cls(
            port=int(os.getenv("PORT", str(DEFAULT_PORT))),
            host=os.getenv("HOST", DEFAULT_HOST),
            moex_iss_base_url=os.getenv("MOEX_ISS_BASE_URL", iss_endpoints.DEFAULT_BASE_URL),
            moex_iss_rate_limit_rps=float(os.getenv("MOEX_ISS_RATE_LIMIT_RPS", str(DEFAULT_MOEX_ISS_RATE_LIMIT_RPS))),
            moex_iss_timeout_seconds=float(
                os.getenv("MOEX_ISS_TIMEOUT_SECONDS", str(DEFAULT_MOEX_ISS_TIMEOUT_SECONDS))
            ),
            enable_monitoring=_get_bool(os.getenv("ENABLE_MONITORING"), default=DEFAULT_ENABLE_MONITORING),
            otel_endpoint=os.getenv("OTEL_ENDPOINT"),
            otel_service_name=os.getenv("OTEL_SERVICE_NAME"),
        )

    def to_iss_settings(self) -> IssClientSettings:
        """
        Сконструировать настройки клиента MOEX ISS на основе конфигурации MCP.
        """
        return IssClientSettings(
            base_url=self.moex_iss_base_url,
            rate_limit_rps=self.moex_iss_rate_limit_rps,
            timeout_seconds=self.moex_iss_timeout_seconds,
        )


def _require_env_vars(names: list[str]) -> dict[str, str]:
    """
    Проверяет наличие обязательных переменных окружения.

    Args:
        names: Список имен переменных окружения

    Returns:
        Словарь с переменными окружения

    Raises:
        McpError: Если отсутствуют обязательные переменные
    """
    from mcp.shared.exceptions import ErrorData, McpError

    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise McpError(
            ErrorData(
                code=-32602,  # Invalid params
                message=f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}",
            )
        )
    return {n: os.getenv(n, "") for n in names}
