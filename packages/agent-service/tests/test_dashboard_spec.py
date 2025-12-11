"""
Тесты для моделей RiskDashboardSpec.

Проверяет:
- Создание и валидацию всех компонентов дашборда
- Вспомогательные методы добавления элементов
- Сериализацию в JSON
- Значения по умолчанию
"""

import pytest
from datetime import datetime
import json

from agent_service.models.dashboard_spec import (
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


class TestMetricCard:
    """Тесты для MetricCard."""

    def test_create_metric_card(self):
        """Проверить создание карточки метрики."""
        card = MetricCard(
            id="portfolio_return",
            title="Доходность портфеля",
            value="11.63%",
            status=MetricSeverity.INFO,
        )

        assert card.id == "portfolio_return"
        assert card.title == "Доходность портфеля"
        assert card.value == "11.63%"
        assert card.status == MetricSeverity.INFO
        assert card.change is None

    def test_metric_card_with_change(self):
        """Проверить карточку с изменением."""
        card = MetricCard(
            id="volatility",
            title="Волатильность",
            value="22.5%",
            change="+2.1%",
            status=MetricSeverity.MEDIUM,
        )

        assert card.change == "+2.1%"
        assert card.status == MetricSeverity.MEDIUM


class TestTableSpec:
    """Тесты для TableSpec."""

    def test_create_table(self):
        """Проверить создание таблицы."""
        table = TableSpec(
            id="positions",
            title="Позиции портфеля",
            columns=[
                TableColumn(id="ticker", label="Тикер"),
                TableColumn(id="weight", label="Вес, %"),
            ],
            rows=[
                ["SBER", "25.0"],
                ["GAZP", "20.0"],
            ],
            data_ref="data.per_instrument",
        )

        assert table.id == "positions"
        assert len(table.columns) == 2
        assert len(table.rows) == 2
        assert table.data_ref == "data.per_instrument"

    def test_empty_table(self):
        """Проверить создание пустой таблицы."""
        table = TableSpec(id="empty", title="Empty Table")

        assert table.columns == []
        assert table.rows == []
        assert table.data_ref is None


class TestChartSpec:
    """Тесты для ChartSpec."""

    def test_create_line_chart(self):
        """Проверить создание линейного графика."""
        chart = ChartSpec(
            id="equity_curve",
            type=ChartType.LINE,
            title="Динамика стоимости",
            x_axis=ChartAxis(field="date", label="Дата"),
            y_axis=ChartAxis(field="value", label="Стоимость"),
            series=[
                ChartSeries(
                    id="portfolio",
                    label="Портфель",
                    data_ref="time_series.portfolio",
                )
            ],
        )

        assert chart.type == ChartType.LINE
        assert chart.x_axis.field == "date"
        assert len(chart.series) == 1

    def test_create_bar_chart(self):
        """Проверить создание столбчатого графика."""
        chart = ChartSpec(
            id="weights",
            type=ChartType.BAR,
            title="Структура портфеля",
        )

        assert chart.type == ChartType.BAR


class TestAlert:
    """Тесты для Alert."""

    def test_create_warning_alert(self):
        """Проверить создание предупреждения."""
        alert = Alert(
            id="concentration_warning",
            severity=AlertSeverity.WARNING,
            message="Концентрация по SBER превышает 15%",
            related_ids=["ticker:SBER", "metric:top1_weight"],
        )

        assert alert.severity == AlertSeverity.WARNING
        assert "SBER" in alert.message
        assert len(alert.related_ids) == 2

    def test_create_critical_alert(self):
        """Проверить создание критического алерта."""
        alert = Alert(
            id="var_exceeded",
            severity=AlertSeverity.CRITICAL,
            message="VaR превышает лимит",
        )

        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.related_ids == []


class TestDashboardMetadata:
    """Тесты для DashboardMetadata."""

    def test_default_metadata(self):
        """Проверить значения по умолчанию."""
        metadata = DashboardMetadata()

        assert isinstance(metadata.as_of, datetime)
        assert metadata.scenario_type == "portfolio_risk_basic"
        assert metadata.base_currency == "RUB"
        assert metadata.portfolio_id is None

    def test_custom_metadata(self):
        """Проверить пользовательские значения."""
        metadata = DashboardMetadata(
            scenario_type="index_risk_scan",
            base_currency="USD",
            portfolio_id="demo-001",
        )

        assert metadata.scenario_type == "index_risk_scan"
        assert metadata.base_currency == "USD"
        assert metadata.portfolio_id == "demo-001"


class TestRiskDashboardSpec:
    """Тесты для RiskDashboardSpec."""

    def test_create_empty_dashboard(self):
        """Проверить создание пустого дашборда."""
        dashboard = RiskDashboardSpec()

        assert dashboard.metadata is not None
        assert dashboard.metric_cards == []
        assert dashboard.tables == []
        assert dashboard.charts == []
        assert dashboard.alerts == []
        assert dashboard.raw_data is None

    def test_add_metric_card_method(self):
        """Проверить метод add_metric_card."""
        dashboard = RiskDashboardSpec()

        card = dashboard.add_metric_card(
            id="return",
            title="Доходность",
            value=11.63,
            unit="%",
            status=MetricSeverity.INFO,
        )

        assert len(dashboard.metric_cards) == 1
        assert card.id == "return"
        assert card.value == "11.63%"

    def test_add_metric_card_string_value(self):
        """Проверить add_metric_card со строковым значением."""
        dashboard = RiskDashboardSpec()

        card = dashboard.add_metric_card(
            id="hhi",
            title="HHI",
            value="1850",
            unit="",
        )

        assert card.value == "1850"

    def test_add_alert_method(self):
        """Проверить метод add_alert."""
        dashboard = RiskDashboardSpec()

        alert = dashboard.add_alert(
            id="warning",
            severity=AlertSeverity.WARNING,
            message="Test warning",
            related_ids=["metric:test"],
        )

        assert len(dashboard.alerts) == 1
        assert alert.message == "Test warning"

    def test_add_table_method(self):
        """Проверить метод add_table."""
        dashboard = RiskDashboardSpec()

        table = dashboard.add_table(
            id="positions",
            title="Позиции",
            columns=[("ticker", "Тикер"), ("weight", "Вес")],
            rows=[["SBER", "25%"]],
            data_ref="data.positions",
        )

        assert len(dashboard.tables) == 1
        assert table.columns[0].id == "ticker"
        assert table.columns[0].label == "Тикер"

    def test_json_serialization(self):
        """Проверить сериализацию в JSON."""
        dashboard = RiskDashboardSpec()
        dashboard.add_metric_card(
            id="return",
            title="Доходность",
            value=10.5,
            unit="%",
        )
        dashboard.add_alert(
            id="test",
            severity=AlertSeverity.INFO,
            message="Test",
        )

        json_str = dashboard.model_dump_json()
        data = json.loads(json_str)

        assert "metadata" in data
        assert "metric_cards" in data
        assert len(data["metric_cards"]) == 1
        assert data["metric_cards"][0]["value"] == "10.50%"

    def test_full_dashboard_structure(self):
        """Проверить полную структуру дашборда."""
        dashboard = RiskDashboardSpec(
            metadata=DashboardMetadata(
                scenario_type="portfolio_risk_basic",
                portfolio_id="demo",
            )
        )

        # Добавляем все типы элементов
        dashboard.add_metric_card(
            id="return",
            title="Доходность",
            value=11.63,
            unit="%",
            status=MetricSeverity.INFO,
        )

        dashboard.add_table(
            id="positions",
            title="Позиции",
            columns=[("ticker", "Тикер")],
            rows=[["SBER"]],
        )

        dashboard.charts.append(
            ChartSpec(
                id="weights",
                type=ChartType.BAR,
                title="Веса",
            )
        )

        dashboard.add_alert(
            id="warning",
            severity=AlertSeverity.WARNING,
            message="Warning message",
        )

        dashboard.raw_data = {"time_series": {"portfolio_value": []}}

        # Проверяем все поля
        assert len(dashboard.metric_cards) == 1
        assert len(dashboard.tables) == 1
        assert len(dashboard.charts) == 1
        assert len(dashboard.alerts) == 1
        assert dashboard.raw_data is not None


class TestEnums:
    """Тесты для перечислений."""

    def test_metric_severity_values(self):
        """Проверить значения MetricSeverity."""
        assert MetricSeverity.INFO.value == "info"
        assert MetricSeverity.LOW.value == "low"
        assert MetricSeverity.MEDIUM.value == "medium"
        assert MetricSeverity.HIGH.value == "high"
        assert MetricSeverity.CRITICAL.value == "critical"

    def test_alert_severity_values(self):
        """Проверить значения AlertSeverity."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_chart_type_values(self):
        """Проверить значения ChartType."""
        assert ChartType.LINE.value == "line"
        assert ChartType.BAR.value == "bar"
        assert ChartType.PIE.value == "pie"
        assert ChartType.HEATMAP.value == "heatmap"
