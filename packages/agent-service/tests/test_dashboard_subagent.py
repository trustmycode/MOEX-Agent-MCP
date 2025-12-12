"""
Тесты для DashboardSubagent.

Проверяет:
- Формирование RiskDashboardSpec из risk_analytics данных
- Генерацию карточек метрик с корректными severity
- Создание таблиц позиций и стресс-сценариев
- Генерацию алертов по пороговым значениям
- Graceful degradation при отсутствии данных
"""

import pytest
from datetime import datetime

from agent_service.core.context import AgentContext
from agent_service.core.result import SubagentResult
from agent_service.subagents.dashboard import DashboardSubagent
from agent_service.models.dashboard_spec import (
    RiskDashboardSpec,
    MetricSeverity,
    AlertSeverity,
)


@pytest.fixture
def dashboard_subagent() -> DashboardSubagent:
    """Создать экземпляр DashboardSubagent для тестов."""
    return DashboardSubagent()


@pytest.fixture
def sample_risk_data() -> dict:
    """Пример данных от RiskAnalyticsSubagent."""
    return {
        "metadata": {
            "as_of": "2025-12-11T10:00:00Z",
        },
        "portfolio_metrics": {
            "total_return_pct": 11.63,
            "annualized_volatility_pct": 22.5,
            "max_drawdown_pct": -8.7,
        },
        "concentration_metrics": {
            "top1_weight_pct": 18.5,  # Выше порога предупреждения
            "top3_weight_pct": 45.0,
            "top5_weight_pct": 65.0,
            "portfolio_hhi": 1850,
        },
        "var_light": {
            "var_pct": 4.47,
            "confidence_level": 0.95,
            "horizon_days": 1,
        },
        "per_instrument": [
            {
                "ticker": "SBER",
                "weight": 0.185,
                "total_return_pct": 15.2,
                "annualized_volatility_pct": 28.3,
                "max_drawdown_pct": -12.1,
            },
            {
                "ticker": "GAZP",
                "weight": 0.15,
                "total_return_pct": 8.5,
                "annualized_volatility_pct": 25.1,
                "max_drawdown_pct": -10.5,
            },
            {
                "ticker": "LKOH",
                "weight": 0.12,
                "total_return_pct": 12.3,
                "annualized_volatility_pct": 20.8,
                "max_drawdown_pct": -7.2,
            },
        ],
        "stress_results": [
            {
                "id": "oil_crisis",
                "description": "Падение нефти на 30%",
                "pnl_pct": -18.5,
            },
            {
                "id": "market_crash",
                "description": "Обвал рынка 2008",
                "pnl_pct": -35.2,
            },
        ],
    }


@pytest.fixture
def context_with_risk_data(sample_risk_data: dict) -> AgentContext:
    """Создать AgentContext с данными risk_analytics."""
    context = AgentContext(
        user_query="Оцени риск портфеля",
        scenario_type="portfolio_risk_basic",
        user_role="CFO",
    )
    context.add_result("risk_analytics", sample_risk_data)
    context.set_metadata("portfolio_id", "demo-001")
    return context


@pytest.fixture
def context_without_data() -> AgentContext:
    """Создать AgentContext без данных."""
    return AgentContext(
        user_query="Оцени риск портфеля",
        scenario_type="portfolio_risk_basic",
    )


def _get_dashboard(result: SubagentResult) -> RiskDashboardSpec:
    """
    Унифицировано извлечь дашборд из SubagentResult.
    Поддерживает оба контракта: словарь с ключом 'dashboard' и прямой RiskDashboardSpec.
    """
    data = result.data
    if isinstance(data, RiskDashboardSpec):
        return data
    if isinstance(data, dict) and isinstance(data.get("dashboard"), RiskDashboardSpec):
        return data["dashboard"]
    if isinstance(data, dict) and "dashboard" in data:
        return data["dashboard"]  # type: ignore[return-value]
    raise AssertionError("Dashboard not found in result.data")


class TestDashboardSubagentBasic:
    """Базовые тесты DashboardSubagent."""

    def test_subagent_name_and_capabilities(
        self, dashboard_subagent: DashboardSubagent
    ):
        """Проверить имя и возможности сабагента."""
        assert dashboard_subagent.name == "dashboard"
        assert "build_risk_dashboard" in dashboard_subagent.capabilities
        assert "generate_alerts" in dashboard_subagent.capabilities

    @pytest.mark.asyncio
    async def test_execute_with_valid_data(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить успешное выполнение с валидными данными."""
        result = await dashboard_subagent.execute(context_with_risk_data)

        assert result.status == "success"
        assert result.next_agent_hint == "explainer"

        dashboard = _get_dashboard(result)
        assert isinstance(dashboard, RiskDashboardSpec)

    @pytest.mark.asyncio
    async def test_execute_without_data(
        self,
        dashboard_subagent: DashboardSubagent,
        context_without_data: AgentContext,
    ):
        """Проверить graceful degradation без данных."""
        result = await dashboard_subagent.execute(context_without_data)

        assert result.status == "partial"
        assert "недоступны" in result.error_message.lower()

        dashboard = _get_dashboard(result)
        # Должен быть алерт о недоступности данных
        assert len(dashboard.alerts) > 0
        assert any(a.id == "no_data" for a in dashboard.alerts)


class TestDashboardMetricCards:
    """Тесты генерации карточек метрик."""

    @pytest.mark.asyncio
    async def test_portfolio_metrics_cards(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить создание карточек метрик портфеля."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        # Проверяем наличие основных метрик
        metric_ids = [m.id for m in dashboard.metric_cards]

        assert "portfolio_total_return_pct" in metric_ids
        assert "portfolio_annualized_volatility_pct" in metric_ids
        assert "portfolio_max_drawdown_pct" in metric_ids

    @pytest.mark.asyncio
    async def test_concentration_metrics_cards(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить создание карточек концентрации."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        metric_ids = [m.id for m in dashboard.metric_cards]

        assert "top1_weight_pct" in metric_ids
        assert "portfolio_hhi" in metric_ids

    @pytest.mark.asyncio
    async def test_var_metric_card(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить создание карточки VaR."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        var_card = next(
            (m for m in dashboard.metric_cards if m.id == "portfolio_var_light"),
            None,
        )

        assert var_card is not None
        assert "VaR" in var_card.title
        assert "4.47" in var_card.value

    @pytest.mark.asyncio
    async def test_metric_severity_assignment(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить корректное назначение severity для метрик."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        # Концентрация 18.5% > 15% порога — должен быть high
        top1_card = next(
            m for m in dashboard.metric_cards if m.id == "top1_weight_pct"
        )
        assert top1_card.status == MetricSeverity.HIGH

        # VaR 4.47% > 4% warning threshold -> MEDIUM
        var_card = next(
            m for m in dashboard.metric_cards if m.id == "portfolio_var_light"
        )
        assert var_card.status == MetricSeverity.MEDIUM


class TestDashboardTables:
    """Тесты генерации таблиц."""

    @pytest.mark.asyncio
    async def test_positions_table(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить создание таблицы позиций."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        positions_table = next(
            (t for t in dashboard.tables if t.id == "positions"), None
        )

        assert positions_table is not None
        assert positions_table.title == "Позиции портфеля"
        assert len(positions_table.columns) == 5
        assert len(positions_table.rows) == 3  # SBER, GAZP, LKOH

        # Проверяем первую строку (SBER)
        first_row = positions_table.rows[0]
        assert first_row[0] == "SBER"
        assert "18.5" in first_row[1]  # Вес в %

    @pytest.mark.asyncio
    async def test_stress_results_table(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить создание таблицы стресс-сценариев."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        stress_table = next(
            (t for t in dashboard.tables if t.id == "stress_results"), None
        )

        assert stress_table is not None
        assert len(stress_table.rows) == 2  # oil_crisis, market_crash
        assert "oil_crisis" in stress_table.rows[0][0]


class TestDashboardAlerts:
    """Тесты генерации алертов."""

    @pytest.mark.asyncio
    async def test_concentration_alert(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить генерацию алерта по концентрации."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        # Концентрация 18.5% > 15% — должен быть warning алерт
        concentration_alerts = [
            a for a in dashboard.alerts if "concentration" in a.id
        ]
        assert len(concentration_alerts) > 0

        alert = concentration_alerts[0]
        assert alert.severity == AlertSeverity.WARNING
        assert "SBER" in alert.message

    @pytest.mark.asyncio
    async def test_var_alert(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить генерацию алерта по VaR."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        var_alerts = [a for a in dashboard.alerts if "var" in a.id]
        assert len(var_alerts) > 0

        alert = var_alerts[0]
        assert alert.severity == AlertSeverity.WARNING
        assert "VaR" in alert.message

    @pytest.mark.asyncio
    async def test_stress_scenario_alert(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить генерацию алертов по стресс-сценариям."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        # Потери > 15% в стресс-сценарии должны генерировать алерт
        stress_alerts = [a for a in dashboard.alerts if "stress" in a.id]
        # oil_crisis (-18.5%) и market_crash (-35.2%) оба выше порога
        assert len(stress_alerts) == 2

    @pytest.mark.asyncio
    async def test_critical_concentration_alert(
        self, dashboard_subagent: DashboardSubagent
    ):
        """Проверить критический алерт при очень высокой концентрации."""
        context = AgentContext(
            user_query="Оцени риск",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result(
            "risk_analytics",
            {
                "concentration_metrics": {
                    "top1_weight_pct": 30.0,  # > 25% critical threshold
                },
                "per_instrument": [{"ticker": "SBER", "weight": 0.30}],
            },
        )

        result = await dashboard_subagent.execute(context)
        dashboard = _get_dashboard(result)

        critical_alerts = [
            a for a in dashboard.alerts if a.severity == AlertSeverity.CRITICAL
        ]
        assert len(critical_alerts) > 0
        assert any("критическ" in a.message.lower() for a in critical_alerts)


class TestDashboardMetadata:
    """Тесты метаданных дашборда."""

    @pytest.mark.asyncio
    async def test_metadata_from_context(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить заполнение метаданных из контекста."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        assert dashboard.metadata.scenario_type == "portfolio_risk_basic"
        assert dashboard.metadata.base_currency == "RUB"
        assert dashboard.metadata.portfolio_id == "demo-001"

    @pytest.mark.asyncio
    async def test_metadata_as_of_parsing(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить парсинг as_of из данных."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        # as_of должен быть распарсен из "2025-12-11T10:00:00Z"
        assert isinstance(dashboard.metadata.as_of, datetime)


class TestDashboardCharts:
    """Тесты генерации графиков."""

    @pytest.mark.asyncio
    async def test_weights_chart(
        self,
        dashboard_subagent: DashboardSubagent,
        context_with_risk_data: AgentContext,
    ):
        """Проверить создание графика весов."""
        result = await dashboard_subagent.execute(context_with_risk_data)
        dashboard = _get_dashboard(result)

        weights_chart = next(
            (c for c in dashboard.charts if c.id == "weights_by_ticker"), None
        )

        assert weights_chart is not None
        assert weights_chart.type.value == "bar"
        assert weights_chart.x_axis is not None
        assert weights_chart.x_axis.field == "ticker"


class TestDashboardEdgeCases:
    """Тесты граничных случаев."""

    @pytest.mark.asyncio
    async def test_empty_per_instrument(self, dashboard_subagent: DashboardSubagent):
        """Проверить обработку пустого списка инструментов."""
        context = AgentContext(
            user_query="Оцени риск",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result(
            "risk_analytics",
            {
                "portfolio_metrics": {"total_return_pct": 5.0},
                "per_instrument": [],
            },
        )

        result = await dashboard_subagent.execute(context)
        dashboard = _get_dashboard(result)

        # Таблица позиций не должна создаваться
        positions_table = next(
            (t for t in dashboard.tables if t.id == "positions"), None
        )
        assert positions_table is None

    @pytest.mark.asyncio
    async def test_partial_risk_data(self, dashboard_subagent: DashboardSubagent):
        """Проверить обработку частичных данных."""
        context = AgentContext(
            user_query="Оцени риск",
            scenario_type="portfolio_risk_basic",
        )
        context.add_result(
            "risk_analytics",
            {
                "portfolio_metrics": {
                    "total_return_pct": 10.0,
                    # Нет volatility и drawdown
                },
            },
        )

        result = await dashboard_subagent.execute(context)
        dashboard = _get_dashboard(result)

        # Должна быть только карточка доходности
        assert len(dashboard.metric_cards) == 1
        assert dashboard.metric_cards[0].id == "portfolio_total_return_pct"

