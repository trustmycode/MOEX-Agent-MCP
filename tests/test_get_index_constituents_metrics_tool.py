"""
Интеграционные тесты для инструмента get_index_constituents_metrics.
"""

from datetime import date
from unittest.mock import patch

import anyio
from starlette.testclient import TestClient

from moex_iss_mcp.config import McpConfig
from moex_iss_mcp.server import McpServer
from moex_iss_mcp.tools.get_index_constituents_metrics import init_tool_dependencies as init_index_tool_dependencies
from moex_iss_sdk.exceptions import InvalidTickerError
from moex_iss_sdk.models import IndexConstituent


def _call_tool(server: McpServer, name: str, **kwargs):
    tool = server.fastmcp._tool_manager._tools[name]
    result = anyio.run(lambda: tool.fn(**kwargs))
    return getattr(result, "structured_content", result)


class TestGetIndexConstituentsMetricsTool:
    """Тесты для get_index_constituents_metrics."""

    def test_successful_index_metrics(self):
        """Успешное получение состава индекса и метрик."""
        members = [
            IndexConstituent(index_ticker="IMOEX", ticker="SBER", weight_pct=25.0, last_price=100.0, price_change_pct=1.2, sector="FIN"),
            IndexConstituent(index_ticker="IMOEX", ticker="GAZP", weight_pct=15.0, last_price=200.0, price_change_pct=-0.5, sector="OG"),
            IndexConstituent(index_ticker="IMOEX", ticker="LKOH", weight_pct=10.0, last_price=300.0, price_change_pct=0.3, sector="OG"),
        ]

        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_index_constituents", return_value=members):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = _call_tool(
                    server,
                    "get_index_constituents_metrics",
                    index_ticker="IMOEX",
                    as_of_date="2024-01-10",
                )

                assert result["error"] is None
                metadata = result["metadata"]
                assert metadata["index_ticker"] == "IMOEX"
                assert metadata["as_of_date"] == "2024-01-10"
                assert len(result["data"]) == 3

                metrics = result["metrics"]
                assert metrics is not None
                assert metrics["num_constituents"] == 3
                assert metrics["top5_weight_pct"] == 50.0

    def test_unknown_index_error(self):
        """Неизвестный индекс возвращает UNKNOWN_INDEX в error."""
        config = McpConfig()
        server = McpServer(config)

        app = server.fastmcp.http_app(transport="streamable-http")
        with TestClient(app):
            result = _call_tool(
                server,
                "get_index_constituents_metrics",
                index_ticker="UNKNOWN",
                as_of_date=date(2024, 1, 10),
            )

            assert result["error"] is not None
            assert result["error"]["error_type"] == "UNKNOWN_INDEX"
            assert result["data"] == []

    def test_top5_weights_and_counts(self):
        """Проверка расчёта top5_weight_pct и num_constituents при >5 бумаг."""
        members = [
            IndexConstituent(index_ticker="IMOEX", ticker="A", weight_pct=30.0),
            IndexConstituent(index_ticker="IMOEX", ticker="B", weight_pct=20.0),
            IndexConstituent(index_ticker="IMOEX", ticker="C", weight_pct=15.0),
            IndexConstituent(index_ticker="IMOEX", ticker="D", weight_pct=10.0),
            IndexConstituent(index_ticker="IMOEX", ticker="E", weight_pct=5.0),
            IndexConstituent(index_ticker="IMOEX", ticker="F", weight_pct=4.0),
        ]

        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_index_constituents", return_value=members):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = _call_tool(
                    server,
                    "get_index_constituents_metrics",
                    index_ticker="IMOEX",
                    as_of_date="2024-01-10",
                )

                metrics = result["metrics"]
                assert metrics["num_constituents"] == 6
                assert metrics["top5_weight_pct"] == 80.0  # 30+20+15+10+5

    def test_optional_fields_omitted_when_none(self):
        """last_price/price_change_pct/sector=None → ключи отсутствуют в data."""
        members = [
            IndexConstituent(index_ticker="IMOEX", ticker="SBER", weight_pct=20.0, last_price=None, price_change_pct=None, sector=None),
        ]
        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_index_constituents", return_value=members):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = _call_tool(
                    server,
                    "get_index_constituents_metrics",
                    index_ticker="IMOEX",
                    as_of_date="2024-01-10",
                )

                row = result["data"][0]
                assert "last_price" not in row
                assert "price_change_pct" not in row
                assert "sector" not in row

    def test_invalid_index_error_from_iss(self):
        """Ошибки IssClient (InvalidTicker) маппятся в error_type INVALID_TICKER."""
        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_index_constituents", side_effect=InvalidTickerError("bad index")):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = _call_tool(
                    server,
                    "get_index_constituents_metrics",
                    index_ticker="IMOEX",
                    as_of_date="2024-01-10",
                )

                assert result["error"] is not None
                assert result["error"]["error_type"] == "INVALID_TICKER"

    def test_index_ticker_lowercase_is_mapped(self):
        """index_ticker в нижнем регистре корректно маппится в ISS id."""
        members = [IndexConstituent(index_ticker="IMOEX", ticker="SBER", weight_pct=10.0)]
        config = McpConfig()
        server = McpServer(config)

        with patch.object(server.iss_client, "get_index_constituents", return_value=members) as mock_get:
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                result = _call_tool(
                    server,
                    "get_index_constituents_metrics",
                    index_ticker="imoex",
                    as_of_date="2024-01-10",
                )

                assert result["error"] is None
                mock_get.assert_called_once()
                assert result["metadata"]["index_ticker"] == "IMOEX"

    def test_repeated_calls_use_cached_index_mapping(self):
        """Повторные вызовы используют кэш маппинга индекса (TTLCache)."""

        class _Cache:
            def __init__(self) -> None:
                self.store = {}
                self.get_calls: list[str] = []
                self.set_calls: list[tuple[str, str]] = []

            def get(self, key: str):
                self.get_calls.append(key)
                return self.store.get(key)

            def set(self, key: str, value: str):
                self.set_calls.append((key, value))
                self.store[key] = value

        members = [IndexConstituent(index_ticker="IMOEX", ticker="SBER", weight_pct=20.0)]
        cache = _Cache()

        config = McpConfig()
        server = McpServer(config)
        server._index_cache = cache  # type: ignore[attr-defined]
        init_index_tool_dependencies(server.iss_client, server.metrics, server.tracing, cache)

        with patch.object(server.iss_client, "get_index_constituents", return_value=members):
            app = server.fastmcp.http_app(transport="streamable-http")
            with TestClient(app):
                _call_tool(server, "get_index_constituents_metrics", index_ticker="IMOEX", as_of_date="2024-01-10")
                _call_tool(server, "get_index_constituents_metrics", index_ticker="IMOEX", as_of_date="2024-01-11")

        assert cache.set_calls == [("IMOEX", "IMOEX")]
        assert cache.get_calls.count("IMOEX") >= 2
