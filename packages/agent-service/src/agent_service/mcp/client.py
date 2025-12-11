"""
McpClient — универсальный клиент для взаимодействия с MCP-серверами.

Инкапсулирует протокол MCP (HTTP-based), управление тайм-аутами и ретраями.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx

from .types import McpConfig, ToolCallResult, ToolError

logger = logging.getLogger(__name__)


class McpClient:
    """
    HTTP client for MCP server communication.

    Provides methods to call MCP tools with automatic retry,
    timeout handling, and error normalization.

    Attributes:
        config: MCP server configuration.
        _client: httpx.AsyncClient instance.

    Example:
        >>> config = McpConfig(name="moex-iss-mcp", url="http://localhost:8000")
        >>> client = McpClient(config)
        >>> result = await client.call_tool("get_security_snapshot", {"ticker": "SBER"})
        >>> if result.success:
        ...     print(result.data)
    """

    def __init__(
        self,
        config: McpConfig,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """
        Initialize MCP client.

        Args:
            config: MCP server configuration.
            client: Optional pre-configured httpx client (for testing).
        """
        self.config = config
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create httpx client.

        Returns:
            httpx.AsyncClient instance.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.url,
                timeout=self.config.timeout_seconds,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client connection."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def call_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolCallResult:
        """
        Call an MCP tool with the given arguments.

        Implements retry logic and error normalization.

        Args:
            tool_name: Name of the MCP tool to call.
            args: Arguments to pass to the tool.

        Returns:
            ToolCallResult with either data or error.
        """
        start_time = time.perf_counter()
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await self._execute_call(tool_name, args)
                latency_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    "MCP call %s.%s completed in %.2fms (attempt %d)",
                    self.config.name,
                    tool_name,
                    latency_ms,
                    attempt + 1,
                )

                # Check for error in response
                if isinstance(result, dict) and result.get("error"):
                    error = ToolError.from_mcp_response(result["error"])
                    return ToolCallResult.error_result(
                        tool_name=tool_name,
                        error=error,
                        latency_ms=latency_ms,
                    )

                return ToolCallResult.success_result(
                    tool_name=tool_name,
                    data=result,
                    latency_ms=latency_ms,
                )

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "MCP call %s.%s timeout (attempt %d/%d): %s",
                    self.config.name,
                    tool_name,
                    attempt + 1,
                    self.config.max_retries + 1,
                    str(e),
                )
                if attempt < self.config.max_retries:
                    continue

            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code

                # Retry on 5xx errors
                if 500 <= status_code < 600:
                    logger.warning(
                        "MCP call %s.%s HTTP %d (attempt %d/%d)",
                        self.config.name,
                        tool_name,
                        status_code,
                        attempt + 1,
                        self.config.max_retries + 1,
                    )
                    if attempt < self.config.max_retries:
                        continue
                else:
                    # Don't retry client errors (4xx)
                    break

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    "MCP call %s.%s network error (attempt %d/%d): %s",
                    self.config.name,
                    tool_name,
                    attempt + 1,
                    self.config.max_retries + 1,
                    str(e),
                )
                if attempt < self.config.max_retries:
                    continue

        # All retries exhausted
        latency_ms = (time.perf_counter() - start_time) * 1000
        error_type = self._classify_error(last_error)

        return ToolCallResult.error_result(
            tool_name=tool_name,
            error=ToolError(
                error_type=error_type,
                message=str(last_error) if last_error else "Unknown error",
                details={"attempts": self.config.max_retries + 1},
            ),
            latency_ms=latency_ms,
        )

    async def _execute_call(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute the actual HTTP call to MCP server.

        Uses MCP protocol format (JSON-RPC style) with streamable-http transport.

        Args:
            tool_name: Name of the tool to call.
            args: Tool arguments.

        Returns:
            Response data as dictionary.

        Raises:
            httpx.HTTPStatusError: On HTTP error responses.
            httpx.RequestError: On network errors.
        """
        client = await self._get_client()

        # MCP protocol format
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": args,
            },
            "id": 1,
        }

        # Required headers for FastMCP streamable-http transport
        # Must include text/event-stream for streamable-http compatibility
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        response = await client.post("/mcp", json=payload, headers=headers)
        response.raise_for_status()

        result = response.json()

        # Extract result from JSON-RPC response
        if "result" in result:
            return result["result"]
        elif "error" in result:
            # JSON-RPC error
            return {"error": result["error"]}
        else:
            return result

    def _classify_error(self, error: Optional[Exception]) -> str:
        """
        Classify exception into standard error type.

        Args:
            error: Exception to classify.

        Returns:
            Error type code.
        """
        if error is None:
            return "UNKNOWN"

        if isinstance(error, httpx.TimeoutException):
            return "ISS_TIMEOUT"

        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            if 500 <= status < 600:
                return "ISS_5XX"
            elif status == 429:
                return "RATE_LIMIT"
            elif status == 404:
                return "INVALID_TICKER"
            elif status == 400:
                return "VALIDATION_ERROR"
            else:
                return "UNKNOWN"

        if isinstance(error, httpx.RequestError):
            return "ISS_TIMEOUT"  # Network errors treated as timeout

        return "UNKNOWN"

    async def health_check(self) -> bool:
        """
        Check if MCP server is healthy.

        Returns:
            True if server responds with OK status.
        """
        try:
            client = await self._get_client()
            response = await client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(
                "Health check failed for %s: %s",
                self.config.name,
                str(e),
            )
            return False

    def __repr__(self) -> str:
        """String representation."""
        return f"<McpClient(name={self.config.name!r}, url={self.config.url!r})>"
