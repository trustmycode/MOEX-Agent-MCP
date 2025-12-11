"""
Интеграционные тесты для инструмента get_ohlcv_timeseries.
"""

import importlib
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import anyio
import pytest
from starlette.testclient import TestClient

from moex_iss_mcp.config import McpConfig
from moex_iss_mcp.server import McpServer
from moex_iss_sdk.exceptions import DateRangeTooLargeError, InvalidTickerError
from moex_iss_sdk.models import OhlcvBar


class TestGetOhlcvTimeseriesTool:
    """Тесты для get_ohlcv_timeseries."""

    def _call_tool(self, server: McpConfig, **kwargs):
        tool = server.fastmcp._tool_manager._tools["get_ohlcv_timeseries"]
        result = anyio.run(lambda: tool.fn(**kwargs))
        return getattr(result, "structured_content", result)

    def test_successful_timeseries(self):
        """Успешный запрос OHLCV-данных за 90 дней."""
        bars = [
            OhlcvBar(
                ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
                open=100.0,
                high=110.0,
                low=95.0,
                close=100.0,
                volume=1200.0,
                value=150000.0,
            ),
            OhlcvBar(
                ts=datetime(2024, 2, 15, tzinfo=timezone.utc),
                open=101.0,
                high=112.0,
                low=100.0,
                close=110.0,
                volume=1800.0,
                value=200000.0,
            ),
            OhlcvBar(
                ts=datetime(2024, 3, 31, tzinfo=timezone.utc),
                open=112.0,
                high=125.0,
                low=110.0,
                close=120.0,
                volume=2400.0,
                value=260000.0,
            ),
        ]

        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_ohlcv_series", return_value=bars):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(
                    server,
                    ticker="SBER",
                    board="TQBR",
                    from_date="2024-01-01",
                    to_date="2024-03-31",
                    interval="1d",
                )

                assert result["error"] is None
                metadata = result["metadata"]
                assert metadata["ticker"] == "SBER"
                assert metadata["board"] == "TQBR"
                assert metadata["interval"] == "1d"
                assert metadata["from_date"] == "2024-01-01"
                assert metadata["to_date"] == "2024-03-31"

                assert len(result["data"]) == 3
                assert result["data"][0]["ts"].startswith("2024-01-01")
                assert result["data"][2]["close"] == 120.0

                metrics = result["metrics"]
                assert metrics is not None
                assert metrics["total_return_pct"] == 20.0
                assert metrics["avg_daily_volume"] == 1800.0
                assert metrics["annualized_volatility"] is not None
                assert metrics["annualized_volatility"] >= 0

    def test_autofill_default_dates(self, monkeypatch):
        """Даты по умолчанию: to=today, from=today-365."""
        fixed_now = datetime(2024, 4, 1, tzinfo=timezone.utc)
        tool_module = importlib.import_module("moex_iss_mcp.tools.get_ohlcv_timeseries")
        monkeypatch.setattr(tool_module, "utc_now", lambda: fixed_now)

        captured = {}

        def _mock_get(ticker, board, from_date, to_date, interval):
            captured["args"] = (ticker, board, from_date, to_date, interval)
            return []

        config = McpConfig()
        server = McpServer(config)
        monkeypatch.setattr(server.iss_client, "get_ohlcv_series", _mock_get)

        app = server.fastmcp.http_app(transport="streamable-http")
        with TestClient(app):
            result = self._call_tool(server, ticker="SBER")

        assert captured["args"][0] == "SBER"
        assert captured["args"][2] == date(2023, 4, 2)  # 2024-04-01 минус 365 дней
        assert captured["args"][3] == date(2024, 4, 1)
        assert result["metadata"]["from_date"] == "2023-04-02"
        assert result["metadata"]["to_date"] == "2024-04-01"
        assert result["data"] == []
        assert result["metrics"] is None

    def test_default_board_used(self):
        """Если board не передан, используется дефолт из настроек IssClient."""
        bar = OhlcvBar(
            ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=1,
            high=1,
            low=1,
            close=1,
        )
        config = McpConfig()
        server = McpServer(config)
        server.iss_client.settings.default_board = "ZZZ"

        with patch.object(
            server.iss_client,
            "get_ohlcv_series",
            side_effect=lambda ticker, board, from_date, to_date, interval: (
                (bar,) if board == "ZZZ" else pytest.fail("Unexpected board")
            ),
        ):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(server, ticker="SBER", board=None)

                assert result["metadata"]["board"] == "ZZZ"

    def test_invalid_interval_raises(self):
        """Неподдерживаемый interval приводит к ошибке валидации."""
        config = McpConfig()
        server = McpServer(config)

        with pytest.raises(Exception):
            self._call_tool(
                server,
                ticker="SBER",
                board="TQBR",
                from_date="2024-01-01",
                to_date="2024-01-10",
                interval="5m",
            )

    def test_empty_bars_produce_empty_metrics(self):
        """Пустой ответ ISS → пустые data и metrics=None."""
        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_ohlcv_series", return_value=[]):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(
                    server,
                    ticker="SBER",
                    board="TQBR",
                    from_date="2024-01-01",
                    to_date="2024-01-10",
                )

                assert result["error"] is None
                assert result["data"] == []
                assert result["metrics"] is None

    def test_invalid_ticker_maps_error(self):
        """InvalidTickerError из IssClient маппится в error_type INVALID_TICKER."""
        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_ohlcv_series", side_effect=InvalidTickerError("bad")):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(
                    server,
                    ticker="BAD",
                    board="TQBR",
                    from_date="2024-01-01",
                    to_date="2024-01-10",
                )

                assert result["error"] is not None
                assert result["error"]["error_type"] == "INVALID_TICKER"
                assert result["data"] == []

    def test_single_bar_metrics_only_avg_volume(self):
        """При одном баре доходность и волатильность отсутствуют, но средний объём считается."""
        bar = OhlcvBar(
            ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=500.0,
        )
        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_ohlcv_series", return_value=[bar]):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(
                    server,
                    ticker="SBER",
                    board="TQBR",
                    from_date="2024-01-01",
                    to_date="2024-01-01",
                )

                metrics = result["metrics"]
                assert metrics is not None
                assert "total_return_pct" not in metrics
                assert "annualized_volatility" not in metrics
                assert metrics["avg_daily_volume"] == 500.0

    def test_max_lookback_boundary_allowed(self):
        """Диапазон ровно MAX_LOOKBACK_DAYS (730) допускается."""
        captured = {}

        def _mock_get(ticker, board, from_date, to_date, interval):
            captured["delta"] = (to_date - from_date).days
            return [
                OhlcvBar(
                    ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                )
            ]

        config = McpConfig()
        server = McpServer(config)
        with patch.object(server.iss_client, "get_ohlcv_series", side_effect=_mock_get):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(
                    server,
                    ticker="SBER",
                    board="TQBR",
                    from_date="2022-01-01",
                    to_date="2024-01-01",
                )

                assert captured["delta"] == 730
                assert result["error"] is None

    def test_sorts_bars_before_metrics(self):
        """Бары сортируются по времени перед расчётами и формированием data."""
        bars = [
            OhlcvBar(ts=datetime(2024, 3, 1, tzinfo=timezone.utc), open=2, high=2, low=2, close=2),
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=1, high=1, low=1, close=1),
        ]

        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_ohlcv_series", return_value=bars):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(
                    server,
                    ticker="SBER",
                    board="TQBR",
                    from_date="2024-01-01",
                    to_date="2024-03-10",
                )

                assert result["data"][0]["ts"].startswith("2024-01-01")
                assert result["data"][1]["ts"].startswith("2024-03-01")

    def test_to_date_before_from_date_raises(self):
        """to_date < from_date приводит к ошибке валидации input."""
        config = McpConfig()
        server = McpServer(config)

        with pytest.raises(Exception):
            self._call_tool(
                server,
                ticker="SBER",
                board="TQBR",
                from_date="2024-02-01",
                to_date="2024-01-01",
            )

    def test_date_range_too_large_error(self):
        """Период свыше лимита возвращает DATE_RANGE_TOO_LARGE в error."""
        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_ohlcv_series", side_effect=DateRangeTooLargeError("too wide")):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = self._call_tool(
                    server,
                    ticker="SBER",
                    board="TQBR",
                    from_date="2019-01-01",
                    to_date="2024-01-01",
                    interval="1d",
                )

                assert result["error"] is not None
                assert result["error"]["error_type"] == "DATE_RANGE_TOO_LARGE"
                assert result["data"] == []
