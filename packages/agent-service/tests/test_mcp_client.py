"""
Tests for MCP client.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agent_service.mcp.client import McpClient
from agent_service.mcp.types import McpConfig, ToolCallResult, ToolError


@pytest.fixture
def mcp_config() -> McpConfig:
    """Create MCP config for testing."""
    return McpConfig(
        name="test-mcp",
        url="http://localhost:8000",
        timeout_seconds=10.0,
        max_retries=2,
    )


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Create mock httpx client."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


class TestMcpConfig:
    """Test McpConfig model."""

    def test_config_creation(self):
        """Test basic config creation."""
        config = McpConfig(name="test", url="http://localhost:8000")

        assert config.name == "test"
        assert config.url == "http://localhost:8000"
        assert config.timeout_seconds == 30.0  # default
        assert config.max_retries == 3  # default

    def test_config_custom_values(self):
        """Test config with custom values."""
        config = McpConfig(
            name="custom",
            url="http://custom:9000",
            timeout_seconds=60.0,
            max_retries=5,
        )

        assert config.timeout_seconds == 60.0
        assert config.max_retries == 5

    def test_config_immutable(self):
        """Test that config is immutable (frozen)."""
        config = McpConfig(name="test", url="http://localhost:8000")

        with pytest.raises(Exception):  # ValidationError or AttributeError
            config.name = "changed"


class TestToolError:
    """Test ToolError model."""

    def test_tool_error_creation(self):
        """Test basic tool error creation."""
        error = ToolError(
            error_type="INVALID_TICKER",
            message="Ticker not found",
        )

        assert error.error_type == "INVALID_TICKER"
        assert error.message == "Ticker not found"
        assert error.details is None

    def test_tool_error_with_details(self):
        """Test tool error with details."""
        error = ToolError(
            error_type="VALIDATION_ERROR",
            message="Invalid input",
            details={"field": "ticker", "value": ""},
        )

        assert error.details["field"] == "ticker"

    def test_from_mcp_response(self):
        """Test creating ToolError from MCP response."""
        response = {
            "error_type": "ISS_TIMEOUT",
            "message": "Connection timeout",
            "details": {"retry_after": 5},
        }

        error = ToolError.from_mcp_response(response)

        assert error.error_type == "ISS_TIMEOUT"
        assert error.message == "Connection timeout"
        assert error.details["retry_after"] == 5

    def test_from_mcp_response_minimal(self):
        """Test creating ToolError from minimal response."""
        response = {}

        error = ToolError.from_mcp_response(response)

        assert error.error_type == "UNKNOWN"
        assert error.message == "Unknown error"


class TestToolCallResult:
    """Test ToolCallResult model."""

    def test_success_result(self):
        """Test creating success result."""
        result = ToolCallResult.success_result(
            tool_name="test_tool",
            data={"key": "value"},
            latency_ms=100.5,
        )

        assert result.success
        assert result.tool_name == "test_tool"
        assert result.data["key"] == "value"
        assert result.latency_ms == 100.5
        assert result.error is None

    def test_error_result(self):
        """Test creating error result."""
        error = ToolError(error_type="ERROR", message="Failed")
        result = ToolCallResult.error_result(
            tool_name="test_tool",
            error=error,
            latency_ms=50.0,
        )

        assert not result.success
        assert result.error.error_type == "ERROR"
        assert result.data is None


class TestMcpClient:
    """Test McpClient."""

    def test_client_creation(self, mcp_config: McpConfig):
        """Test client creation."""
        client = McpClient(mcp_config)

        assert client.config == mcp_config
        assert repr(client) == "<McpClient(name='test-mcp', url='http://localhost:8000')>"

    @pytest.mark.asyncio
    async def test_call_tool_success(self, mcp_config: McpConfig):
        """Test successful tool call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"data": {"ticker": "SBER"}},
        }

        mock_httpx = AsyncMock()
        mock_httpx.post.return_value = mock_response

        client = McpClient(mcp_config, client=mock_httpx)
        result = await client.call_tool("test_tool", {"arg": "value"})

        assert result.success
        assert result.data["data"]["ticker"] == "SBER"

    @pytest.mark.asyncio
    async def test_call_tool_with_error_in_response(self, mcp_config: McpConfig):
        """Test tool call with error in response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "error": {
                    "error_type": "INVALID_TICKER",
                    "message": "Not found",
                }
            }
        }

        mock_httpx = AsyncMock()
        mock_httpx.post.return_value = mock_response

        client = McpClient(mcp_config, client=mock_httpx)
        result = await client.call_tool("test_tool", {"ticker": "FAKE"})

        assert not result.success
        assert result.error.error_type == "INVALID_TICKER"

    @pytest.mark.asyncio
    async def test_call_tool_timeout_retry(self, mcp_config: McpConfig):
        """Test retry on timeout."""
        mock_httpx = AsyncMock()
        mock_httpx.post.side_effect = [
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),  # All retries exhausted
        ]

        client = McpClient(mcp_config, client=mock_httpx)
        result = await client.call_tool("test_tool", {})

        assert not result.success
        assert result.error.error_type == "ISS_TIMEOUT"
        # Should have tried max_retries + 1 times
        assert mock_httpx.post.call_count == 3

    @pytest.mark.asyncio
    async def test_call_tool_5xx_retry(self, mcp_config: McpConfig):
        """Test retry on 5xx errors."""
        error_response = MagicMock()
        error_response.status_code = 503

        mock_httpx = AsyncMock()
        mock_httpx.post.side_effect = httpx.HTTPStatusError(
            "Service Unavailable",
            request=MagicMock(),
            response=error_response,
        )

        client = McpClient(mcp_config, client=mock_httpx)
        result = await client.call_tool("test_tool", {})

        assert not result.success
        assert result.error.error_type == "ISS_5XX"

    @pytest.mark.asyncio
    async def test_call_tool_4xx_no_retry(self, mcp_config: McpConfig):
        """Test no retry on 4xx errors."""
        error_response = MagicMock()
        error_response.status_code = 400

        mock_httpx = AsyncMock()
        mock_httpx.post.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=error_response,
        )

        client = McpClient(mcp_config, client=mock_httpx)
        result = await client.call_tool("test_tool", {})

        assert not result.success
        # Should not retry on 4xx
        assert mock_httpx.post.call_count == 1

    @pytest.mark.asyncio
    async def test_health_check_success(self, mcp_config: McpConfig):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_httpx = AsyncMock()
        mock_httpx.get.return_value = mock_response

        client = McpClient(mcp_config, client=mock_httpx)
        result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mcp_config: McpConfig):
        """Test failed health check."""
        mock_httpx = AsyncMock()
        mock_httpx.get.side_effect = httpx.RequestError("Connection failed")

        client = McpClient(mcp_config, client=mock_httpx)
        result = await client.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_close(self, mcp_config: McpConfig):
        """Test client close."""
        mock_httpx = AsyncMock()

        client = McpClient(mcp_config, client=mock_httpx)
        client._owns_client = True
        await client.close()

        mock_httpx.aclose.assert_called_once()

    def test_classify_error_timeout(self, mcp_config: McpConfig):
        """Test error classification for timeout."""
        client = McpClient(mcp_config)
        error_type = client._classify_error(httpx.TimeoutException("timeout"))

        assert error_type == "ISS_TIMEOUT"

    def test_classify_error_http_5xx(self, mcp_config: McpConfig):
        """Test error classification for 5xx."""
        response = MagicMock()
        response.status_code = 500

        client = McpClient(mcp_config)
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=response)
        error_type = client._classify_error(error)

        assert error_type == "ISS_5XX"

    def test_classify_error_http_429(self, mcp_config: McpConfig):
        """Test error classification for rate limit."""
        response = MagicMock()
        response.status_code = 429

        client = McpClient(mcp_config)
        error = httpx.HTTPStatusError("Rate limit", request=MagicMock(), response=response)
        error_type = client._classify_error(error)

        assert error_type == "RATE_LIMIT"

