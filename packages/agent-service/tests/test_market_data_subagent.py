"""
Tests for MarketDataSubagent.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_service.core.context import AgentContext
from agent_service.core.result import SubagentResult
from agent_service.mcp.client import McpClient
from agent_service.mcp.types import McpConfig, ToolCallResult, ToolError
from agent_service.subagents.market_data import (
    DEFAULT_BOARD,
    MAX_TICKERS_PER_CALL,
    MarketDataSubagent,
)


@pytest.fixture
def mock_mcp_client() -> McpClient:
    """Create a mock MCP client."""
    config = McpConfig(name="moex-iss-mcp", url="http://test:8000")
    client = McpClient(config)
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def market_data_subagent(mock_mcp_client: McpClient) -> MarketDataSubagent:
    """Create MarketDataSubagent with mocked MCP client."""
    return MarketDataSubagent(mcp_client=mock_mcp_client)


@pytest.fixture
def basic_context() -> AgentContext:
    """Create basic AgentContext for testing."""
    return AgentContext(user_query="Покажи котировки SBER")


class TestMarketDataSubagentInit:
    """Test MarketDataSubagent initialization."""

    def test_init_with_mcp_client(self, mock_mcp_client: McpClient):
        """Test initialization with pre-configured MCP client."""
        subagent = MarketDataSubagent(mcp_client=mock_mcp_client)

        assert subagent.name == "market_data"
        assert subagent.mcp_client is mock_mcp_client
        assert "get_security_snapshot" in subagent.capabilities

    def test_init_with_mcp_config(self):
        """Test initialization with MCP config."""
        config = McpConfig(name="moex-iss-mcp", url="http://custom:9000")
        subagent = MarketDataSubagent(mcp_config=config)

        assert subagent.mcp_client.config.url == "http://custom:9000"

    def test_init_from_env(self):
        """Test initialization from environment variables."""
        with patch.dict("os.environ", {"MOEX_ISS_MCP_URL": "http://env:8080"}):
            subagent = MarketDataSubagent()
            assert subagent.mcp_client.config.url == "http://env:8080"

    def test_capabilities(self, market_data_subagent: MarketDataSubagent):
        """Test that subagent has correct capabilities."""
        expected = [
            "get_security_snapshot",
            "get_ohlcv_timeseries",
            "get_index_constituents_metrics",
            "get_security_fundamentals",
        ]
        assert market_data_subagent.capabilities == expected


class TestMarketDataSubagentSnapshot:
    """Test get_security_snapshot functionality."""

    @pytest.mark.asyncio
    async def test_get_security_snapshot_success(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test successful snapshot retrieval."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="get_security_snapshot",
            data={
                "metadata": {"ticker": "SBER", "board": "TQBR"},
                "data": {"last_price": 290.5, "price_change_pct": 1.2},
            },
        )

        result = await market_data_subagent.get_security_snapshot("SBER")

        assert result.success
        assert result.data["data"]["last_price"] == 290.5
        mock_mcp_client.call_tool.assert_called_once_with(
            tool_name="get_security_snapshot",
            args={"ticker": "SBER", "board": DEFAULT_BOARD},
        )

    @pytest.mark.asyncio
    async def test_get_security_snapshot_invalid_ticker(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test snapshot with invalid ticker."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.error_result(
            tool_name="get_security_snapshot",
            error=ToolError(
                error_type="INVALID_TICKER",
                message="Ticker 'FAKE' not found",
            ),
        )

        result = await market_data_subagent.get_security_snapshot("FAKE")

        assert not result.success
        assert result.error.error_type == "INVALID_TICKER"


class TestMarketDataSubagentOHLCV:
    """Test get_ohlcv_timeseries functionality."""

    @pytest.mark.asyncio
    async def test_get_ohlcv_success(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test successful OHLCV data retrieval."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="get_ohlcv_timeseries",
            data={
                "metadata": {"ticker": "SBER", "from_date": "2024-01-01"},
                "data": [{"ts": "2024-01-01", "close": 280.0}],
                "metrics": {"total_return_pct": 10.5},
            },
        )

        result = await market_data_subagent.get_ohlcv_timeseries(
            ticker="SBER",
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert result.success
        assert result.data["metrics"]["total_return_pct"] == 10.5


class TestMarketDataSubagentExecute:
    """Test execute method with different scenarios."""

    @pytest.mark.asyncio
    async def test_execute_single_security_overview(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test execute for single_security_overview scenario."""
        context = AgentContext(
            user_query="Покажи котировки SBER",
            scenario_type="single_security_overview",
        )
        context.add_result("parsed_params", {"ticker": "SBER"})

        # Mock snapshot response
        mock_mcp_client.call_tool.side_effect = [
            ToolCallResult.success_result(
                tool_name="get_security_snapshot",
                data={"data": {"last_price": 290.5}},
            ),
            ToolCallResult.success_result(
                tool_name="get_ohlcv_timeseries",
                data={"data": [], "metrics": {}},
            ),
        ]

        result = await market_data_subagent.execute(context)

        assert result.is_success
        assert result.data["ticker"] == "SBER"
        assert result.data["snapshot"]["data"]["last_price"] == 290.5
        assert result.next_agent_hint == "risk_analytics"

    @pytest.mark.asyncio
    async def test_execute_compare_securities(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test execute for compare_securities scenario."""
        context = AgentContext(
            user_query="Сравни SBER и GAZP",
            scenario_type="compare_securities",
        )
        context.add_result("parsed_params", {"tickers": ["SBER", "GAZP"]})

        # Mock responses for each ticker
        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="get_security_snapshot",
            data={"data": {"last_price": 290.5}},
        )

        result = await market_data_subagent.execute(context)

        assert result.is_success or result.is_partial
        assert "SBER" in result.data["securities"]
        assert "GAZP" in result.data["securities"]

    @pytest.mark.asyncio
    async def test_execute_portfolio_data_limits_tickers(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test that portfolio data respects ticker limits."""
        # Create positions with more than MAX_TICKERS_PER_CALL
        positions = [
            {"ticker": f"TICK{i}", "weight": 1.0 / 15}
            for i in range(15)
        ]

        context = AgentContext(
            user_query="Оцени риск портфеля",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result("parsed_params", {"positions": positions})

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="get_ohlcv_timeseries",
            data={"data": []},
        )

        result = await market_data_subagent.execute(context)

        # Should have called OHLCV for max tickers only
        assert mock_mcp_client.call_tool.call_count <= MAX_TICKERS_PER_CALL

    @pytest.mark.asyncio
    async def test_execute_index_risk_scan(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test execute for index_risk_scan scenario."""
        context = AgentContext(
            user_query="Анализ индекса IMOEX",
            scenario_type="index_risk_scan",
        )
        context.add_result("parsed_params", {"index_ticker": "IMOEX"})

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="get_index_constituents_metrics",
            data={
                "metadata": {"index_ticker": "IMOEX"},
                "data": [{"ticker": "SBER", "weight_pct": 15.0}],
            },
        )

        result = await market_data_subagent.execute(context)

        assert result.is_success
        assert result.data["index_ticker"] == "IMOEX"

    @pytest.mark.asyncio
    async def test_execute_validation_no_ticker(
        self,
        market_data_subagent: MarketDataSubagent,
    ):
        """Test that execute handles missing ticker gracefully."""
        # Query without any recognizable ticker
        context = AgentContext(user_query="Покажи данные")
        context.scenario_type = None  # No scenario type

        result = await market_data_subagent.safe_execute(context)

        # Should fail due to no tickers extracted
        assert result.is_error
        assert "тикер" in result.error_message.lower()


class TestMarketDataSubagentHelpers:
    """Test helper methods."""

    def test_extract_single_ticker(
        self,
        market_data_subagent: MarketDataSubagent,
    ):
        """Test ticker extraction from query."""
        # Use query without stopwords that match
        ticker = market_data_subagent._extract_single_ticker(
            "Get SBER quotes"
        )
        assert ticker == "SBER"

    def test_extract_single_ticker_from_russian(
        self,
        market_data_subagent: MarketDataSubagent,
    ):
        """Test ticker extraction from Russian query."""
        # Test with Latin ticker in Russian text
        ticker = market_data_subagent._extract_single_ticker(
            "Котировки по GAZP"
        )
        assert ticker == "GAZP"

    def test_extract_ticker_ignores_english_stopwords(
        self,
        market_data_subagent: MarketDataSubagent,
    ):
        """Test that common English words are ignored."""
        ticker = market_data_subagent._extract_single_ticker(
            "SHOW THE SBER data"
        )
        # SHOW and THE should be ignored, SBER extracted
        assert ticker == "SBER"

    def test_extract_tickers_multiple(
        self,
        market_data_subagent: MarketDataSubagent,
    ):
        """Test multiple ticker extraction."""
        tickers = market_data_subagent._extract_tickers(
            "Сравни SBER, GAZP и LKOH"
        )
        assert "SBER" in tickers
        assert "GAZP" in tickers
        assert "LKOH" in tickers

    def test_extract_tickers_filters_stopwords(
        self,
        market_data_subagent: MarketDataSubagent,
    ):
        """Test that stopwords are filtered."""
        tickers = market_data_subagent._extract_tickers(
            "Рассчитай ROE и VaR для SBER"
        )
        assert "SBER" in tickers
        assert "ROE" not in tickers
        assert "VaR" not in tickers

    def test_default_dates(
        self,
        market_data_subagent: MarketDataSubagent,
    ):
        """Test default date calculation."""
        to_date = market_data_subagent._default_to_date()
        from_date = market_data_subagent._default_from_date()

        assert to_date == date.today().isoformat()
        expected_from = (date.today() - timedelta(days=365)).isoformat()
        assert from_date == expected_from


class TestMarketDataSubagentErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_mcp_error_handling(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test handling of MCP errors."""
        context = AgentContext(
            user_query="Покажи SBER",
            scenario_type="single_security_overview",
        )
        context.add_result("parsed_params", {"ticker": "SBER"})

        mock_mcp_client.call_tool.return_value = ToolCallResult.error_result(
            tool_name="get_security_snapshot",
            error=ToolError(
                error_type="ISS_TIMEOUT",
                message="Connection timeout",
            ),
        )

        result = await market_data_subagent.execute(context)

        assert result.is_error
        assert "SBER" in result.error_message

    @pytest.mark.asyncio
    async def test_partial_result_on_ohlcv_error(
        self,
        market_data_subagent: MarketDataSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test partial result when OHLCV fails but snapshot succeeds."""
        context = AgentContext(
            user_query="Покажи SBER",
            scenario_type="single_security_overview",
        )
        context.add_result("parsed_params", {"ticker": "SBER"})

        mock_mcp_client.call_tool.side_effect = [
            ToolCallResult.success_result(
                tool_name="get_security_snapshot",
                data={"data": {"last_price": 290.5}},
            ),
            ToolCallResult.error_result(
                tool_name="get_ohlcv_timeseries",
                error=ToolError(
                    error_type="DATE_RANGE_TOO_LARGE",
                    message="Too many days requested",
                ),
            ),
        ]

        result = await market_data_subagent.execute(context)

        assert result.is_partial
        assert result.data["snapshot"] is not None
        assert result.data["ohlcv"] is None

