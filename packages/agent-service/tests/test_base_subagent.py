"""
Тесты для BaseSubagent — абстрактного базового класса сабагентов.
"""

import asyncio

import pytest

from agent_service.core import AgentContext, BaseSubagent, SubagentResult


class MockSubagent(BaseSubagent):
    """Тестовая реализация BaseSubagent."""

    def __init__(
        self,
        name: str = "mock_agent",
        description: str = "Mock agent for testing",
        capabilities: list[str] | None = None,
        should_fail: bool = False,
        fail_with_exception: bool = False,
    ):
        super().__init__(name, description, capabilities or ["mock_action"])
        self.should_fail = should_fail
        self.fail_with_exception = fail_with_exception
        self.execute_called = False
        self.last_context: AgentContext | None = None

    async def execute(self, context: AgentContext) -> SubagentResult:
        self.execute_called = True
        self.last_context = context
        
        if self.fail_with_exception:
            raise RuntimeError("Intentional test error")
        
        if self.should_fail:
            return SubagentResult.create_error(error="Mock error")
        
        return SubagentResult.success(
            data={"mock_result": True},
            next_agent_hint="next_agent",
        )


class TestBaseSubagentProperties:
    """Тесты свойств BaseSubagent."""

    def test_name_property(self):
        """Свойство name возвращает имя агента."""
        agent = MockSubagent(name="test_agent")
        assert agent.name == "test_agent"

    def test_description_property(self):
        """Свойство description возвращает описание."""
        agent = MockSubagent(description="Test description")
        assert agent.description == "Test description"

    def test_capabilities_property(self):
        """Свойство capabilities возвращает копию списка."""
        agent = MockSubagent(capabilities=["action1", "action2"])
        
        caps = agent.capabilities
        assert caps == ["action1", "action2"]
        
        # Проверяем, что возвращается копия
        caps.append("action3")
        assert agent.capabilities == ["action1", "action2"]

    def test_default_capabilities(self):
        """По умолчанию capabilities пустой список."""
        agent = MockSubagent(capabilities=None)
        # В MockSubagent по умолчанию ["mock_action"]
        assert agent.capabilities == ["mock_action"]


class TestBaseSubagentExecute:
    """Тесты метода execute."""

    def test_execute_success(self):
        """Успешное выполнение execute."""
        agent = MockSubagent()
        ctx = AgentContext(user_query="test query")
        
        result = asyncio.get_event_loop().run_until_complete(agent.execute(ctx))
        
        assert agent.execute_called is True
        assert agent.last_context is ctx
        assert result.is_success
        assert result.data == {"mock_result": True}
        assert result.next_agent_hint == "next_agent"

    def test_execute_failure(self):
        """Выполнение execute с ошибкой."""
        agent = MockSubagent(should_fail=True)
        ctx = AgentContext(user_query="test query")
        
        result = asyncio.get_event_loop().run_until_complete(agent.execute(ctx))
        
        assert result.is_error
        assert result.error_message == "Mock error"


class TestBaseSubagentSafeExecute:
    """Тесты метода safe_execute."""

    def test_safe_execute_success(self):
        """safe_execute при успешном выполнении."""
        agent = MockSubagent()
        ctx = AgentContext(user_query="test query")
        
        result = asyncio.get_event_loop().run_until_complete(agent.safe_execute(ctx))
        
        assert result.is_success
        assert result.data == {"mock_result": True}

    def test_safe_execute_catches_exception(self):
        """safe_execute перехватывает исключения."""
        agent = MockSubagent(fail_with_exception=True)
        ctx = AgentContext(user_query="test query")
        
        result = asyncio.get_event_loop().run_until_complete(agent.safe_execute(ctx))
        
        assert result.is_error
        assert "mock_agent" in result.error_message
        assert "RuntimeError" in result.error_message
        assert "Intentional test error" in result.error_message


class TestBaseSubagentValidation:
    """Тесты валидации контекста."""

    def test_validate_context_valid(self):
        """Валидация корректного контекста."""
        agent = MockSubagent()
        ctx = AgentContext(user_query="test query")
        
        error = agent.validate_context(ctx)
        
        assert error is None

    def test_validate_context_empty_query(self):
        """Валидация с пустым user_query через Pydantic не пройдёт,
        но если бы прошла — validate_context вернул бы ошибку.
        """
        agent = MockSubagent()
        # Создаём контекст с валидным query, потом меняем
        ctx = AgentContext(user_query="test")
        ctx.user_query = ""  # Эмулируем пустой query
        
        error = agent.validate_context(ctx)
        
        assert error == "user_query is required"


class TestBaseSubagentRepr:
    """Тесты строкового представления."""

    def test_repr(self):
        """__repr__ возвращает информативную строку."""
        agent = MockSubagent(
            name="test_agent",
            capabilities=["action1", "action2"],
        )
        
        repr_str = repr(agent)
        
        assert "MockSubagent" in repr_str
        assert "test_agent" in repr_str
        assert "action1" in repr_str
        assert "action2" in repr_str

    def test_str(self):
        """__str__ возвращает краткую строку."""
        agent = MockSubagent(name="test_agent")
        
        str_repr = str(agent)
        
        assert "MockSubagent" in str_repr
        assert "test_agent" in str_repr


