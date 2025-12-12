"""
MCP client infrastructure for agent-service.

Provides clients for communication with MCP servers (moex-iss-mcp, risk-analytics-mcp).
"""

from .client import McpClient
from .types import McpConfig, ToolCallResult, ToolError

__all__ = [
    "McpClient",
    "McpConfig",
    "ToolCallResult",
    "ToolError",
]


