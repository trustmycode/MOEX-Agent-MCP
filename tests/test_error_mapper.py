"""
Unit-тесты для модуля error_mapper.
"""

import pytest

from moex_iss_sdk.error_mapper import ErrorMapper, ToolErrorModel
from moex_iss_sdk.exceptions import (
    DateRangeTooLargeError,
    InvalidTickerError,
    IssServerError,
    IssTimeoutError,
    TooManyTickersError,
    UnknownIssError,
)


class TestErrorMapper:
    """Тесты для ErrorMapper."""

    def test_map_invalid_ticker_error(self):
        """Маппинг InvalidTickerError."""
        error = InvalidTickerError("Ticker not found", details={"ticker": "INVALID"})
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "INVALID_TICKER"
        assert result.message == "Ticker not found"
        assert result.details == {"ticker": "INVALID"}

    def test_map_date_range_too_large_error(self):
        """Маппинг DateRangeTooLargeError."""
        error = DateRangeTooLargeError("Range too large", details={"days": 1000})
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "DATE_RANGE_TOO_LARGE"
        assert result.message == "Range too large"
        assert result.details == {"days": 1000}

    def test_map_iss_timeout_error(self):
        """Маппинг IssTimeoutError."""
        error = IssTimeoutError("Request timeout", details={"timeout_seconds": 10})
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "ISS_TIMEOUT"
        assert result.message == "Request timeout"
        assert result.details == {"timeout_seconds": 10}

    def test_map_iss_server_error(self):
        """Маппинг IssServerError."""
        error = IssServerError("Server error", status_code=500, details={"status": 500})
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "ISS_5XX"
        assert result.message == "Server error"
        assert result.details == {"status": 500}

    def test_map_unknown_iss_error(self):
        """Маппинг UnknownIssError."""
        error = UnknownIssError("Unknown error", details={"raw": "data"})
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "UNKNOWN"
        assert result.message == "Unknown error"
        assert result.details == {"raw": "data"}

    def test_map_too_many_tickers_error(self):
        """Маппинг TooManyTickersError."""
        error = TooManyTickersError("Too many tickers", details={"count": 100})
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "TOO_MANY_TICKERS"
        assert result.message == "Too many tickers"
        assert result.details == {"count": 100}

    def test_map_value_error(self):
        """Маппинг ValueError."""
        error = ValueError("Invalid value")
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "VALIDATION_ERROR"
        assert result.message == "Invalid value"
        assert result.details is not None
        assert result.details["exception_type"] == "ValueError"

    def test_map_key_error(self):
        """Маппинг KeyError."""
        error = KeyError("missing_key")
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "VALIDATION_ERROR"
        assert "missing_key" in result.message
        assert result.details is not None
        assert result.details["exception_type"] == "KeyError"

    def test_map_timeout_by_message(self):
        """Определение timeout по сообщению."""
        error = Exception("Connection timeout after 10 seconds")
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "ISS_TIMEOUT"
        assert "timeout" in result.message.lower()

    def test_map_404_by_message(self):
        """Определение 404 по сообщению."""
        error = Exception("404 Not Found")
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "INVALID_TICKER"

    def test_map_500_by_message(self):
        """Определение 500 по сообщению."""
        error = Exception("500 Internal Server Error")
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "ISS_5XX"

    def test_map_unknown_exception(self):
        """Маппинг неизвестного исключения."""
        error = Exception("Some random error")
        result = ErrorMapper.map_exception(error)
        assert result.error_type == "UNKNOWN"
        assert result.message == "Some random error"
        assert result.details is not None
        assert result.details["exception_type"] == "Exception"

    def test_map_iss_sdk_error_explicit(self):
        """Явный маппинг через map_iss_sdk_error."""
        error = InvalidTickerError("Ticker not found", details={"ticker": "INVALID"})
        result = ErrorMapper.map_iss_sdk_error(error)
        assert result.error_type == "INVALID_TICKER"
        assert result.message == "Ticker not found"
        assert result.details == {"ticker": "INVALID"}

    def test_get_error_type_for_exception(self):
        """Получение типа ошибки без создания полной модели."""
        error = InvalidTickerError("Ticker not found")
        assert ErrorMapper.get_error_type_for_exception(error) == "INVALID_TICKER"

        error = ValueError("Invalid")
        assert ErrorMapper.get_error_type_for_exception(error) == "VALIDATION_ERROR"

        error = Exception("Timeout occurred")
        assert ErrorMapper.get_error_type_for_exception(error) == "ISS_TIMEOUT"


class TestToolErrorModel:
    """Тесты для ToolErrorModel."""

    def test_create_error_model(self):
        """Создание модели ошибки."""
        error = ToolErrorModel(
            error_type="INVALID_TICKER",
            message="Ticker not found",
            details={"ticker": "INVALID"},
        )
        assert error.error_type == "INVALID_TICKER"
        assert error.message == "Ticker not found"
        assert error.details == {"ticker": "INVALID"}

    def test_error_model_without_details(self):
        """Создание модели ошибки без details."""
        error = ToolErrorModel(
            error_type="UNKNOWN",
            message="Some error",
        )
        assert error.error_type == "UNKNOWN"
        assert error.message == "Some error"
        assert error.details is None

    def test_error_model_json_serialization(self):
        """Проверка JSON-сериализации."""
        error = ToolErrorModel(
            error_type="INVALID_TICKER",
            message="Ticker not found",
            details={"ticker": "INVALID"},
        )
        json_data = error.model_dump(mode="json")
        assert json_data["error_type"] == "INVALID_TICKER"
        assert json_data["message"] == "Ticker not found"
        assert json_data["details"] == {"ticker": "INVALID"}


