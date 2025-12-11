"""
Tests for RiskAnalyticsSubagent.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from agent_service.core.context import AgentContext
from agent_service.core.result import SubagentResult
from agent_service.mcp.client import McpClient
from agent_service.mcp.types import McpConfig, ToolCallResult, ToolError
from agent_service.subagents.risk_analytics import RiskAnalyticsSubagent


@pytest.fixture
def mock_mcp_client() -> McpClient:
    """Create a mock MCP client."""
    config = McpConfig(name="risk-analytics-mcp", url="http://test:8010")
    client = McpClient(config)
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def risk_subagent(mock_mcp_client: McpClient) -> RiskAnalyticsSubagent:
    """Create RiskAnalyticsSubagent with mocked MCP client."""
    return RiskAnalyticsSubagent(mcp_client=mock_mcp_client)


@pytest.fixture
def basic_context() -> AgentContext:
    """Create basic AgentContext for testing."""
    return AgentContext(user_query="Оцени риск портфеля")


@pytest.fixture
def portfolio_positions() -> list[dict]:
    """Sample portfolio positions."""
    return [
        {"ticker": "SBER", "weight": 0.4},
        {"ticker": "GAZP", "weight": 0.3},
        {"ticker": "LKOH", "weight": 0.3},
    ]


class TestRiskAnalyticsSubagentInit:
    """Test RiskAnalyticsSubagent initialization."""

    def test_init_with_mcp_client(self, mock_mcp_client: McpClient):
        """Test initialization with pre-configured MCP client."""
        subagent = RiskAnalyticsSubagent(mcp_client=mock_mcp_client)

        assert subagent.name == "risk_analytics"
        assert subagent.mcp_client is mock_mcp_client
        assert "compute_portfolio_risk_basic" in subagent.capabilities

    def test_init_with_mcp_config(self):
        """Test initialization with MCP config."""
        config = McpConfig(name="risk-analytics-mcp", url="http://custom:9001")
        subagent = RiskAnalyticsSubagent(mcp_config=config)

        assert subagent.mcp_client.config.url == "http://custom:9001"

    def test_init_from_env(self):
        """Test initialization from environment variables."""
        with patch.dict("os.environ", {"RISK_ANALYTICS_MCP_URL": "http://env:8081"}):
            subagent = RiskAnalyticsSubagent()
            assert subagent.mcp_client.config.url == "http://env:8081"

    def test_capabilities(self, risk_subagent: RiskAnalyticsSubagent):
        """Test that subagent has correct capabilities."""
        expected = [
            "compute_portfolio_risk_basic",
            "compute_correlation_matrix",
            "suggest_rebalance",
            "cfo_liquidity_report",
            "issuer_peers_compare",
        ]
        assert risk_subagent.capabilities == expected


class TestRiskAnalyticsSubagentPortfolioRisk:
    """Test compute_portfolio_risk_basic functionality."""

    @pytest.mark.asyncio
    async def test_compute_portfolio_risk_success(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
        portfolio_positions: list[dict],
    ):
        """Test successful portfolio risk calculation."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="compute_portfolio_risk_basic",
            data={
                "metadata": {"from_date": "2024-01-01", "to_date": "2024-12-31"},
                "portfolio_metrics": {
                    "total_return_pct": 15.2,
                    "annualized_volatility_pct": 18.5,
                    "max_drawdown_pct": -8.3,
                },
                "concentration_metrics": {
                    "top1_weight_pct": 40.0,
                    "hhi": 0.34,
                },
            },
        )

        result = await risk_subagent.compute_portfolio_risk_basic(
            positions=portfolio_positions,
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert result.success
        assert result.data["portfolio_metrics"]["total_return_pct"] == 15.2
        mock_mcp_client.call_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_compute_portfolio_risk_validation_error(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test portfolio risk with validation error."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.error_result(
            tool_name="compute_portfolio_risk_basic",
            error=ToolError(
                error_type="VALIDATION_ERROR",
                message="Weights must sum to 1.0",
            ),
        )

        result = await risk_subagent.compute_portfolio_risk_basic(
            positions=[{"ticker": "SBER", "weight": 0.5}],  # Doesn't sum to 1
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert not result.success
        assert result.error.error_type == "VALIDATION_ERROR"


class TestRiskAnalyticsSubagentCorrelation:
    """Test compute_correlation_matrix functionality."""

    @pytest.mark.asyncio
    async def test_compute_correlation_success(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test successful correlation matrix calculation."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="compute_correlation_matrix",
            data={
                "tickers": ["SBER", "GAZP"],
                "matrix": [[1.0, 0.65], [0.65, 1.0]],
                "metadata": {"num_observations": 250},
            },
        )

        result = await risk_subagent.compute_correlation_matrix(
            tickers=["SBER", "GAZP"],
            from_date="2024-01-01",
            to_date="2024-12-31",
        )

        assert result.success
        assert result.data["matrix"][0][1] == 0.65

    @pytest.mark.asyncio
    async def test_compute_correlation_insufficient_data(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test correlation with insufficient data."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.error_result(
            tool_name="compute_correlation_matrix",
            error=ToolError(
                error_type="INSUFFICIENT_DATA",
                message="Need at least 30 observations",
            ),
        )

        result = await risk_subagent.compute_correlation_matrix(
            tickers=["SBER", "GAZP"],
            from_date="2024-12-01",
            to_date="2024-12-10",  # Too short
        )

        assert not result.success
        assert result.error.error_type == "INSUFFICIENT_DATA"


class TestRiskAnalyticsSubagentRebalance:
    """Test suggest_rebalance functionality."""

    @pytest.mark.asyncio
    async def test_suggest_rebalance_success(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test successful rebalance suggestion."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.5, "asset_class": "equity"},
            {"ticker": "GAZP", "current_weight": 0.5, "asset_class": "equity"},
        ]

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="suggest_rebalance",
            data={
                "target_weights": {"SBER": 0.4, "GAZP": 0.6},
                "trades": [
                    {
                        "ticker": "SBER",
                        "side": "sell",
                        "weight_delta": -0.1,
                    }
                ],
                "summary": {"total_turnover": 0.2},
            },
        )

        result = await risk_subagent.suggest_rebalance(
            positions=positions,
            risk_profile={"max_single_position_weight": 0.4},
        )

        assert result.success
        assert result.data["target_weights"]["SBER"] == 0.4


class TestRiskAnalyticsSubagentCFOLiquidity:
    """Test cfo_liquidity_report functionality."""

    @pytest.mark.asyncio
    async def test_cfo_liquidity_report_success(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test successful CFO liquidity report generation."""
        positions = [
            {
                "ticker": "SBER",
                "weight": 0.5,
                "asset_class": "equity",
                "liquidity_bucket": "0-7d",
            },
        ]

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="cfo_liquidity_report",
            data={
                "liquidity_profile": {"quick_ratio_pct": 75.0},
                "executive_summary": {
                    "overall_liquidity_status": "adequate",
                },
            },
        )

        result = await risk_subagent.cfo_liquidity_report(
            positions=positions,
            from_date="2024-01-01",
            to_date="2024-12-31",
            horizon_months=12,
        )

        assert result.success
        assert result.data["executive_summary"]["overall_liquidity_status"] == "adequate"


class TestRiskAnalyticsSubagentIssuerPeers:
    """Test issuer_peers_compare functionality."""

    @pytest.mark.asyncio
    async def test_issuer_peers_compare_success(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test successful issuer peers comparison."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="issuer_peers_compare",
            data={
                "metadata": {"base_ticker": "SBER", "peer_count": 5},
                "base_issuer": {
                    "ticker": "SBER",
                    "pe_ratio": 5.2,
                    "roe_pct": 22.5,
                },
                "peers": [
                    {"ticker": "VTBR", "pe_ratio": 3.8},
                ],
                "ranking": [
                    {"metric": "pe_ratio", "rank": 2, "total": 6},
                ],
                "flags": [],
            },
        )

        result = await risk_subagent.issuer_peers_compare(
            ticker="SBER",
            sector="FINANCIALS",
        )

        assert result.success
        assert result.data["base_issuer"]["ticker"] == "SBER"

    @pytest.mark.asyncio
    async def test_issuer_peers_compare_no_peers_found(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test issuer peers comparison when no peers found."""
        mock_mcp_client.call_tool.return_value = ToolCallResult.error_result(
            tool_name="issuer_peers_compare",
            error=ToolError(
                error_type="NO_PEERS_FOUND",
                message="No peers found for the given criteria",
            ),
        )

        result = await risk_subagent.issuer_peers_compare(
            ticker="RARE",
            sector="UNKNOWN_SECTOR",
        )

        assert not result.success
        assert result.error.error_type == "NO_PEERS_FOUND"


class TestRiskAnalyticsSubagentExecute:
    """Test execute method with different scenarios."""

    @pytest.mark.asyncio
    async def test_execute_portfolio_risk_scenario(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
        portfolio_positions: list[dict],
    ):
        """Test execute for portfolio_risk_basic scenario."""
        context = AgentContext(
            user_query="Оцени риск портфеля",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result("parsed_params", {"positions": portfolio_positions})

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="compute_portfolio_risk_basic",
            data={"portfolio_metrics": {"total_return_pct": 15.0}},
        )

        result = await risk_subagent.execute(context)

        assert result.is_success
        assert result.data["scenario"] == "portfolio_risk_basic"
        assert result.next_agent_hint == "dashboard"

    @pytest.mark.asyncio
    async def test_execute_correlation_scenario(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test execute for portfolio_correlation scenario."""
        context = AgentContext(
            user_query="Покажи корреляции",
            scenario_type="portfolio_correlation",
        )
        context.add_result("parsed_params", {"tickers": ["SBER", "GAZP", "LKOH"]})

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="compute_correlation_matrix",
            data={"matrix": [[1.0, 0.6, 0.5], [0.6, 1.0, 0.7], [0.5, 0.7, 1.0]]},
        )

        result = await risk_subagent.execute(context)

        assert result.is_success
        assert result.data["scenario"] == "portfolio_correlation"

    @pytest.mark.asyncio
    async def test_execute_rebalance_scenario(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test execute for rebalance scenario."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.5},
            {"ticker": "GAZP", "current_weight": 0.5},
        ]

        context = AgentContext(
            user_query="Предложи ребалансировку",
            scenario_type="rebalance",
        )
        context.add_result("parsed_params", {"positions": positions})

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="suggest_rebalance",
            data={"trades": [], "summary": {}},
        )

        result = await risk_subagent.execute(context)

        assert result.is_success
        assert result.data["scenario"] == "rebalance"
        assert result.next_agent_hint == "explainer"

    @pytest.mark.asyncio
    async def test_execute_cfo_liquidity_scenario(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test execute for cfo_liquidity_report scenario."""
        positions = [{"ticker": "SBER", "weight": 0.5}]

        context = AgentContext(
            user_query="CFO отчёт по ликвидности",
            scenario_type="cfo_liquidity_report",
        )
        context.add_result("parsed_params", {"positions": positions})

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="cfo_liquidity_report",
            data={"executive_summary": {}},
        )

        result = await risk_subagent.execute(context)

        assert result.is_success
        assert result.data["scenario"] == "cfo_liquidity_report"

    @pytest.mark.asyncio
    async def test_execute_issuer_peers_scenario(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test execute for issuer_peers_compare scenario."""
        context = AgentContext(
            user_query="Сравни SBER с пирами",
            scenario_type="issuer_peers_compare",
        )
        context.add_result("parsed_params", {"ticker": "SBER"})

        mock_mcp_client.call_tool.return_value = ToolCallResult.success_result(
            tool_name="issuer_peers_compare",
            data={"metadata": {}, "peers": [], "ranking": [], "flags": []},
        )

        result = await risk_subagent.execute(context)

        assert result.is_success
        assert result.data["scenario"] == "issuer_peers_compare"

    @pytest.mark.asyncio
    async def test_execute_missing_positions(
        self,
        risk_subagent: RiskAnalyticsSubagent,
    ):
        """Test execute with missing positions for portfolio risk."""
        context = AgentContext(
            user_query="Оцени риск",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result("parsed_params", {})  # No positions

        result = await risk_subagent.execute(context)

        assert result.is_error
        assert "позиции" in result.error_message.lower()


class TestRiskAnalyticsSubagentHelpers:
    """Test helper methods."""

    def test_default_dates(
        self,
        risk_subagent: RiskAnalyticsSubagent,
    ):
        """Test default date calculation."""
        to_date = risk_subagent._default_to_date()
        from_date = risk_subagent._default_from_date()

        assert to_date == date.today().isoformat()
        expected_from = (date.today() - timedelta(days=365)).isoformat()
        assert from_date == expected_from


class TestRiskAnalyticsSubagentErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_mcp_error_handling(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
        portfolio_positions: list[dict],
    ):
        """Test handling of MCP errors."""
        context = AgentContext(
            user_query="Оцени риск",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result("parsed_params", {"positions": portfolio_positions})

        mock_mcp_client.call_tool.return_value = ToolCallResult.error_result(
            tool_name="compute_portfolio_risk_basic",
            error=ToolError(
                error_type="ISS_TIMEOUT",
                message="Connection timeout",
            ),
        )

        result = await risk_subagent.execute(context)

        assert result.is_error
        assert "риск" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_exception_handling(
        self,
        risk_subagent: RiskAnalyticsSubagent,
        mock_mcp_client: McpClient,
    ):
        """Test handling of unexpected exceptions."""
        context = AgentContext(
            user_query="Оцени риск",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result("parsed_params", {"positions": [{"ticker": "SBER", "weight": 1.0}]})

        mock_mcp_client.call_tool.side_effect = RuntimeError("Unexpected error")

        result = await risk_subagent.execute(context)

        assert result.is_error
        assert "RuntimeError" in result.error_message
