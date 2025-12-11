"""
Сабагенты для мультиагентной архитектуры moex-market-analyst-agent.

Содержит специализированные сабагенты:
- DashboardSubagent — формирование RiskDashboardSpec для UI
- ExplainerSubagent — генерация текстового отчёта через LLM
"""

from .dashboard import DashboardSubagent
from .explainer import ExplainerSubagent

__all__ = [
    "DashboardSubagent",
    "ExplainerSubagent",
]
