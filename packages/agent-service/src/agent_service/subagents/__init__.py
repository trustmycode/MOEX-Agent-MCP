"""
Сабагенты для мультиагентной архитектуры moex-market-analyst-agent.

Содержит специализированные сабагенты:
- DashboardSubagent — формирование RiskDashboardSpec для UI
- ExplainerSubagent — генерация текстового отчёта через LLM
"""

from .dashboard import DashboardSubagent
from .explainer import ExplainerSubagent
from .market_data import MarketDataSubagent
from .research_planner import ResearchPlannerSubagent
from .risk_analytics import RiskAnalyticsSubagent

__all__ = [
    "DashboardSubagent",
    "ExplainerSubagent",
    "MarketDataSubagent",
    "ResearchPlannerSubagent",
    "RiskAnalyticsSubagent",
]
