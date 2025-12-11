"""
Единый экземпляр FastMCP для risk-analytics-mcp.

Этот модуль создаёт и экспортирует единственный экземпляр FastMCP,
который используется всеми инструментами сервера.
"""

from fastmcp import FastMCP

# Создаём единый экземпляр FastMCP
mcp = FastMCP("risk-analytics-mcp")

