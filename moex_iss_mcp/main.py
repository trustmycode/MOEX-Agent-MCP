from __future__ import annotations

from .config import McpConfig
from .server import McpServer


def main() -> None:
    """
    Точка входа MCP-процесса.
    """
    config = McpConfig.from_env()
    server = McpServer(config)
    server.run()


if __name__ == "__main__":
    main()
