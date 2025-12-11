"""
Маппер ошибок SDK в унифицированную модель для MCP-инструментов.

Позволяет сервисам (moex_iss_mcp, risk_analytics_mcp и др.) получать один и тот
же формат ошибок без жёсткой зависимости на конкретный MCP-пакет.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .exceptions import (
    DateRangeTooLargeError,
    InvalidTickerError,
    IssSdkError,
    IssServerError,
    IssTimeoutError,
    TooManyTickersError,
    UnknownIssError,
)


class ToolErrorModel(BaseModel):
    """
    Унифицированная модель ошибки для MCP-инструментов.

    Совместима с JSON Schema, используемой сервисами MCP.
    """

    error_type: str = Field(description="Тип ошибки (INVALID_TICKER, ISS_TIMEOUT, и т.д.)")
    message: str = Field(description="Человекочитаемое сообщение об ошибке")
    details: Optional[dict[str, Any]] = Field(default=None, description="Дополнительные детали ошибки (опционально)")


class ErrorMapper:
    """
    Маппер для преобразования исключений в ToolErrorModel.
    """

    @staticmethod
    def map_exception(exc: Exception) -> ToolErrorModel:
        """
        Преобразовать исключение в ToolErrorModel.
        """
        # Исключения SDK
        if isinstance(exc, IssSdkError):
            return ToolErrorModel(
                error_type=exc.error_type,
                message=exc.message,
                details=exc.details if hasattr(exc, "details") else None,
            )

        # Валидационные ошибки
        if isinstance(exc, ValueError):
            return ToolErrorModel(
                error_type="VALIDATION_ERROR",
                message=str(exc) or "Validation error",
                details={"exception_type": type(exc).__name__},
            )

        if isinstance(exc, KeyError):
            return ToolErrorModel(
                error_type="VALIDATION_ERROR",
                message=f"Missing required field: {exc}",
                details={"exception_type": type(exc).__name__},
            )

        # Сетевые/таймаут ошибки (если не обёрнуты в SDK)
        error_message = str(exc) or "Unknown error"
        error_type = "UNKNOWN"

        error_lower = error_message.lower()
        if "timeout" in error_lower or "timed out" in error_lower:
            error_type = "ISS_TIMEOUT"
        elif "connection" in error_lower or "network" in error_lower:
            error_type = "NETWORK_ERROR"
        elif "404" in error_message or "not found" in error_lower:
            error_type = "INVALID_TICKER"
        elif "500" in error_message or "502" in error_message or "503" in error_message:
            error_type = "ISS_5XX"

        return ToolErrorModel(
            error_type=error_type,
            message=error_message,
            details={"exception_type": type(exc).__name__},
        )

    @staticmethod
    def map_iss_sdk_error(error: IssSdkError) -> ToolErrorModel:
        """
        Явный маппинг для исключений SDK (для удобства и явности).
        """
        return ToolErrorModel(error_type=error.error_type, message=error.message, details=error.details)

    @classmethod
    def get_error_type_for_exception(cls, exc: Exception) -> str:
        """
        Получить error_type для исключения без создания полной модели.
        """
        if isinstance(exc, IssSdkError):
            return exc.error_type

        if isinstance(exc, ValueError):
            return "VALIDATION_ERROR"
        if isinstance(exc, KeyError):
            return "VALIDATION_ERROR"

        error_message = str(exc).lower()
        if "timeout" in error_message:
            return "ISS_TIMEOUT"
        if "404" in str(exc) or "not found" in error_message:
            return "INVALID_TICKER"
        if "500" in str(exc) or "502" in str(exc) or "503" in str(exc):
            return "ISS_5XX"

        return "UNKNOWN"


# Пересборка модели для корректной работы с postponed annotations
ToolErrorModel.model_rebuild()


__all__ = [
    "ErrorMapper",
    "ToolErrorModel",
    "IssSdkError",
    "InvalidTickerError",
    "DateRangeTooLargeError",
    "TooManyTickersError",
    "IssTimeoutError",
    "IssServerError",
    "UnknownIssError",
]
