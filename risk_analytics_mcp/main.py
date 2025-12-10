from __future__ import annotations

from .config import RiskMcpConfig
from .server import RiskMcpServer


def main() -> None:
    """
    Точка входа MCP-процесса риск-аналитики.
    """
    config = RiskMcpConfig.from_env()
    server = RiskMcpServer(config)
    server.run()


if __name__ == "__main__":
    main()
