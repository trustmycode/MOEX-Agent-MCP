"""
Модели данных для agent-service.

Содержит Pydantic-модели для структурированных ответов агентов,
включая RiskDashboardSpec для UI-дашборда.
"""

from .dashboard_spec import (
    Alert,
    AlertSeverity,
    ChartAxis,
    ChartSeries,
    ChartSpec,
    ChartType,
    DashboardMetadata,
    MetricCard,
    MetricSeverity,
    RiskDashboardSpec,
    TableColumn,
    TableSpec,
)

__all__ = [
    # Enums
    "MetricSeverity",
    "AlertSeverity",
    "ChartType",
    # Metric Cards
    "MetricCard",
    # Tables
    "TableColumn",
    "TableSpec",
    # Charts
    "ChartAxis",
    "ChartSeries",
    "ChartSpec",
    # Alerts
    "Alert",
    # Dashboard
    "DashboardMetadata",
    "RiskDashboardSpec",
]
