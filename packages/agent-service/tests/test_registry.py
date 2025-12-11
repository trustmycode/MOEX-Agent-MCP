"""
Тесты для SubagentRegistry — реестра сабагентов.
"""

import pytest

from agent_service.core import AgentContext, BaseSubagent, SubagentRegistry, SubagentResult


class MockSubagent(BaseSubagent):
    """Тестовая реализация BaseSubagent."""

    async def execute(self, context: AgentContext) -> SubagentResult:
        return SubagentResult.success(data={"agent": self.name})


@pytest.fixture
def registry():
    """Создаёт новый реестр для каждого теста."""
    return SubagentRegistry()


@pytest.fixture
def mock_agents():
    """Создаёт набор тестовых агентов."""
    return [
        MockSubagent(
            name="market_data",
            description="Market data provider",
            capabilities=["get_ohlcv", "get_snapshot"],
        ),
        MockSubagent(
            name="risk_analytics",
            description="Risk analytics provider",
            capabilities=["compute_risk", "compute_var"],
        ),
        MockSubagent(
            name="explainer",
            description="Report generator",
            capabilities=["generate_text"],
        ),
    ]


class TestSubagentRegistryBasic:
    """Базовые тесты SubagentRegistry."""

    def test_empty_registry(self, registry):
        """Новый реестр пустой."""
        assert len(registry) == 0
        assert registry.list_available() == []

    def test_register_single(self, registry):
        """Регистрация одного сабагента."""
        agent = MockSubagent(name="test_agent")
        
        registry.register(agent)
        
        assert len(registry) == 1
        assert "test_agent" in registry
        assert registry.list_available() == ["test_agent"]

    def test_register_multiple(self, registry, mock_agents):
        """Регистрация нескольких сабагентов."""
        for agent in mock_agents:
            registry.register(agent)
        
        assert len(registry) == 3
        assert registry.list_available() == ["explainer", "market_data", "risk_analytics"]

    def test_register_duplicate_raises(self, registry):
        """Повторная регистрация вызывает ошибку."""
        agent1 = MockSubagent(name="agent")
        agent2 = MockSubagent(name="agent")
        
        registry.register(agent1)
        
        with pytest.raises(ValueError, match="already registered"):
            registry.register(agent2)


class TestSubagentRegistryGet:
    """Тесты получения сабагентов."""

    def test_get_existing(self, registry, mock_agents):
        """Получение существующего сабагента."""
        for agent in mock_agents:
            registry.register(agent)
        
        market = registry.get("market_data")
        
        assert market is not None
        assert market.name == "market_data"

    def test_get_missing(self, registry):
        """Получение несуществующего сабагента возвращает None."""
        result = registry.get("nonexistent")
        
        assert result is None

    def test_get_required_existing(self, registry, mock_agents):
        """get_required для существующего сабагента."""
        for agent in mock_agents:
            registry.register(agent)
        
        market = registry.get_required("market_data")
        
        assert market.name == "market_data"

    def test_get_required_missing(self, registry):
        """get_required для несуществующего сабагента вызывает KeyError."""
        with pytest.raises(KeyError, match="not found"):
            registry.get_required("nonexistent")


class TestSubagentRegistryUnregister:
    """Тесты удаления сабагентов."""

    def test_unregister_existing(self, registry):
        """Удаление существующего сабагента."""
        agent = MockSubagent(name="test")
        registry.register(agent)
        
        removed = registry.unregister("test")
        
        assert removed is agent
        assert "test" not in registry
        assert len(registry) == 0

    def test_unregister_missing(self, registry):
        """Удаление несуществующего сабагента возвращает None."""
        result = registry.unregister("nonexistent")
        
        assert result is None


class TestSubagentRegistrySearch:
    """Тесты поиска сабагентов."""

    def test_find_by_capability(self, registry, mock_agents):
        """Поиск сабагентов по возможности."""
        for agent in mock_agents:
            registry.register(agent)
        
        # Ищем агентов с compute_risk
        found = registry.find_by_capability("compute_risk")
        
        assert len(found) == 1
        assert found[0].name == "risk_analytics"

    def test_find_by_capability_multiple(self, registry):
        """Поиск возвращает несколько агентов с одинаковой возможностью."""
        agent1 = MockSubagent(name="agent1", capabilities=["shared_cap"])
        agent2 = MockSubagent(name="agent2", capabilities=["shared_cap"])
        registry.register(agent1)
        registry.register(agent2)
        
        found = registry.find_by_capability("shared_cap")
        
        assert len(found) == 2

    def test_find_by_capability_none(self, registry, mock_agents):
        """Поиск несуществующей возможности возвращает пустой список."""
        for agent in mock_agents:
            registry.register(agent)
        
        found = registry.find_by_capability("nonexistent_capability")
        
        assert found == []


class TestSubagentRegistryOperations:
    """Тесты дополнительных операций."""

    def test_list_all(self, registry, mock_agents):
        """list_all возвращает все сабагенты."""
        for agent in mock_agents:
            registry.register(agent)
        
        all_agents = registry.list_all()
        
        assert len(all_agents) == 3
        names = {a.name for a in all_agents}
        assert names == {"market_data", "risk_analytics", "explainer"}

    def test_clear(self, registry, mock_agents):
        """clear удаляет все сабагенты."""
        for agent in mock_agents:
            registry.register(agent)
        
        registry.clear()
        
        assert len(registry) == 0
        assert registry.list_available() == []

    def test_contains(self, registry):
        """Оператор in проверяет наличие сабагента."""
        agent = MockSubagent(name="test")
        registry.register(agent)
        
        assert "test" in registry
        assert "missing" not in registry

    def test_iter(self, registry, mock_agents):
        """Итерация по реестру возвращает имена."""
        for agent in mock_agents:
            registry.register(agent)
        
        names = list(registry)
        
        assert set(names) == {"market_data", "risk_analytics", "explainer"}


class TestSubagentRegistrySingleton:
    """Тесты singleton-паттерна."""

    def test_get_instance_returns_same(self):
        """get_instance возвращает один и тот же экземпляр."""
        SubagentRegistry.reset_instance()  # Сбрасываем для чистоты теста
        
        instance1 = SubagentRegistry.get_instance()
        instance2 = SubagentRegistry.get_instance()
        
        assert instance1 is instance2
        
        SubagentRegistry.reset_instance()  # Чистим после теста

    def test_reset_instance(self):
        """reset_instance сбрасывает singleton."""
        instance1 = SubagentRegistry.get_instance()
        SubagentRegistry.reset_instance()
        instance2 = SubagentRegistry.get_instance()
        
        assert instance1 is not instance2
        
        SubagentRegistry.reset_instance()  # Чистим после теста


class TestSubagentRegistryRepr:
    """Тесты строкового представления."""

    def test_repr_empty(self, registry):
        """__repr__ для пустого реестра."""
        repr_str = repr(registry)
        
        assert "SubagentRegistry" in repr_str
        assert "[]" in repr_str

    def test_repr_with_agents(self, registry, mock_agents):
        """__repr__ для реестра с агентами."""
        for agent in mock_agents:
            registry.register(agent)
        
        repr_str = repr(registry)
        
        assert "SubagentRegistry" in repr_str
        assert "market_data" in repr_str
