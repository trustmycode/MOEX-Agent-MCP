"""
MCP type definitions for agent-service.

Contains Pydantic models for MCP configuration, tool calls, and error handling.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class McpConfig(BaseModel):
    """
    Configuration for MCP client connection.

    Attributes:
        name: Unique name for the MCP server (e.g., "moex-iss-mcp").
        url: Base URL of the MCP server (e.g., "http://localhost:8000").
        timeout_seconds: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        ...,
        description="Unique name for the MCP server",
        examples=["moex-iss-mcp", "risk-analytics-mcp"],
    )

    url: str = Field(
        ...,
        description="Base URL of the MCP server",
        examples=["http://localhost:8000", "http://moex-iss-mcp:8080"],
    )

    timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds",
    )

    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts",
    )


class ToolError(BaseModel):
    """
    Standardized error from MCP tool call.

    Matches the error format defined in SPEC_risk-analytics-mcp.md.

    Attributes:
        error_type: Error type code (e.g., INVALID_TICKER, ISS_TIMEOUT).
        message: Human-readable error message.
        details: Additional structured error details.
    """

    model_config = ConfigDict(extra="allow")

    error_type: str = Field(
        ...,
        description="Error type code",
        examples=[
            "INVALID_TICKER",
            "DATE_RANGE_TOO_LARGE",
            "TOO_MANY_TICKERS",
            "ISS_TIMEOUT",
            "ISS_5XX",
            "VALIDATION_ERROR",
            "INSUFFICIENT_DATA",
            "UNKNOWN",
        ],
    )

    message: str = Field(
        ...,
        description="Human-readable error message",
    )

    details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional structured error details",
    )

    @classmethod
    def from_mcp_response(cls, error_data: dict[str, Any]) -> ToolError:
        """
        Create ToolError from MCP response error object.

        Args:
            error_data: Error dictionary from MCP response.

        Returns:
            ToolError instance.
        """
        return cls(
            error_type=error_data.get("error_type", "UNKNOWN"),
            message=error_data.get("message", "Unknown error"),
            details=error_data.get("details"),
        )


class ToolCallResult(BaseModel):
    """
    Result of an MCP tool call.

    Wraps either successful response data or error information.

    Attributes:
        tool_name: Name of the called tool.
        success: Whether the call was successful.
        data: Response data (if success=True).
        error: Error information (if success=False).
        latency_ms: Request latency in milliseconds.
    """

    model_config = ConfigDict(extra="allow")

    tool_name: str = Field(
        ...,
        description="Name of the called MCP tool",
    )

    success: bool = Field(
        ...,
        description="Whether the tool call was successful",
    )

    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Response data from the tool (if success=True)",
    )

    error: Optional[ToolError] = Field(
        default=None,
        description="Error information (if success=False)",
    )

    latency_ms: Optional[float] = Field(
        default=None,
        ge=0,
        description="Request latency in milliseconds",
    )

    @classmethod
    def success_result(
        cls,
        tool_name: str,
        data: dict[str, Any],
        latency_ms: Optional[float] = None,
    ) -> ToolCallResult:
        """
        Create successful result.

        Args:
            tool_name: Name of the called tool.
            data: Response data.
            latency_ms: Request latency.

        Returns:
            ToolCallResult with success=True.
        """
        return cls(
            tool_name=tool_name,
            success=True,
            data=data,
            error=None,
            latency_ms=latency_ms,
        )

    @classmethod
    def error_result(
        cls,
        tool_name: str,
        error: ToolError,
        latency_ms: Optional[float] = None,
    ) -> ToolCallResult:
        """
        Create error result.

        Args:
            tool_name: Name of the called tool.
            error: Error information.
            latency_ms: Request latency.

        Returns:
            ToolCallResult with success=False.
        """
        return cls(
            tool_name=tool_name,
            success=False,
            data=None,
            error=error,
            latency_ms=latency_ms,
        )


