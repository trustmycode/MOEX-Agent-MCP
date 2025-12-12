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
    LayoutItem,
    Metric,
    MetricCard,
    MetricSeverity,
    RiskDashboardSpec,
    TableColumn,
    TableSpec,
    WidgetType,
)

__all__ = [
    # Enums
    "MetricSeverity",
    "AlertSeverity",
    "ChartType",
    "WidgetType",
    # Metric Cards
    "MetricCard",
    "Metric",
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
    "LayoutItem",
    "RiskDashboardSpec",
]

