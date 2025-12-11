"""
Тесты для AgentContext — разделяемого контекста выполнения.
"""

import pytest
from pydantic import ValidationError

from agent_service.core import AgentContext


class TestAgentContextCreation:
    """Тесты создания AgentContext."""

    def test_minimal_context(self):
        """Создание контекста с минимальными параметрами."""
        ctx = AgentContext(user_query="Оцени риск портфеля")
        
        assert ctx.user_query == "Оцени риск портфеля"
        assert ctx.session_id  # Автоматически генерируется
        assert ctx.user_role is None
        assert ctx.scenario_type is None
        assert ctx.intermediate_results == {}
        assert ctx.errors == []
        assert ctx.metadata == {}

    def test_full_context(self):
        """Создание контекста со всеми параметрами."""
        ctx = AgentContext(
            user_query="Сравни SBER и GAZP",
            session_id="test-session-123",
            user_role="CFO",
            scenario_type="compare_securities",
            intermediate_results={"key": "value"},
            errors=["warning1"],
            metadata={"locale": "ru"},
        )
        
        assert ctx.user_query == "Сравни SBER и GAZP"
        assert ctx.session_id == "test-session-123"
        assert ctx.user_role == "CFO"
        assert ctx.scenario_type == "compare_securities"
        assert ctx.intermediate_results == {"key": "value"}
        assert ctx.errors == ["warning1"]
        assert ctx.metadata == {"locale": "ru"}

    def test_empty_query_raises(self):
        """Пустой user_query вызывает ошибку валидации."""
        with pytest.raises(ValidationError):
            AgentContext(user_query="")

    def test_session_id_auto_generated(self):
        """session_id автоматически генерируется UUID."""
        ctx1 = AgentContext(user_query="test1")
        ctx2 = AgentContext(user_query="test2")
        
        # Разные контексты имеют разные session_id
        assert ctx1.session_id != ctx2.session_id
        # UUID формат (36 символов с дефисами)
        assert len(ctx1.session_id) == 36

    def test_created_at_auto_set(self):
        """created_at автоматически устанавливается."""
        ctx = AgentContext(user_query="test")
        
        assert ctx.created_at is not None


class TestAgentContextMethods:
    """Тесты методов AgentContext."""

    def test_add_result(self):
        """Добавление промежуточного результата."""
        ctx = AgentContext(user_query="test")
        
        ctx.add_result("market_data", {"SBER": 290.5})
        ctx.add_result("risk_metrics", {"volatility": 0.15})
        
        assert ctx.intermediate_results["market_data"] == {"SBER": 290.5}
        assert ctx.intermediate_results["risk_metrics"] == {"volatility": 0.15}

    def test_get_result_existing(self):
        """Получение существующего результата."""
        ctx = AgentContext(
            user_query="test",
            intermediate_results={"key": "value"},
        )
        
        assert ctx.get_result("key") == "value"

    def test_get_result_missing(self):
        """Получение несуществующего результата возвращает default."""
        ctx = AgentContext(user_query="test")
        
        assert ctx.get_result("missing") is None
        assert ctx.get_result("missing", "default") == "default"

    def test_add_error(self):
        """Добавление ошибки."""
        ctx = AgentContext(user_query="test")
        
        ctx.add_error("MCP timeout")
        ctx.add_error("Data validation failed")
        
        assert len(ctx.errors) == 2
        assert "MCP timeout" in ctx.errors
        assert "Data validation failed" in ctx.errors

    def test_has_errors(self):
        """Проверка наличия ошибок."""
        ctx = AgentContext(user_query="test")
        
        assert ctx.has_errors() is False
        
        ctx.add_error("error1")
        assert ctx.has_errors() is True

    def test_metadata_operations(self):
        """Операции с метаданными."""
        ctx = AgentContext(user_query="test")
        
        ctx.set_metadata("locale", "ru")
        ctx.set_metadata("version", "1.0")
        
        assert ctx.get_metadata("locale") == "ru"
        assert ctx.get_metadata("version") == "1.0"
        assert ctx.get_metadata("missing") is None
        assert ctx.get_metadata("missing", "default") == "default"


class TestAgentContextSerialization:
    """Тесты сериализации AgentContext."""

    def test_to_dict(self):
        """Сериализация в словарь."""
        ctx = AgentContext(
            user_query="test",
            session_id="session-123",
            user_role="analyst",
        )
        
        data = ctx.model_dump()
        
        assert data["user_query"] == "test"
        assert data["session_id"] == "session-123"
        assert data["user_role"] == "analyst"

    def test_to_json(self):
        """Сериализация в JSON."""
        ctx = AgentContext(
            user_query="test",
            session_id="session-123",
        )
        
        json_str = ctx.model_dump_json()
        
        assert '"user_query":"test"' in json_str
        assert '"session_id":"session-123"' in json_str

    def test_from_dict(self):
        """Десериализация из словаря."""
        data = {
            "user_query": "test query",
            "session_id": "sid-456",
            "user_role": "CFO",
        }
        
        ctx = AgentContext(**data)
        
        assert ctx.user_query == "test query"
        assert ctx.session_id == "sid-456"
        assert ctx.user_role == "CFO"
