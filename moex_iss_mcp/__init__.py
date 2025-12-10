"""
moex-iss-mcp package exports the MCP server wrapper and configuration helpers.

The actual tools will be implemented in later phases; this module provides the
entry points (`McpConfig`, `McpServer`, `main`) to start a FastMCP instance.
"""

from .config import McpConfig
from .server import McpServer

__all__ = ["McpConfig", "McpServer"]
