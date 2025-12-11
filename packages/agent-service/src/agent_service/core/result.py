"""
SubagentResult — стандартизированный ответ сабагента.

Унифицирует формат результата выполнения для всех сабагентов,
обеспечивая предсказуемую обработку результатов оркестратором.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SubagentResult(BaseModel):
    """
    Стандартизированный результат выполнения сабагента.

    Все сабагенты возвращают этот тип, что позволяет оркестратору
    единообразно обрабатывать результаты и ошибки.

    Attributes:
        status: Статус выполнения:
            - "success" — выполнено успешно, данные доступны в data.
            - "error" — критическая ошибка, данные недоступны.
            - "partial" — частичное выполнение, часть данных доступна, но есть проблемы.
        data: Результирующие данные (опционально, зависит от сабагента).
        error_message: Описание ошибки (если status != "success").
        next_agent_hint: Подсказка для оркестратора — какого сабагента вызвать следующим.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "success",
                    "data": {"portfolio_risk": 0.15, "sharpe_ratio": 1.2},
                    "error_message": None,
                    "next_agent_hint": "explainer",
                },
                {
                    "status": "error",
                    "data": None,
                    "error_message": "MCP timeout: moex-iss-mcp не отвечает",
                    "next_agent_hint": None,
                },
                {
                    "status": "partial",
                    "data": {"SBER": {"price": 290.5}},
                    "error_message": "Данные по GAZP недоступны",
                    "next_agent_hint": "dashboard",
                },
            ]
        }
    )

    status: Literal["success", "error", "partial"] = Field(
        ...,
        description="Статус выполнения сабагента",
    )

    data: Optional[Any] = Field(
        default=None,
        description="Результирующие данные (структура зависит от сабагента)",
    )

    error_message: Optional[str] = Field(
        default=None,
        description="Описание ошибки (если status != 'success')",
    )

    next_agent_hint: Optional[str] = Field(
        default=None,
        description="Подсказка для оркестратора — имя следующего сабагента",
        examples=["market_data", "risk_analytics", "explainer", "dashboard"],
    )

    @classmethod
    def success(
        cls,
        data: Any = None,
        next_agent_hint: Optional[str] = None,
    ) -> SubagentResult:
        """
        Создать успешный результат.

        Args:
            data: Результирующие данные.
            next_agent_hint: Подсказка для следующего шага.

        Returns:
            SubagentResult с status="success".
        """
        return cls(
            status="success",
            data=data,
            error_message=None,
            next_agent_hint=next_agent_hint,
        )

    @classmethod
    def create_error(
        cls,
        error: str,
        data: Any = None,
    ) -> SubagentResult:
        """
        Создать результат с ошибкой.

        Args:
            error: Описание ошибки.
            data: Частичные данные (опционально).

        Returns:
            SubagentResult с status="error".
        """
        return cls(
            status="error",
            data=data,
            error_message=error,
            next_agent_hint=None,
        )

    @classmethod
    def partial(
        cls,
        data: Any,
        error: str,
        next_agent_hint: Optional[str] = None,
    ) -> SubagentResult:
        """
        Создать частичный результат (есть данные, но с проблемами).

        Args:
            data: Частичные данные.
            error: Описание проблемы.
            next_agent_hint: Подсказка для следующего шага.

        Returns:
            SubagentResult с status="partial".
        """
        return cls(
            status="partial",
            data=data,
            error_message=error,
            next_agent_hint=next_agent_hint,
        )

    @property
    def is_success(self) -> bool:
        """Проверить, успешно ли выполнение."""
        return self.status == "success"

    @property
    def is_error(self) -> bool:
        """Проверить, произошла ли ошибка."""
        return self.status == "error"

    @property
    def is_partial(self) -> bool:
        """Проверить, является ли результат частичным."""
        return self.status == "partial"

    @property
    def has_data(self) -> bool:
        """Проверить, есть ли данные в результате."""
        return self.data is not None
