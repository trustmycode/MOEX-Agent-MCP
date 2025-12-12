"""
DashboardSubagent — сабагент для формирования RiskDashboardSpec.

Детерминированный маппинг данных из intermediate_results в структурированный
JSON-дашборд для UI/AGI UI. **Не использует LLM** — чисто код.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from ..core.base_subagent import BaseSubagent
from ..core.context import AgentContext
from ..core.result import SubagentResult
from ..models.dashboard_spec import (
    Alert,
    AlertSeverity,
    ChartAxis,
    ChartSeries,
    ChartSpec,
    ChartType,
    DashboardMetadata,
    LayoutItem,
    MetricCard,
    MetricSeverity,
    RiskDashboardSpec,
    TableColumn,
    TableSpec,
    WidgetType,
)

logger = logging.getLogger(__name__)

# Пороговые значения для определения severity
CONCENTRATION_WARNING_THRESHOLD = 15.0  # % — порог предупреждения по концентрации
CONCENTRATION_CRITICAL_THRESHOLD = 25.0  # % — критический порог
VAR_WARNING_THRESHOLD = 4.0  # % — порог предупреждения по VaR
VAR_CRITICAL_THRESHOLD = 6.0  # % — критический порог
VOLATILITY_HIGH_THRESHOLD = 30.0  # % — высокая волатильность
DRAWDOWN_WARNING_THRESHOLD = 10.0  # % — предупреждение по просадке
DRAWDOWN_CRITICAL_THRESHOLD = 20.0  # % — критическая просадка


class DashboardSubagent(BaseSubagent):
    """
    Сабагент для формирования структурированного JSON-дашборда (RiskDashboardSpec).

    **Не использует LLM** — детерминированная логика маппинга данных
    из `context.intermediate_results` в UI-формат.

    Ожидаемые данные в intermediate_results:
        - "risk_analytics" — результат от RiskAnalyticsSubagent
          (portfolio_metrics, per_instrument, concentration_metrics, var_light, stress_results)
        - "market_data" — опционально, данные от MarketDataSubagent

    Returns:
        SubagentResult с data={"dashboard": RiskDashboardSpec}
    """

    def __init__(self) -> None:
        """Инициализация DashboardSubagent."""
        super().__init__(
            name="dashboard",
            description="Формирует структурированный JSON-дашборд риска для UI/AGI UI",
            capabilities=[
                "build_risk_dashboard",
                "map_portfolio_metrics",
                "generate_alerts",
                "create_position_tables",
            ],
        )

    async def execute(self, context: AgentContext) -> SubagentResult:
        """
        Сформировать RiskDashboardSpec на основе данных из context.

        Args:
            context: AgentContext с intermediate_results от других сабагентов.

        Returns:
            SubagentResult с dashboard в data или ошибка.
        """
        logger.info(
            "DashboardSubagent: building dashboard for session %s",
            context.session_id,
        )

        try:
            # Получаем данные от risk_analytics
            risk_data = context.get_result("risk_analytics")
            if not risk_data:
                logger.warning("No risk_analytics data in intermediate_results")
                # Создаём пустой дашборд
                dashboard = self._build_empty_dashboard(context)
                return SubagentResult.partial(
                    data=dashboard,
                    error="Данные risk_analytics недоступны. Дашборд создан с ограничениями.",
                    next_agent_hint="explainer",
                )

            # Строим полный дашборд
            dashboard = self._build_dashboard(context, risk_data)

            logger.info(
                "DashboardSubagent: dashboard built with %d metric_cards, %d tables, %d alerts",
                len(dashboard.metric_cards),
                len(dashboard.tables),
                len(dashboard.alerts),
            )

            return SubagentResult.success(
                data=dashboard,
                next_agent_hint="explainer",
            )

        except Exception as e:
            logger.exception("DashboardSubagent failed: %s", e)
            return SubagentResult.create_error(
                error=f"Ошибка формирования дашборда: {e}"
            )

    def _build_empty_dashboard(self, context: AgentContext) -> RiskDashboardSpec:
        """Создать пустой дашборд с базовыми метаданными."""
        return RiskDashboardSpec(
            metadata=DashboardMetadata(
                as_of=datetime.utcnow(),
                scenario_type=context.scenario_type or "unknown",
                base_currency="RUB",
                portfolio_id=context.get_metadata("portfolio_id"),
            ),
            metric_cards=[],
            tables=[],
            charts=[],
            alerts=[
                Alert(
                    id="no_data",
                    severity=AlertSeverity.WARNING,
                    message="Данные для дашборда недоступны",
                    related_ids=[],
                )
            ],
        )

    def _build_dashboard(
        self, context: AgentContext, risk_data: dict[str, Any]
    ) -> RiskDashboardSpec:
        """
        Построить полный RiskDashboardSpec из данных risk_analytics.

        Args:
            context: AgentContext для метаданных.
            risk_data: Данные от RiskAnalyticsSubagent.

        Returns:
            Заполненный RiskDashboardSpec.
        """
        dashboard = RiskDashboardSpec(
            metadata=self._build_metadata(context, risk_data),
        )

        # 1. Добавляем карточки метрик
        self._add_portfolio_metrics(dashboard, risk_data)
        self._add_concentration_metrics(dashboard, risk_data)
        self._add_var_metrics(dashboard, risk_data)

        # 2. Добавляем таблицы
        self._add_positions_table(dashboard, risk_data)
        self._add_stress_table(dashboard, risk_data)

        # 3. Добавляем графики
        self._add_charts(dashboard, risk_data)

        # 4. Генерируем алерты
        self._generate_alerts(dashboard, risk_data)

        # 5. Собираем data/time_series для data_ref ссылок
        dashboard.data = self._build_data_payload(risk_data)
        dashboard.time_series = self._build_time_series(risk_data)
        if dashboard.time_series:
            dashboard.raw_data = {"time_series": dashboard.time_series}

        # 6. Layout: декларативный список виджетов для AG-UI
        dashboard.layout = self._build_layout(dashboard)

        return dashboard

    def _build_metadata(
        self, context: AgentContext, risk_data: dict[str, Any]
    ) -> DashboardMetadata:
        """Собрать метаданные дашборда."""
        # Пытаемся получить as_of из данных
        metadata = risk_data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        as_of_str = metadata.get("as_of")

        if as_of_str:
            try:
                as_of = datetime.fromisoformat(as_of_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                as_of = datetime.utcnow()
        else:
            as_of = datetime.utcnow()

        return DashboardMetadata(
            as_of=as_of,
            scenario_type=context.scenario_type or "portfolio_risk_basic",
            base_currency=risk_data.get("base_currency", "RUB"),
            portfolio_id=context.get_metadata("portfolio_id"),
        )

    def _add_portfolio_metrics(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить основные метрики портфеля."""
        portfolio_metrics = risk_data.get("portfolio_metrics") or {}
        if not isinstance(portfolio_metrics, dict):
            portfolio_metrics = {}

        # Доходность
        total_return = portfolio_metrics.get("total_return_pct")
        if total_return is not None:
            status = MetricSeverity.INFO
            if total_return < 0:
                status = MetricSeverity.WARNING
            elif total_return > 20:
                status = MetricSeverity.LOW  # Хорошо

            dashboard.add_metric_card(
                id="portfolio_total_return_pct",
                title="Доходность портфеля за период",
                value=total_return,
                unit="%",
                status=status,
            )

        # Волатильность
        volatility = portfolio_metrics.get("annualized_volatility_pct")
        if volatility is not None:
            status = MetricSeverity.INFO
            if volatility > VOLATILITY_HIGH_THRESHOLD:
                status = MetricSeverity.HIGH

            dashboard.add_metric_card(
                id="portfolio_annualized_volatility_pct",
                title="Годовая волатильность",
                value=volatility,
                unit="%",
                status=status,
            )

        # Max Drawdown
        max_drawdown = portfolio_metrics.get("max_drawdown_pct")
        if max_drawdown is not None:
            # Drawdown обычно отрицательный, берём абсолютное значение
            dd_abs = abs(max_drawdown)
            status = MetricSeverity.INFO
            if dd_abs > DRAWDOWN_CRITICAL_THRESHOLD:
                status = MetricSeverity.CRITICAL
            elif dd_abs > DRAWDOWN_WARNING_THRESHOLD:
                status = MetricSeverity.WARNING

            dashboard.add_metric_card(
                id="portfolio_max_drawdown_pct",
                title="Максимальная просадка",
                value=max_drawdown,
                unit="%",
                status=status,
            )

    def _add_concentration_metrics(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить метрики концентрации."""
        concentration = risk_data.get("concentration_metrics") or {}
        if not isinstance(concentration, dict):
            concentration = {}

        # Top-1 концентрация
        top1 = concentration.get("top1_weight_pct")
        if top1 is not None:
            status = self._get_concentration_severity(top1)
            dashboard.add_metric_card(
                id="top1_weight_pct",
                title="Концентрация Top-1",
                value=top1,
                unit="%",
                status=status,
            )

        # Top-3 концентрация
        top3 = concentration.get("top3_weight_pct")
        if top3 is not None:
            dashboard.add_metric_card(
                id="top3_weight_pct",
                title="Концентрация Top-3",
                value=top3,
                unit="%",
                status=MetricSeverity.INFO,
            )

        # HHI
        hhi = concentration.get("portfolio_hhi")
        if hhi is not None:
            status = MetricSeverity.INFO
            if hhi > 2500:  # Высоко концентрированный
                status = MetricSeverity.HIGH
            elif hhi > 1500:  # Умеренно концентрированный
                status = MetricSeverity.MEDIUM

            dashboard.add_metric_card(
                id="portfolio_hhi",
                title="Индекс Херфиндаля-Хиршмана (HHI)",
                value=hhi,
                unit="",
                status=status,
            )

    def _add_var_metrics(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить метрики VaR."""
        # var_light может прийти как None при деградации risk_analytics
        var_light = risk_data.get("var_light") or {}
        if not isinstance(var_light, dict):
            var_light = {}

        var_pct = var_light.get("var_pct")
        if var_pct is not None:
            confidence = var_light.get("confidence_level", 0.95)
            horizon = var_light.get("horizon_days", 1)

            status = MetricSeverity.INFO
            if var_pct > VAR_CRITICAL_THRESHOLD:
                status = MetricSeverity.CRITICAL
            elif var_pct > VAR_WARNING_THRESHOLD:
                status = MetricSeverity.MEDIUM

            dashboard.add_metric_card(
                id="portfolio_var_light",
                title=f"VaR ({int(confidence * 100)}%, {horizon}д)",
                value=var_pct,
                unit="%",
                status=status,
            )

    def _add_positions_table(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить таблицу позиций портфеля."""
        per_instrument = risk_data.get("per_instrument", [])
        if not per_instrument:
            return

        columns = [
            ("ticker", "Тикер"),
            ("weight_pct", "Вес, %"),
            ("total_return_pct", "Доходность, %"),
            ("annualized_volatility_pct", "Волатильность, %"),
            ("max_drawdown_pct", "Max DD, %"),
        ]

        rows = []
        for instr in per_instrument:
            weight_raw = instr.get("weight")
            try:
                weight = float(weight_raw) * 100  # Конвертируем в проценты
            except (TypeError, ValueError):
                weight = 0.0
            row = [
                str(instr.get("ticker", "")),
                f"{weight:.1f}",
                f"{float(instr.get('total_return_pct') or 0):.2f}",
                f"{float(instr.get('annualized_volatility_pct') or 0):.2f}",
                f"{float(instr.get('max_drawdown_pct') or 0):.2f}",
            ]
            rows.append(row)

        dashboard.add_table(
            id="positions",
            title="Позиции портфеля",
            columns=columns,
            rows=rows,
            data_ref="data.per_instrument",
        )

    def _add_stress_table(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить таблицу результатов стресс-тестов."""
        stress_results = risk_data.get("stress_results", [])
        if not stress_results:
            return

        columns = [
            ("id", "Сценарий"),
            ("description", "Описание"),
            ("pnl_pct", "P&L, %"),
        ]

        rows = []
        for stress in stress_results:
            row = [
                str(stress.get("id", "")),
                str(stress.get("description", "")),
                f"{float(stress.get('pnl_pct') or 0):.2f}",
            ]
            rows.append(row)

        dashboard.add_table(
            id="stress_results",
            title="Результаты стресс-сценариев",
            columns=columns,
            rows=rows,
            data_ref="data.stress_results",
        )

    def _add_charts(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить графики на дашборд."""
        # График структуры портфеля по весам
        per_instrument = risk_data.get("per_instrument", [])
        if per_instrument:
            dashboard.charts.append(
                ChartSpec(
                    id="weights_by_ticker",
                    type=ChartType.BAR,
                    title="Структура портфеля по бумагам",
                    x_axis=ChartAxis(field="ticker", label="Тикер"),
                    y_axis=ChartAxis(field="weight_pct", label="Вес, %"),
                    series=[
                        ChartSeries(
                            id="weights",
                            label="Вес бумаги",
                            data_ref="data.per_instrument",
                        )
                    ],
                )
            )

        # Добавляем ссылку на equity curve, если есть time_series
        time_series = risk_data.get("time_series") or {}
        if not isinstance(time_series, dict):
            time_series = {}
        if time_series.get("portfolio_value"):
            dashboard.charts.append(
                ChartSpec(
                    id="equity_curve",
                    type=ChartType.LINE,
                    title="Динамика стоимости портфеля",
                    x_axis=ChartAxis(field="date", label="Дата"),
                    y_axis=ChartAxis(field="value", label="Стоимость"),
                    series=[
                        ChartSeries(
                            id="portfolio",
                            label="Портфель",
                            data_ref="time_series.portfolio_value",
                        )
                    ],
                )
            )
            # Сохраняем raw_data для фронтенда
            dashboard.raw_data = {"time_series": time_series}

    def _generate_alerts(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Генерировать алерты на основе метрик."""
        concentration = risk_data.get("concentration_metrics") or {}
        if not isinstance(concentration, dict):
            concentration = {}
        var_light = risk_data.get("var_light") or {}
        if not isinstance(var_light, dict):
            var_light = {}
        portfolio_metrics = risk_data.get("portfolio_metrics") or {}
        if not isinstance(portfolio_metrics, dict):
            portfolio_metrics = {}

        # Алерт по концентрации Top-1
        top1 = concentration.get("top1_weight_pct")
        if top1 is not None:
            if top1 > CONCENTRATION_CRITICAL_THRESHOLD:
                # Находим тикер с максимальным весом
                top_ticker = self._get_top_ticker(risk_data)
                dashboard.add_alert(
                    id="issuer_concentration_critical",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Критическая концентрация: {top_ticker} составляет {top1:.1f}% портфеля (лимит {CONCENTRATION_CRITICAL_THRESHOLD}%).",
                    related_ids=[f"ticker:{top_ticker}", "metric:top1_weight_pct"],
                )
            elif top1 > CONCENTRATION_WARNING_THRESHOLD:
                top_ticker = self._get_top_ticker(risk_data)
                dashboard.add_alert(
                    id="issuer_concentration_warning",
                    severity=AlertSeverity.WARNING,
                    message=f"Концентрация по эмитенту {top_ticker} превышает лимит {CONCENTRATION_WARNING_THRESHOLD}%.",
                    related_ids=[f"ticker:{top_ticker}", "metric:top1_weight_pct"],
                )

        # Алерт по VaR
        var_pct = var_light.get("var_pct")
        if var_pct is not None:
            if var_pct > VAR_CRITICAL_THRESHOLD:
                dashboard.add_alert(
                    id="var_limit_exceeded",
                    severity=AlertSeverity.CRITICAL,
                    message=f"VaR {var_pct:.1f}% превышает критический лимит {VAR_CRITICAL_THRESHOLD}%.",
                    related_ids=["metric:portfolio_var_light"],
                )
            elif var_pct > VAR_WARNING_THRESHOLD:
                dashboard.add_alert(
                    id="var_limit_near",
                    severity=AlertSeverity.WARNING,
                    message=f"VaR {var_pct:.1f}% близок к установленному лимиту {VAR_CRITICAL_THRESHOLD}%.",
                    related_ids=["metric:portfolio_var_light"],
                )

        # Алерт по просадке
        max_drawdown = portfolio_metrics.get("max_drawdown_pct")
        if max_drawdown is not None:
            dd_abs = abs(max_drawdown)
            if dd_abs > DRAWDOWN_CRITICAL_THRESHOLD:
                dashboard.add_alert(
                    id="drawdown_critical",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Максимальная просадка {dd_abs:.1f}% превышает критический порог {DRAWDOWN_CRITICAL_THRESHOLD}%.",
                    related_ids=["metric:portfolio_max_drawdown_pct"],
                )

        # Алерт по стресс-сценариям
        stress_results = risk_data.get("stress_results", [])
        for stress in stress_results:
            pnl_pct = stress.get("pnl_pct", 0)
            if pnl_pct < -15:  # Потери более 15% при стрессе
                dashboard.add_alert(
                    id=f"stress_loss_{stress.get('id', 'unknown')}",
                    severity=AlertSeverity.WARNING,
                    message=f"Стресс-сценарий '{stress.get('description', stress.get('id'))}': потери {abs(pnl_pct):.1f}%.",
                    related_ids=[f"stress:{stress.get('id')}"],
                )

    def _build_data_payload(self, risk_data: dict[str, Any]) -> dict[str, Any]:
        """Сформировать словарь data/time_series для data_ref ссылок на фронте."""
        data: dict[str, Any] = {}

        per_instrument = risk_data.get("per_instrument") or []
        normalized_instr: list[dict[str, Any]] = []
        for instr in per_instrument:
            if not isinstance(instr, dict):
                continue
            weight_pct = instr.get("weight_pct")
            if weight_pct is None:
                raw_weight = instr.get("weight")
                weight_pct = float(raw_weight) * 100 if raw_weight is not None else None

            normalized_instr.append(
                {
                    "ticker": instr.get("ticker"),
                    "weight_pct": weight_pct,
                    "total_return_pct": instr.get("total_return_pct"),
                    "annualized_volatility_pct": instr.get("annualized_volatility_pct"),
                    "max_drawdown_pct": instr.get("max_drawdown_pct"),
                }
            )

        if normalized_instr:
            data["per_instrument"] = normalized_instr

        stress_results = risk_data.get("stress_results") or []
        normalized_stress: list[dict[str, Any]] = []
        for stress in stress_results:
            if not isinstance(stress, dict):
                continue
            normalized_stress.append(
                {
                    "id": stress.get("id"),
                    "description": stress.get("description"),
                    "pnl_pct": stress.get("pnl_pct"),
                }
            )
        if normalized_stress:
            data["stress_results"] = normalized_stress

        return data

    def _build_time_series(self, risk_data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        """Извлечь временные ряды в безопасном формате."""
        ts = risk_data.get("time_series")
        if isinstance(ts, dict):
            return {k: v for k, v in ts.items() if isinstance(v, list)}
        return {}

    def _build_layout(self, dashboard: RiskDashboardSpec) -> list[LayoutItem]:
        """Построить декларативный layout для рендерера."""
        layout: list[LayoutItem] = []

        if dashboard.metrics:
            layout.append(
                LayoutItem(
                    id="kpi_grid",
                    type=WidgetType.KPI_GRID,
                    title="Ключевые метрики",
                    metric_ids=[metric.id for metric in dashboard.metrics],
                    columns=3,
                )
            )

        if dashboard.alerts:
            layout.append(
                LayoutItem(
                    id="alerts",
                    type=WidgetType.ALERT_LIST,
                    title="Предупреждения",
                    alert_ids=[alert.id for alert in dashboard.alerts],
                )
            )

        for chart in dashboard.charts:
            layout.append(
                LayoutItem(
                    id=f"chart_{chart.id}",
                    type=WidgetType.CHART,
                    title=chart.title,
                    chart_id=chart.id,
                )
            )

        for table in dashboard.tables:
            layout.append(
                LayoutItem(
                    id=f"table_{table.id}",
                    type=WidgetType.TABLE,
                    title=table.title,
                    table_id=table.id,
                )
            )

        return layout

    def _get_concentration_severity(self, concentration_pct: float) -> MetricSeverity:
        """Определить severity для метрики концентрации."""
        if concentration_pct > CONCENTRATION_CRITICAL_THRESHOLD:
            return MetricSeverity.CRITICAL
        elif concentration_pct > CONCENTRATION_WARNING_THRESHOLD:
            return MetricSeverity.HIGH
        elif concentration_pct > 10:
            return MetricSeverity.MEDIUM
        return MetricSeverity.INFO

    def _get_top_ticker(self, risk_data: dict[str, Any]) -> str:
        """Получить тикер с максимальным весом."""
        per_instrument = risk_data.get("per_instrument", [])
        if not per_instrument:
            return "Unknown"

        max_weight = 0
        top_ticker = "Unknown"
        for instr in per_instrument:
            weight = instr.get("weight", 0)
            if weight > max_weight:
                max_weight = weight
                top_ticker = instr.get("ticker", "Unknown")

        return top_ticker

