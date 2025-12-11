"""
A2A Models — модели входа и выхода для протокола A2A Evolution AI Agents.

Определяет структуры данных для:
- A2AInput — входящий запрос от пользователя
- A2AOutput — исходящий ответ агента
- Вспомогательные модели (сообщения, debug-информация и т.п.)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class A2AMessage(BaseModel):
    """
    Сообщение в формате A2A.

    Attributes:
        role: Роль отправителя (user, assistant, system).
        content: Текстовое содержимое сообщения.
        name: Опциональное имя отправителя.
    """

    model_config = ConfigDict(extra="allow")

    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Роль отправителя сообщения",
    )

    content: str = Field(
        ...,
        description="Текстовое содержимое сообщения",
    )

    name: Optional[str] = Field(
        default=None,
        description="Опциональное имя отправителя",
    )


class A2AInput(BaseModel):
    """
    Входящий A2A-запрос.

    Структура соответствует спецификации Evolution AI Agents A2A.

    Attributes:
        messages: Массив сообщений (история чата + текущий запрос).
        user_role: Роль пользователя в бизнес-контексте (CFO, risk_manager, analyst).
        session_id: Идентификатор сессии для трейсинга.
        locale: Локаль для ответа (ru, en).
        metadata: Дополнительные метаданные запроса.
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": "Оцени риск портфеля: SBER 40%, GAZP 30%, LKOH 30%",
                    }
                ],
                "user_role": "CFO",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "locale": "ru",
            }
        },
    )

    messages: list[A2AMessage] = Field(
        ...,
        min_length=1,
        description="Массив сообщений (минимум одно)",
    )

    user_role: Optional[str] = Field(
        default=None,
        description="Роль пользователя: CFO, risk_manager, analyst, investor",
        examples=["CFO", "risk_manager", "analyst", "investor"],
    )

    session_id: Optional[str] = Field(
        default=None,
        description="Идентификатор сессии для трейсинга",
    )

    locale: str = Field(
        default="ru",
        description="Локаль для ответа",
        examples=["ru", "en"],
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные метаданные запроса",
    )

    @property
    def last_user_message(self) -> Optional[str]:
        """Получить текст последнего сообщения пользователя."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None

    @property
    def user_query(self) -> str:
        """Получить запрос пользователя (последнее user-сообщение или пустая строка)."""
        return self.last_user_message or ""


class TableData(BaseModel):
    """
    Табличные данные для вывода.

    Attributes:
        id: Идентификатор таблицы.
        title: Заголовок таблицы.
        columns: Список названий колонок.
        rows: Данные таблицы (список списков).
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(
        ...,
        description="Уникальный идентификатор таблицы",
    )

    title: str = Field(
        ...,
        description="Заголовок таблицы",
    )

    columns: list[str] = Field(
        ...,
        description="Названия колонок",
    )

    rows: list[list[Any]] = Field(
        default_factory=list,
        description="Данные таблицы (строки)",
    )


class SubagentTrace(BaseModel):
    """
    Информация о вызове сабагента для debug/трейсинга.

    Attributes:
        name: Имя сабагента.
        status: Статус выполнения.
        duration_ms: Длительность выполнения в миллисекундах.
        error: Текст ошибки (если была).
    """

    name: str
    status: Literal["success", "error", "partial", "skipped"]
    duration_ms: float
    error: Optional[str] = None


class DebugInfo(BaseModel):
    """
    Отладочная информация для вывода.

    Attributes:
        scenario_type: Определённый тип сценария.
        scenario_confidence: Уверенность в определении сценария (0.0-1.0).
        pipeline: Выполненный pipeline (список шагов).
        subagent_traces: Информация о вызовах сабагентов.
        total_duration_ms: Общее время выполнения.
        rag_sources: Источники из RAG (если использовался).
        raw_llm_response: Сырой ответ LLM (опционально).
        plan_source: Источник плана (static/dynamic/fallback).
        planner_reasoning: Краткое объяснение от планировщика.
        raw_planner_response: Сырой ответ планировщика.
    """

    model_config = ConfigDict(extra="allow")

    scenario_type: str = Field(
        ...,
        description="Определённый тип сценария",
    )

    scenario_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Уверенность в определении сценария",
    )

    pipeline: list[str] = Field(
        default_factory=list,
        description="Выполненный pipeline (имена шагов)",
    )

    subagent_traces: list[SubagentTrace] = Field(
        default_factory=list,
        description="Трейсы вызовов сабагентов",
    )

    total_duration_ms: Optional[float] = Field(
        default=None,
        description="Общее время выполнения запроса",
    )

    rag_sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Источники из RAG",
    )

    raw_llm_response: Optional[str] = Field(
        default=None,
        description="Сырой ответ LLM (для отладки)",
    )

    plan_source: Optional[Literal["static", "dynamic", "fallback"]] = Field(
        default=None,
        description="Источник плана: статический pipeline или динамический LLM",
    )

    planner_reasoning: Optional[str] = Field(
        default=None,
        description="Краткое объяснение выбора шагов от ResearchPlanner",
    )

    raw_planner_response: Optional[str] = Field(
        default=None,
        description="Сырой ответ ResearchPlannerSubagent",
    )


class A2AOutput(BaseModel):
    """
    Исходящий A2A-ответ агента.

    Структура соответствует спецификации Evolution AI Agents A2A
    с расширениями для Risk Dashboard.

    Attributes:
        text: Текстовый отчёт на русском языке.
        tables: Табличные данные (для UI/отчётов).
        dashboard: Структурированный JSON-дашборд риска (RiskDashboardSpec).
        debug: Отладочная информация.
        status: Статус выполнения запроса.
        error_message: Сообщение об ошибке (если status != "success").
        timestamp: Время формирования ответа.
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "status": "success",
                "text": "Анализ портфеля показал...",
                "tables": [],
                "dashboard": {"metadata": {}, "metrics": [], "charts": [], "tables": [], "alerts": []},
                "timestamp": "2025-12-11T10:00:00Z",
            }
        },
    )

    status: Literal["success", "error", "partial"] = Field(
        default="success",
        description="Статус выполнения запроса",
    )

    text: str = Field(
        ...,
        description="Текстовый отчёт на русском языке",
    )

    tables: list[TableData] = Field(
        default_factory=list,
        description="Табличные данные",
    )

    dashboard: Optional[dict[str, Any]] = Field(
        default=None,
        description="RiskDashboardSpec для UI/AGI UI",
    )

    debug: Optional[DebugInfo] = Field(
        default=None,
        description="Отладочная информация",
    )

    error_message: Optional[str] = Field(
        default=None,
        description="Сообщение об ошибке (если status != 'success')",
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время формирования ответа",
    )

    @classmethod
    def success(
        cls,
        text: str,
        tables: Optional[list[TableData]] = None,
        dashboard: Optional[dict[str, Any]] = None,
        debug: Optional[DebugInfo] = None,
    ) -> A2AOutput:
        """
        Создать успешный ответ.

        Args:
            text: Текстовый отчёт.
            tables: Табличные данные.
            dashboard: RiskDashboardSpec.
            debug: Отладочная информация.

        Returns:
            A2AOutput с status="success".
        """
        return cls(
            status="success",
            text=text,
            tables=tables or [],
            dashboard=dashboard,
            debug=debug,
        )

    @classmethod
    def error(
        cls,
        error_message: str,
        debug: Optional[DebugInfo] = None,
    ) -> A2AOutput:
        """
        Создать ответ с ошибкой.

        Args:
            error_message: Сообщение об ошибке.
            debug: Отладочная информация.

        Returns:
            A2AOutput с status="error".
        """
        return cls(
            status="error",
            text=f"К сожалению, не удалось выполнить запрос: {error_message}",
            tables=[],
            dashboard=None,
            debug=debug,
            error_message=error_message,
        )

    @classmethod
    def partial(
        cls,
        text: str,
        error_message: str,
        tables: Optional[list[TableData]] = None,
        dashboard: Optional[dict[str, Any]] = None,
        debug: Optional[DebugInfo] = None,
    ) -> A2AOutput:
        """
        Создать частичный ответ (есть данные, но с ограничениями).

        Args:
            text: Текстовый отчёт с имеющимися данными.
            error_message: Описание ограничений.
            tables: Табличные данные.
            dashboard: RiskDashboardSpec.
            debug: Отладочная информация.

        Returns:
            A2AOutput с status="partial".
        """
        return cls(
            status="partial",
            text=text,
            tables=tables or [],
            dashboard=dashboard,
            debug=debug,
            error_message=error_message,
        )
