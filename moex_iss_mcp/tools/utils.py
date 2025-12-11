"""
Утилиты для MCP-инструментов.

Содержит ToolResult для стандартизированного возврата результатов
и вспомогательные функции для валидации и обработки ошибок.
"""

import os
from typing import Any, Dict, List, Optional

from fastmcp.tools.tool import ToolResult as FastmcpToolResult
from mcp.shared.exceptions import ErrorData, McpError
from mcp.types import TextContent


class ToolResult(FastmcpToolResult):
    """
    Стандартизированный результат выполнения MCP-инструмента.

    Наследуется от fastmcp.tools.tool.ToolResult, чтобы FastMCP
    корректно сериализовал structured_content без лишних обёрток.
    """

    def __init__(
        self,
        *,
        content: Optional[List[TextContent]] = None,
        structured_content: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(content=content, structured_content=structured_content, meta=meta or {})

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        text_content: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        """
        Создать ToolResult из словаря (для совместимости с текущим форматом).

        Преобразует формат {metadata, data, error} в ToolResult.

        Args:
            data: Словарь с результатом (может содержать metadata, data, error)
            text_content: Опциональный текстовый контент для content
            meta: Дополнительные метаданные

        Returns:
            ToolResult: Результат в стандартном формате
        """
        # Извлекаем данные из текущего формата
        metadata = data.get("metadata", {})
        result_data = data.get("data")
        error = data.get("error")

        if result_data is None:
            extra_fields = {k: v for k, v in data.items() if k not in {"metadata", "data", "error"}}
            if extra_fields:
                result_data = extra_fields

        # Формируем structured_content с сохранением текущего формата
        structured_content: Dict[str, Any] = {
            "metadata": metadata,
            "data": result_data,
            "error": error,  # Явно включаем ключ error (может быть None)
        }
        if "metrics" in data:
            structured_content["metrics"] = data.get("metrics")

        # Формируем текстовый контент
        if text_content:
            text = text_content
        elif error:
            error_msg = error.get("message", "Unknown error")
            error_type = error.get("error_type", "UNKNOWN")
            text = f"❌ Ошибка ({error_type}): {error_msg}"
        elif result_data:
            text = "✅ Операция выполнена успешно"
        else:
            text = "Операция завершена"

        # Объединяем метаданные
        result_meta = {**(meta or {}), **metadata}

        return cls(
            content=[TextContent(type="text", text=text)],
            structured_content=structured_content,
            meta=result_meta,
        )

    @classmethod
    def success(
        cls,
        *,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        text: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        """
        Создать успешный ToolResult.

        Args:
            data: Данные результата
            metadata: Метаданные операции
            text: Текстовое описание результата
            meta: Дополнительные метаданные

        Returns:
            ToolResult: Успешный результат
        """
        structured_content: Dict[str, Any] = {
            "metadata": metadata or {},
            "data": data,
            "error": None,
        }

        text_content = text or "✅ Операция выполнена успешно"

        result_meta = {**(meta or {}), **(metadata or {})}

        return cls(
            content=[TextContent(type="text", text=text_content)],
            structured_content=structured_content,
            meta=result_meta,
        )

    @classmethod
    def error(
        cls,
        *,
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ToolResult":
        """
        Создать ToolResult с ошибкой.

        Args:
            error_type: Тип ошибки
            message: Сообщение об ошибке
            details: Дополнительные детали ошибки
            metadata: Метаданные операции
            meta: Дополнительные метаданные

        Returns:
            ToolResult: Результат с ошибкой
        """
        error_data = {
            "error_type": error_type,
            "message": message,
            "details": details or {},
        }

        structured_content: Dict[str, Any] = {
            "metadata": metadata or {},
            "data": None,
            "error": error_data,
        }

        text_content = f"❌ Ошибка ({error_type}): {message}"

        result_meta = {**(meta or {}), **(metadata or {})}

        return cls(
            content=[TextContent(type="text", text=text_content)],
            structured_content=structured_content,
            meta=result_meta,
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
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise McpError(
            ErrorData(
                code=-32602,  # Invalid params
                message=f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}",
            )
        )
    return {n: os.getenv(n, "") for n in names}


def format_api_error(response_text: str, status_code: int) -> str:
    """
    Форматирует ошибку API в понятное сообщение.

    Args:
        response_text: Текст ответа от API
        status_code: HTTP статус код

    Returns:
        Отформатированное сообщение об ошибке
    """
    import json

    try:
        error_data = json.loads(response_text)
        code = error_data.get("code", "unknown")
        message = error_data.get("message", response_text)

        error_msg = f"Ошибка API (код {code}): {message}"

        # Специальная обработка для разных статус кодов
        if status_code == 401:
            error_msg = (
                "Ошибка аутентификации.\n\n"
                "Что можно сделать:\n"
                "- Проверьте учетные данные\n"
                f"Детали: {message}"
            )

        return error_msg
    except json.JSONDecodeError:
        return f"Ошибка API (статус {status_code}): {response_text}"
