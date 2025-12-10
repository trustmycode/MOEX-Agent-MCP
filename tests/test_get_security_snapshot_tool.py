"""
Интеграционные тесты для инструмента get_security_snapshot.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from moex_iss_mcp.config import McpConfig
from moex_iss_mcp.models import GetSecuritySnapshotInput, GetSecuritySnapshotOutput
from moex_iss_mcp.server import McpServer
from moex_iss_sdk.exceptions import InvalidTickerError, IssTimeoutError
from moex_iss_sdk.models import SecuritySnapshot


class TestGetSecuritySnapshotTool:
    """Тесты для инструмента get_security_snapshot."""

    def test_successful_snapshot(self):
        """Успешный запрос снимка инструмента."""
        # Подготовка мока IssClient
        mock_snapshot = SecuritySnapshot(
            ticker="SBER",
            board="TQBR",
            as_of=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            last_price=300.5,
            price_change_abs=1.5,
            price_change_pct=0.5,
            open_price=299.0,
            high_price=301.0,
            low_price=298.5,
            volume=1000000.0,
            value=300000000.0,
        )

        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_security_snapshot", return_value=mock_snapshot):
            app = server.fastmcp.http_app(transport="streamable-http")

            with TestClient(app) as client:
                # Вызов через FastMCP tool (нужно найти правильный endpoint)
                # Для FastMCP с streamable-http обычно используется POST /mcp
                # Но для тестирования можно вызвать функцию напрямую
                result = server.fastmcp._tools["get_security_snapshot"].func(
                    ticker="SBER",
                    board="TQBR",
                )

                # Проверка результата
                assert "metadata" in result
                assert "data" in result
                assert result["error"] is None

                # Проверка metadata
                metadata = result["metadata"]
                assert metadata["source"] == "moex-iss"
                assert metadata["ticker"] == "SBER"
                assert metadata["board"] == "TQBR"
                assert "as_of" in metadata

                # Проверка data
                data = result["data"]
                assert data["last_price"] == 300.5
                assert data["price_change_abs"] == 1.5
                assert data["price_change_pct"] == 0.5
                assert data["open_price"] == 299.0
                assert data["high_price"] == 301.0
                assert data["low_price"] == 298.5
                assert data["volume"] == 1000000.0
                assert data["value"] == 300000000.0

                # Проверка metrics (должна быть внутридневная волатильность)
                assert "metrics" in result
                if result["metrics"]:
                    assert "intraday_volatility_estimate" in result["metrics"]

    def test_invalid_ticker_error(self):
        """Обработка ошибки невалидного тикера."""
        config = McpConfig()
        server = McpServer(config)

        error = InvalidTickerError("Ticker not found", details={"ticker": "INVALID", "board": "TQBR"})

        with patch.object(server.iss_client, "get_security_snapshot", side_effect=error):
            app = server.fastmcp.http_app(transport="streamable-http")

            with TestClient(app) as client:
                result = server.fastmcp._tools["get_security_snapshot"].func(
                    ticker="INVALID",
                    board="TQBR",
                )

                # Проверка ошибки
                assert result["error"] is not None
                assert result["error"]["error_type"] == "INVALID_TICKER"
                assert "Ticker not found" in result["error"]["message"]
                assert result["data"] == {}

    def test_timeout_error(self):
        """Обработка ошибки таймаута."""
        config = McpConfig()
        server = McpServer(config)

        error = IssTimeoutError("Request timeout", details={"timeout_seconds": 10})

        with patch.object(server.iss_client, "get_security_snapshot", side_effect=error):
            app = server.fastmcp.http_app(transport="streamable-http")

            with TestClient(app) as client:
                result = server.fastmcp._tools["get_security_snapshot"].func(
                    ticker="SBER",
                    board="TQBR",
                )

                # Проверка ошибки
                assert result["error"] is not None
                assert result["error"]["error_type"] == "ISS_TIMEOUT"
                assert "timeout" in result["error"]["message"].lower()

    def test_default_board(self):
        """Проверка использования дефолтного борда."""
        mock_snapshot = SecuritySnapshot(
            ticker="SBER",
            board="TQBR",
            as_of=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            last_price=300.5,
            price_change_abs=1.5,
            price_change_pct=0.5,
        )

        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_security_snapshot", return_value=mock_snapshot):
            app = server.fastmcp.http_app(transport="streamable-http")

            with TestClient(app) as client:
                # Вызов без указания борда
                result = server.fastmcp._tools["get_security_snapshot"].func(
                    ticker="SBER",
                    board=None,
                )

                # Проверка, что использован дефолтный борд
                assert result["metadata"]["board"] == "TQBR"

    def test_ticker_validation(self):
        """Проверка валидации тикера через Pydantic."""
        config = McpConfig()
        server = McpServer(config)

        # Пустой тикер должен вызвать ошибку валидации
        with pytest.raises(Exception):  # Может быть ValueError или ValidationError
            result = server.fastmcp._tools["get_security_snapshot"].func(
                ticker="",
                board="TQBR",
            )

    def test_snapshot_without_optional_fields(self):
        """Снимок без опциональных полей (open, high, low, volume, value)."""
        mock_snapshot = SecuritySnapshot(
            ticker="SBER",
            board="TQBR",
            as_of=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            last_price=300.5,
            price_change_abs=1.5,
            price_change_pct=0.5,
            open_price=None,
            high_price=None,
            low_price=None,
            volume=None,
            value=None,
        )

        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_security_snapshot", return_value=mock_snapshot):
            app = server.fastmcp.http_app(transport="streamable-http")

            with TestClient(app) as client:
                result = server.fastmcp._tools["get_security_snapshot"].func(
                    ticker="SBER",
                    board="TQBR",
                )

                # Проверка, что обязательные поля присутствуют
                assert result["data"]["last_price"] == 300.5
                assert result["data"]["price_change_abs"] == 1.5
                assert result["data"]["price_change_pct"] == 0.5

                # Опциональные поля могут отсутствовать
                assert "open_price" not in result["data"]
                assert "high_price" not in result["data"]
                assert "low_price" not in result["data"]
                assert "volume" not in result["data"]
                assert "value" not in result["data"]

                # Метрики могут отсутствовать, если нет данных для расчёта
                # (intraday_volatility требует хотя бы open или high/low)


