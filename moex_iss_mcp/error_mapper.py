"""
Модуль для нормализации ошибок в унифицированный формат MCP.

ErrorMapper преобразует исключения SDK и другие ошибки в ToolErrorModel,
который соответствует JSON Schema в SPEC.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from moex_iss_sdk.exceptions import (
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

    Соответствует JSON Schema в SPEC_moex-iss-mcp.md.
    """

    error_type: str = Field(description="Тип ошибки (INVALID_TICKER, ISS_TIMEOUT, и т.д.)")
    message: str = Field(description="Человекочитаемое сообщение об ошибке")
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Дополнительные детали ошибки (опционально)"
    )


class ErrorMapper:
    """
    Маппер для преобразования исключений в ToolErrorModel.

    Обрабатывает исключения SDK и другие типы ошибок, нормализуя их
    в единый формат для MCP-инструментов.
    """

    @staticmethod
    def map_exception(exc: Exception) -> ToolErrorModel:
        """
        Преобразовать исключение в ToolErrorModel.

        Args:
            exc: Исключение для маппинга.

        Returns:
            ToolErrorModel с нормализованными полями.
        """
        # Обработка исключений SDK
        if isinstance(exc, IssSdkError):
            return ToolErrorModel(
                error_type=exc.error_type,
                message=exc.message,
                details=exc.details if hasattr(exc, "details") else None,
            )

        # Обработка стандартных исключений Python
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

        # Обработка сетевых/таймаут ошибок (если они не обёрнуты в SDK)
        error_message = str(exc) or "Unknown error"
        error_type = "UNKNOWN"

        # Попытка определить тип по сообщению
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

        Args:
            error: Исключение из moex_iss_sdk.

        Returns:
            ToolErrorModel с соответствующими полями.
        """
        return ToolErrorModel(
            error_type=error.error_type,
            message=error.message,
            details=error.details,
        )

    @classmethod
    def get_error_type_for_exception(cls, exc: Exception) -> str:
        """
        Получить error_type для исключения без создания полной модели.

        Args:
            exc: Исключение.

        Returns:
            Строка с типом ошибки.
        """
        if isinstance(exc, IssSdkError):
            return exc.error_type

        # Специфичные проверки для стандартных исключений
        if isinstance(exc, ValueError):
            return "VALIDATION_ERROR"
        if isinstance(exc, KeyError):
            return "VALIDATION_ERROR"

        # Попытка определить по сообщению
        error_message = str(exc).lower()
        if "timeout" in error_message:
            return "ISS_TIMEOUT"
        if "404" in str(exc) or "not found" in error_message:
            return "INVALID_TICKER"
        if "500" in str(exc) or "502" in str(exc) or "503" in str(exc):
            return "ISS_5XX"

        return "UNKNOWN"


# Пересборка модели для корректной работы с from __future__ import annotations
ToolErrorModel.model_rebuild()


