"""
BaseSubagent — абстрактный базовый класс для всех сабагентов.

Определяет единый интерфейс для всех специализированных сабагентов
в мультиагентной архитектуре moex-market-analyst-agent.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from .context import AgentContext
from .result import SubagentResult

if TYPE_CHECKING:
    # Избегаем циклических импортов при проверке типов
    pass


logger = logging.getLogger(__name__)


class BaseSubagent(ABC):
    """
    Абстрактный базовый класс для всех сабагентов.

    Определяет единый интерфейс выполнения (`execute`) и свойства
    (`name`, `capabilities`), которые должны реализовать все сабагенты.

    Наследники:
        - ResearchPlannerSubagent — планировщик сценария
        - MarketDataSubagent — провайдер рыночных данных (moex-iss-mcp)
        - RiskAnalyticsSubagent — риск-аналитика (risk-analytics-mcp)
        - DashboardSubagent — формирование UI-дашборда
        - ExplainerSubagent — генерация текстового отчёта
        - KnowledgeSubagent — провайдер знаний (kb-rag-mcp)

    Attributes:
        _name: Уникальное имя сабагента.
        _description: Человекочитаемое описание назначения сабагента.
        _capabilities: Список возможностей/операций сабагента.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        capabilities: Optional[list[str]] = None,
    ) -> None:
        """
        Инициализация базового сабагента.

        Args:
            name: Уникальное имя сабагента (используется в registry).
            description: Человекочитаемое описание назначения.
            capabilities: Список возможностей/операций сабагента.
        """
        self._name = name
        self._description = description
        self._capabilities = capabilities or []

    @property
    def name(self) -> str:
        """
        Уникальное имя сабагента.

        Используется для регистрации в SubagentRegistry и
        идентификации в логах/трейсах.
        """
        return self._name

    @property
    def description(self) -> str:
        """Человекочитаемое описание назначения сабагента."""
        return self._description

    @property
    def capabilities(self) -> list[str]:
        """
        Список возможностей/операций сабагента.

        Используется для:
        - Документирования возможностей агента
        - Выбора сабагента планировщиком
        - Автоматической генерации Agent Card
        """
        return self._capabilities.copy()

    @abstractmethod
    async def execute(self, context: AgentContext) -> SubagentResult:
        """
        Выполнить основную логику сабагента.

        Это главный метод, который должны реализовать все сабагенты.
        Получает контекст с данными запроса и возвращает
        стандартизированный результат.

        Args:
            context: AgentContext с данными запроса и промежуточными результатами.

        Returns:
            SubagentResult с результатом выполнения или ошибкой.

        Raises:
            Не должен бросать исключения напрямую — все ошибки
            должны быть обёрнуты в SubagentResult.error().
        """
        pass

    async def safe_execute(self, context: AgentContext) -> SubagentResult:
        """
        Безопасное выполнение с обработкой исключений.

        Обёртка над execute(), которая ловит все исключения
        и преобразует их в SubagentResult.error().

        Args:
            context: AgentContext с данными запроса.

        Returns:
            SubagentResult — всегда возвращает результат, даже при ошибках.
        """
        try:
            logger.info(
                "Executing subagent '%s' for session %s",
                self.name,
                context.session_id,
            )
            result = await self.execute(context)
            logger.info(
                "Subagent '%s' completed with status '%s'",
                self.name,
                result.status,
            )
            return result
        except Exception as e:
            error_msg = f"Subagent '{self.name}' failed: {type(e).__name__}: {e}"
            logger.exception(error_msg)
            return SubagentResult.create_error(error=error_msg)

    def validate_context(self, context: AgentContext) -> Optional[str]:
        """
        Валидация контекста перед выполнением.

        Базовая реализация проверяет наличие user_query.
        Наследники могут переопределить для дополнительных проверок.

        Args:
            context: AgentContext для валидации.

        Returns:
            None если валидация прошла, строка с ошибкой если нет.
        """
        if not context.user_query:
            return "user_query is required"
        return None

    def __repr__(self) -> str:
        """Строковое представление сабагента."""
        return (
            f"<{self.__class__.__name__}("
            f"name={self.name!r}, "
            f"capabilities={self.capabilities!r})>"
        )

    def __str__(self) -> str:
        """Краткое строковое представление."""
        return f"{self.__class__.__name__}({self.name!r})"


