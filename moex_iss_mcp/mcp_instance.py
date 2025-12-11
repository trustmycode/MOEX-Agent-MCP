"""
Единый экземпляр FastMCP для moex-iss-mcp.

Этот модуль создаёт и экспортирует единственный экземпляр FastMCP,
который используется всеми инструментами сервера.
"""

from fastmcp import FastMCP

# Создаём единый экземпляр FastMCP
mcp = FastMCP("moex-iss-mcp")

