"""
AgentContext — разделяемый контекст выполнения запроса в мультиагентной системе.

Передаётся между агентами для обмена данными, хранения промежуточных результатов
и накопления ошибок в процессе выполнения сценария.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentContext(BaseModel):
    """
    Разделяемый контекст выполнения запроса.

    Передаётся между OrchestratorAgent и Subagents для обмена данными,
    хранения промежуточных результатов и накопления ошибок.

    Attributes:
        user_query: Исходный запрос пользователя на естественном языке.
        session_id: Уникальный идентификатор сессии (для трейсинга и логирования).
        user_role: Роль пользователя (CFO, risk_manager, analyst и т.п.).
        scenario_type: Тип сценария, определённый планировщиком (portfolio_risk, issuer_peers, cfo_liquidity и т.п.).
        intermediate_results: Словарь для обмена данными между сабагентами.
        errors: Список ошибок, накопленных в процессе выполнения.
        metadata: Дополнительные метаданные (locale, request_id, telemetry_span_id и т.п.).
    """

    user_query: str = Field(
        ...,
        description="Исходный запрос пользователя на естественном языке",
        min_length=1,
    )

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Уникальный идентификатор сессии (для трейсинга и логирования)",
    )

    user_role: Optional[str] = Field(
        default=None,
        description="Роль пользователя: CFO, risk_manager, analyst, investor",
        examples=["CFO", "risk_manager", "analyst", "investor"],
    )

    scenario_type: Optional[str] = Field(
        default=None,
        description="Тип сценария, определённый планировщиком",
        examples=[
            "single_security_overview",
            "compare_securities",
            "portfolio_risk_basic",
            "issuer_peers_compare",
            "cfo_liquidity_report",
            "index_risk_scan",
        ],
    )

    intermediate_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Словарь для обмена данными между сабагентами",
    )

    errors: list[str] = Field(
        default_factory=list,
        description="Список ошибок, накопленных в процессе выполнения",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные (locale, request_id, telemetry и т.п.)",
    )

    # Внутренние поля для отслеживания времени выполнения
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время создания контекста",
    )

    def add_result(self, key: str, value: Any) -> None:
        """
        Добавить промежуточный результат от сабагента.

        Args:
            key: Ключ результата (обычно имя сабагента или шага).
            value: Данные для сохранения.
        """
        self.intermediate_results[key] = value

    def get_result(self, key: str, default: Any = None) -> Any:
        """
        Получить промежуточный результат по ключу.

        Args:
            key: Ключ результата.
            default: Значение по умолчанию, если ключ не найден.

        Returns:
            Сохранённые данные или default.
        """
        return self.intermediate_results.get(key, default)

    def add_error(self, error: str) -> None:
        """
        Добавить ошибку в список.

        Args:
            error: Текстовое описание ошибки.
        """
        self.errors.append(error)

    def has_errors(self) -> bool:
        """Проверить, есть ли накопленные ошибки."""
        return len(self.errors) > 0

    def set_metadata(self, key: str, value: Any) -> None:
        """
        Установить значение метаданных.

        Args:
            key: Ключ метаданных.
            value: Значение.
        """
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Получить значение метаданных по ключу.

        Args:
            key: Ключ метаданных.
            default: Значение по умолчанию.

        Returns:
            Значение или default.
        """
        return self.metadata.get(key, default)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_query": "Оцени риск портфеля из SBER, GAZP, LKOH",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_role": "CFO",
                "scenario_type": "portfolio_risk_basic",
                "intermediate_results": {},
                "errors": [],
                "metadata": {"locale": "ru", "client_version": "1.0.0"},
            }
        }
    )

