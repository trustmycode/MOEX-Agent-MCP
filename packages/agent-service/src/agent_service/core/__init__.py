"""
Core модуль мультиагентной архитектуры agent-service.

Содержит базовые абстракции для всех сабагентов и оркестратора:
- BaseSubagent — абстрактный базовый класс для сабагентов
- AgentContext — разделяемый контекст выполнения запроса
- SubagentResult — стандартизированный ответ сабагента
- SubagentRegistry — реестр всех доступных сабагентов

Пример использования:

    from agent_service.core import (
        AgentContext,
        BaseSubagent,
        SubagentResult,
        SubagentRegistry,
    )

    class MySubagent(BaseSubagent):
        async def execute(self, context: AgentContext) -> SubagentResult:
            # Реализация логики
            return SubagentResult.success(data={"key": "value"})

    registry = SubagentRegistry()
    registry.register(MySubagent(name="my_agent", capabilities=["action"]))
"""

from .base_subagent import BaseSubagent
from .context import AgentContext
from .registry import SubagentRegistry, default_registry, get_registry
from .result import SubagentResult

__all__ = [
    # Основные классы
    "AgentContext",
    "BaseSubagent",
    "SubagentResult",
    "SubagentRegistry",
    # Утилиты для доступа к реестру
    "default_registry",
    "get_registry",
]

