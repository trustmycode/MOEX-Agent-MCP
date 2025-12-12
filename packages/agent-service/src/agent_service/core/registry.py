"""
SubagentRegistry — реестр всех доступных сабагентов.

Централизованное хранилище сабагентов с методами регистрации,
получения и перечисления. Поддерживает динамическое добавление
и удаление сабагентов без изменения кода оркестратора.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import TYPE_CHECKING, Iterator, Optional

if TYPE_CHECKING:
    from .base_subagent import BaseSubagent


logger = logging.getLogger(__name__)


class SubagentRegistry:
    """
    Реестр сабагентов с thread-safe доступом.

    Позволяет динамически регистрировать, получать и перечислять
    сабагенты. Реестр можно использовать как singleton или
    создавать отдельные экземпляры для разных контекстов.

    Attributes:
        _subagents: Словарь зарегистрированных сабагентов (name -> instance).
        _lock: Блокировка для thread-safe операций.

    Example:
        >>> registry = SubagentRegistry()
        >>> registry.register(MarketDataSubagent())
        >>> registry.register(RiskAnalyticsSubagent())
        >>> market = registry.get("market_data")
        >>> available = registry.list_available()
        ['market_data', 'risk_analytics']
    """

    # Singleton instance для глобального реестра (опционально)
    _instance: Optional[SubagentRegistry] = None
    _instance_lock: Lock = Lock()

    def __init__(self) -> None:
        """Инициализация пустого реестра."""
        self._subagents: dict[str, BaseSubagent] = {}
        self._lock = Lock()

    @classmethod
    def get_instance(cls) -> SubagentRegistry:
        """
        Получить singleton-экземпляр реестра.

        Thread-safe метод для получения глобального реестра.

        Returns:
            Единственный экземпляр SubagentRegistry.
        """
        if cls._instance is None:
            with cls._instance_lock:
                # Double-checked locking
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Сбросить singleton-экземпляр (для тестов).

        Warning:
            Использовать только в тестах!
        """
        with cls._instance_lock:
            cls._instance = None

    def register(self, subagent: BaseSubagent) -> None:
        """
        Зарегистрировать сабагент в реестре.

        Args:
            subagent: Экземпляр сабагента для регистрации.

        Raises:
            ValueError: Если сабагент с таким именем уже зарегистрирован.
        """
        with self._lock:
            if subagent.name in self._subagents:
                raise ValueError(
                    f"Subagent '{subagent.name}' is already registered. "
                    "Use unregister() first to replace."
                )
            self._subagents[subagent.name] = subagent
            logger.info(
                "Registered subagent '%s' with capabilities: %s",
                subagent.name,
                subagent.capabilities,
            )

    def unregister(self, name: str) -> Optional[BaseSubagent]:
        """
        Удалить сабагент из реестра.

        Args:
            name: Имя сабагента для удаления.

        Returns:
            Удалённый сабагент или None, если не найден.
        """
        with self._lock:
            subagent = self._subagents.pop(name, None)
            if subagent:
                logger.info("Unregistered subagent '%s'", name)
            return subagent

    def get(self, name: str) -> Optional[BaseSubagent]:
        """
        Получить сабагент по имени.

        Args:
            name: Имя сабагента.

        Returns:
            Экземпляр сабагента или None, если не найден.
        """
        with self._lock:
            return self._subagents.get(name)

    def get_required(self, name: str) -> BaseSubagent:
        """
        Получить сабагент по имени (с проверкой существования).

        Args:
            name: Имя сабагента.

        Returns:
            Экземпляр сабагента.

        Raises:
            KeyError: Если сабагент не найден.
        """
        subagent = self.get(name)
        if subagent is None:
            available = self.list_available()
            raise KeyError(
                f"Subagent '{name}' not found. "
                f"Available subagents: {available}"
            )
        return subagent

    def list_available(self) -> list[str]:
        """
        Получить список имён всех зарегистрированных сабагентов.

        Returns:
            Список имён сабагентов (отсортированный).
        """
        with self._lock:
            return sorted(self._subagents.keys())

    def list_all(self) -> list[BaseSubagent]:
        """
        Получить список всех зарегистрированных сабагентов.

        Returns:
            Список экземпляров сабагентов.
        """
        with self._lock:
            return list(self._subagents.values())

    def find_by_capability(self, capability: str) -> list[BaseSubagent]:
        """
        Найти сабагенты по возможности/операции.

        Args:
            capability: Искомая возможность (например, "get_ohlcv", "compute_risk").

        Returns:
            Список сабагентов, обладающих указанной возможностью.
        """
        with self._lock:
            return [
                subagent
                for subagent in self._subagents.values()
                if capability in subagent.capabilities
            ]

    def clear(self) -> None:
        """Очистить реестр (удалить все сабагенты)."""
        with self._lock:
            count = len(self._subagents)
            self._subagents.clear()
            logger.info("Cleared registry, removed %d subagents", count)

    def __len__(self) -> int:
        """Количество зарегистрированных сабагентов."""
        with self._lock:
            return len(self._subagents)

    def __contains__(self, name: str) -> bool:
        """Проверить, зарегистрирован ли сабагент с данным именем."""
        with self._lock:
            return name in self._subagents

    def __iter__(self) -> Iterator[str]:
        """Итератор по именам сабагентов."""
        with self._lock:
            return iter(list(self._subagents.keys()))

    def __repr__(self) -> str:
        """Строковое представление реестра."""
        with self._lock:
            names = list(self._subagents.keys())
        return f"<SubagentRegistry(subagents={names})>"


# Глобальный реестр для удобства использования
# Альтернативно можно использовать SubagentRegistry.get_instance()
default_registry: SubagentRegistry = SubagentRegistry()


def get_registry() -> SubagentRegistry:
    """
    Получить глобальный реестр сабагентов.

    Это рекомендуемый способ доступа к реестру в приложении.
    Для тестов лучше создавать отдельные экземпляры SubagentRegistry.

    Returns:
        Глобальный экземпляр SubagentRegistry.
    """
    return default_registry

