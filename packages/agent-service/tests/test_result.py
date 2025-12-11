"""
Тесты для SubagentResult — стандартизированного ответа сабагента.
"""

import pytest
from pydantic import ValidationError

from agent_service.core import SubagentResult


class TestSubagentResultCreation:
    """Тесты создания SubagentResult."""

    def test_success_status(self):
        """Создание результата со статусом success."""
        result = SubagentResult(
            status="success",
            data={"portfolio_risk": 0.15},
        )
        
        assert result.status == "success"
        assert result.data == {"portfolio_risk": 0.15}
        assert result.error_message is None
        assert result.next_agent_hint is None

    def test_error_status(self):
        """Создание результата со статусом error."""
        result = SubagentResult(
            status="error",
            error_message="MCP timeout",
        )
        
        assert result.status == "error"
        assert result.data is None
        assert result.error_message == "MCP timeout"

    def test_partial_status(self):
        """Создание результата со статусом partial."""
        result = SubagentResult(
            status="partial",
            data={"SBER": 290.5},
            error_message="GAZP data unavailable",
            next_agent_hint="dashboard",
        )
        
        assert result.status == "partial"
        assert result.data == {"SBER": 290.5}
        assert result.error_message == "GAZP data unavailable"
        assert result.next_agent_hint == "dashboard"

    def test_invalid_status_raises(self):
        """Невалидный статус вызывает ошибку."""
        with pytest.raises(ValidationError):
            SubagentResult(status="invalid")


class TestSubagentResultFactoryMethods:
    """Тесты фабричных методов SubagentResult."""

    def test_success_factory(self):
        """Фабричный метод success()."""
        result = SubagentResult.success(
            data={"key": "value"},
            next_agent_hint="explainer",
        )
        
        assert result.status == "success"
        assert result.data == {"key": "value"}
        assert result.error_message is None
        assert result.next_agent_hint == "explainer"

    def test_success_factory_minimal(self):
        """Фабричный метод success() без параметров."""
        result = SubagentResult.success()
        
        assert result.status == "success"
        assert result.data is None
        assert result.error_message is None

    def test_create_error_factory(self):
        """Фабричный метод create_error()."""
        result = SubagentResult.create_error(error="Connection failed")
        
        assert result.status == "error"
        assert result.error_message == "Connection failed"
        assert result.data is None
        assert result.next_agent_hint is None

    def test_create_error_factory_with_data(self):
        """Фабричный метод create_error() с частичными данными."""
        result = SubagentResult.create_error(
            error="Partial failure",
            data={"cached": True},
        )
        
        assert result.status == "error"
        assert result.error_message == "Partial failure"
        assert result.data == {"cached": True}

    def test_partial_factory(self):
        """Фабричный метод partial()."""
        result = SubagentResult.partial(
            data={"SBER": 290.5},
            error="GAZP not found",
            next_agent_hint="dashboard",
        )
        
        assert result.status == "partial"
        assert result.data == {"SBER": 290.5}
        assert result.error_message == "GAZP not found"
        assert result.next_agent_hint == "dashboard"


class TestSubagentResultProperties:
    """Тесты свойств SubagentResult."""

    def test_is_success(self):
        """Свойство is_success."""
        success = SubagentResult.success()
        error = SubagentResult.create_error("err")
        partial = SubagentResult.partial(data={}, error="partial")
        
        assert success.is_success is True
        assert error.is_success is False
        assert partial.is_success is False

    def test_is_error(self):
        """Свойство is_error."""
        success = SubagentResult.success()
        error = SubagentResult.create_error("err")
        partial = SubagentResult.partial(data={}, error="partial")
        
        assert success.is_error is False
        assert error.is_error is True
        assert partial.is_error is False

    def test_is_partial(self):
        """Свойство is_partial."""
        success = SubagentResult.success()
        error = SubagentResult.create_error("err")
        partial = SubagentResult.partial(data={}, error="partial")
        
        assert success.is_partial is False
        assert error.is_partial is False
        assert partial.is_partial is True

    def test_has_data(self):
        """Свойство has_data."""
        with_data = SubagentResult.success(data={"key": "value"})
        without_data = SubagentResult.success()
        
        assert with_data.has_data is True
        assert without_data.has_data is False


class TestSubagentResultSerialization:
    """Тесты сериализации SubagentResult."""

    def test_to_dict(self):
        """Сериализация в словарь."""
        result = SubagentResult.success(data={"risk": 0.15})
        
        data = result.model_dump()
        
        assert data["status"] == "success"
        assert data["data"] == {"risk": 0.15}

    def test_to_json(self):
        """Сериализация в JSON."""
        result = SubagentResult.create_error("timeout")
        
        json_str = result.model_dump_json()
        
        assert '"status":"error"' in json_str
        assert '"error_message":"timeout"' in json_str

    def test_from_dict(self):
        """Десериализация из словаря."""
        data = {
            "status": "success",
            "data": {"key": "value"},
            "error_message": None,
            "next_agent_hint": "next",
        }
        
        result = SubagentResult(**data)
        
        assert result.status == "success"
        assert result.data == {"key": "value"}
        assert result.next_agent_hint == "next"
