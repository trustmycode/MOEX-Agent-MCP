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
CORRELATION_WARNING_THRESHOLD = 0.7  # сильные корреляции
CORRELATION_CRITICAL_THRESHOLD = 0.9  # очень сильные корреляции


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
                self._log_inputs(risk_data, context)
                # Создаём пустой дашборд
                dashboard = self._build_empty_dashboard(context)
                self._log_outputs(dashboard, context, risk_data)
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
            self._log_outputs(dashboard, context, risk_data)

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
        market_data = context.get_result("market_data") or {}
        dashboard = RiskDashboardSpec(
            metadata=self._build_metadata(context, risk_data),
        )

        # Если есть данные ребалансировки — обработать первым, чтобы не показывать "нет данных"
        has_rebalance = self._add_rebalance_blocks(dashboard, risk_data)

        # 1. Добавляем карточки метрик
        self._add_portfolio_metrics(dashboard, risk_data)
        self._add_concentration_metrics(dashboard, risk_data)
        self._add_var_metrics(dashboard, risk_data)
        self._add_cfo_metrics(dashboard, risk_data)

        # 2. Добавляем таблицы
        self._add_positions_table(dashboard, risk_data)
        self._add_stress_table(dashboard, risk_data)
        self._add_cfo_tables(dashboard, risk_data)
        self._add_correlation_views(dashboard, risk_data)
        self._add_tail_table(dashboard, risk_data)
        self._add_market_compare_table(dashboard, market_data)

        # 3. Добавляем графики
        self._add_charts(dashboard, risk_data, market_data)

        # 4. Генерируем алерты
        self._generate_alerts(dashboard, risk_data, market_data)

        # 5. Собираем data/time_series для data_ref ссылок
        dashboard.data = self._build_data_payload(risk_data, market_data)
        dashboard.time_series = self._build_time_series(risk_data, market_data)
        if dashboard.time_series:
            dashboard.raw_data = {"time_series": dashboard.time_series}

        # 6. Layout: декларативный список виджетов для AG-UI
        has_content = bool(
            dashboard.metric_cards
            or dashboard.metrics
            or dashboard.tables
            or dashboard.charts
            or dashboard.alerts
            or has_rebalance
        )

        fallback_message = None
        if not has_content:
            message_candidate = (
                risk_data.get("message") if isinstance(risk_data, dict) else None
            )
            fallback_message = (
                str(message_candidate)
                if message_candidate
                else "Данные для дашборда недоступны"
            )
            dashboard.add_alert(
                id="no_data",
                severity=AlertSeverity.WARNING,
                message=fallback_message,
                related_ids=[],
            )

        dashboard.layout = self._build_layout(dashboard)
        if fallback_message:
            dashboard.layout.append(
                LayoutItem(
                    id="no_data_text",
                    type=WidgetType.TEXT,
                    title="Описание",
                    description=fallback_message,
                )
            )

        return dashboard

    def _add_rebalance_blocks(self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]) -> bool:
        """Обработать результат suggest_rebalance: target_weights, trades, summary."""
        rebalance_block = risk_data.get("rebalance_proposal") or {}
        target_weights = rebalance_block.get("target_weights") or risk_data.get("target_weights")
        trades = rebalance_block.get("trades") or risk_data.get("trades")
        summary = rebalance_block.get("summary") or risk_data.get("summary")

        has_data = bool(target_weights) or bool(trades) or bool(summary)
        if not has_data:
            return False

        # Таблица целевых весов
        if isinstance(target_weights, dict) and target_weights:
            rows = []
            for ticker, weight in target_weights.items():
                try:
                    pct = float(weight) * 100
                except Exception:
                    pct = 0.0
                rows.append([str(ticker), f"{pct:.2f}"])
            dashboard.add_table(
                id="rebalance_target_weights",
                title="Целевые веса после ребалансировки",
                columns=[("ticker", "Тикер"), ("weight_pct", "Вес, %")],
                rows=rows,
                data_ref="data.rebalance.target_weights",
            )

        # Таблица сделок
        if isinstance(trades, list) and trades:
            rows = []
            for trade in trades:
                if not isinstance(trade, dict):
                    continue
                rows.append(
                    [
                        str(trade.get("ticker", "")),
                        str(trade.get("side", "")),
                        self._format_percent(trade.get("weight_delta")),
                        self._format_percent(trade.get("target_weight")),
                        self._format_currency(trade.get("estimated_value")),
                        str(trade.get("reason", "")),
                    ]
                )
            dashboard.add_table(
                id="rebalance_trades",
                title="Предложенные сделки",
                columns=[
                    ("ticker", "Тикер"),
                    ("side", "Сторона"),
                    ("weight_delta", "Δ вес, %"),
                    ("target_weight", "Целевой вес, %"),
                    ("estimated_value", "Оценка, ₽"),
                    ("reason", "Причина"),
                ],
                rows=rows,
                data_ref="data.rebalance.trades",
            )

        # Карточки из summary
        if isinstance(summary, dict) and summary:
            total_turnover = summary.get("total_turnover")
            turnover_within_limit = summary.get("turnover_within_limit")
            positions_changed = summary.get("positions_changed")
            warnings = summary.get("warnings") or []

            if total_turnover is not None:
                dashboard.add_metric_card(
                    id="rebalance_total_turnover",
                    title="Оборот ребалансировки",
                    value=total_turnover * 100 if isinstance(total_turnover, (int, float)) else total_turnover,
                    unit="%",
                    status=MetricSeverity.INFO,
                )
            if turnover_within_limit is not None:
                dashboard.add_metric_card(
                    id="rebalance_turnover_within_limit",
                    title="Turnover в лимите",
                    value="Да" if turnover_within_limit else "Нет",
                    unit="",
                    status=MetricSeverity.INFO if turnover_within_limit else MetricSeverity.WARNING,
                )
            if positions_changed is not None:
                dashboard.add_metric_card(
                    id="rebalance_positions_changed",
                    title="Позиции с изменениями",
                    value=positions_changed,
                    unit="",
                    status=MetricSeverity.INFO,
                )
            if warnings:
                dashboard.add_metric_card(
                    id="rebalance_warnings",
                    title="Предупреждения при ребалансировке",
                    value=len(warnings),
                    unit="",
                    status=MetricSeverity.WARNING,
                )

        # Расширяем data payload
        rebalance_block_out: dict[str, Any] = {}
        if isinstance(target_weights, dict):
            rebalance_block_out["target_weights"] = target_weights
        if isinstance(trades, list):
            rebalance_block_out["trades"] = trades
        if isinstance(summary, dict):
            rebalance_block_out["summary"] = summary

        # если пришло как rebalance_proposal — сохраняем исходное
        if rebalance_block:
            rebalance_block_out.setdefault("raw", rebalance_block)

        if rebalance_block_out:
            dashboard.data["rebalance"] = rebalance_block_out

        return True

    def _log_inputs(self, risk_data: Any, context: AgentContext) -> None:
        """Логируем, что пришло на вход дашборду (только агрегаты, без больших payload)."""
        rd = risk_data if isinstance(risk_data, dict) else {}
        summary = {
            "session": context.session_id,
            "scenario": context.scenario_type,
            "risk_keys": sorted(rd.keys()) if isinstance(rd, dict) else str(type(risk_data)),
            "per_instrument_len": len(rd.get("per_instrument", [])) if isinstance(rd, dict) else 0,
            "stress_len": len(rd.get("stress_results", [])) if isinstance(rd, dict) else 0,
            "rebalance_keys": list((rd.get("rebalance_proposal") or {}).keys()) if isinstance(rd, dict) else [],
        }
        logger.info("DashboardSubagent: inputs summary %s", summary)

    def _log_outputs(
        self,
        dashboard: RiskDashboardSpec,
        context: AgentContext,
        risk_data: Any = None,
    ) -> None:
        """Логируем агрегаты итогового дашборда."""
        data_keys = list(dashboard.data.keys()) if isinstance(dashboard.data, dict) else []
        summary = {
            "session": context.session_id,
            "scenario": context.scenario_type,
            "metric_cards": len(dashboard.metric_cards),
            "tables": len(dashboard.tables),
            "charts": len(dashboard.charts),
            "alerts": len(dashboard.alerts),
            "data_keys": data_keys,
        }
        logger.info("DashboardSubagent: output summary %s", summary)

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

    def _add_cfo_metrics(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить CFO-метрики ликвидности/стоимости портфеля."""
        cfo_report = risk_data.get("cfo_report")
        if not isinstance(cfo_report, dict):
            return

        metadata = cfo_report.get("metadata") or {}
        liquidity_profile = cfo_report.get("liquidity_profile") or {}
        covenant_limits = (
            metadata.get("covenant_limits")
            or cfo_report.get("covenant_limits")
            or {}
        )

        min_liq_ratio = covenant_limits.get("min_liquidity_ratio")
        limit_pct = float(min_liq_ratio) * 100 if min_liq_ratio is not None else None

        short_term_ratio = liquidity_profile.get("short_term_ratio_pct")
        if short_term_ratio is not None:
            status = MetricSeverity.INFO
            if limit_pct is not None and short_term_ratio < limit_pct:
                status = MetricSeverity.CRITICAL
            dashboard.add_metric_card(
                id="cfo_liquidity_ratio_pct",
                title="Коэффициент ликвидности (0-30д)",
                value=short_term_ratio,
                unit="%",
                status=status,
            )

        quick_ratio = liquidity_profile.get("quick_ratio_pct")
        if quick_ratio is not None:
            status = MetricSeverity.INFO
            if quick_ratio < 10:
                status = MetricSeverity.CRITICAL
            elif quick_ratio < 20:
                status = MetricSeverity.WARNING
            dashboard.add_metric_card(
                id="cfo_quick_ratio_pct",
                title="Доля высоколиквидных активов (0-7д)",
                value=quick_ratio,
                unit="%",
                status=status,
            )

        total_value = metadata.get("total_portfolio_value")
        if total_value is not None:
            dashboard.add_metric_card(
                id="cfo_portfolio_value_before",
                title="Стоимость портфеля (до стресса)",
                value=self._format_currency(total_value),
                unit="",
                status=MetricSeverity.INFO,
            )

            worst_after = self._compute_worst_stress_value(
                total_value, cfo_report.get("stress_scenarios")
            )
            if worst_after is not None:
                worst_pct = self._compute_worst_pnl_pct(cfo_report.get("stress_scenarios"))
                status = MetricSeverity.INFO
                if worst_pct is not None:
                    if worst_pct < -20:
                        status = MetricSeverity.CRITICAL
                    elif worst_pct < -10:
                        status = MetricSeverity.WARNING
                dashboard.add_metric_card(
                    id="cfo_portfolio_value_after",
                    title="Стоимость портфеля (худший стресс)",
                    value=self._format_currency(worst_after),
                    unit="",
                    status=status,
                    change=f"{worst_pct:.2f}" if worst_pct is not None else None,
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

    def _add_cfo_tables(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить CFO-таблицы (ликвидность и стресс-сценарии)."""
        cfo_report = risk_data.get("cfo_report")
        if not isinstance(cfo_report, dict):
            return

        liquidity_profile = cfo_report.get("liquidity_profile") or {}
        buckets = liquidity_profile.get("buckets") or []
        bucket_order = {"0-7d": 0, "8-30d": 1, "31-90d": 2, "90d+": 3}

        if buckets:
            sorted_buckets = sorted(
                [b for b in buckets if isinstance(b, dict)],
                key=lambda b: bucket_order.get(b.get("bucket"), 99),
            )
            rows = []
            for bucket in sorted_buckets:
                rows.append(
                    [
                        str(bucket.get("bucket", "")),
                        self._format_percent(bucket.get("weight_pct")),
                        self._format_currency(bucket.get("value")),
                        ", ".join(sorted(bucket.get("tickers", []))) if bucket.get("tickers") else "нет данных",
                    ]
                )
            dashboard.add_table(
                id="cfo_liquidity_buckets",
                title="Корзины ликвидности",
                columns=[
                    ("bucket", "Корзина"),
                    ("weight_pct", "Доля, %"),
                    ("value", "Стоимость"),
                    ("tickers", "Тикеры"),
                ],
                rows=rows,
                data_ref="data.cfo_report.liquidity_profile.buckets",
            )

        stress_scenarios = cfo_report.get("stress_scenarios") or []
        if stress_scenarios:
            sorted_stress = sorted(
                [s for s in stress_scenarios if isinstance(s, dict)],
                key=lambda s: str(s.get("id", "")),
            )
            rows = []
            for scenario in sorted_stress:
                breaches = scenario.get("covenant_breaches") or []
                breach_codes = ", ".join(
                    sorted({b.get("code") for b in breaches if isinstance(b, dict) and b.get("code")})
                ) or "нет"
                rows.append(
                    [
                        str(scenario.get("id", "")),
                        self._format_percent(scenario.get("pnl_pct")),
                        self._format_percent(scenario.get("liquidity_ratio_after")),
                        breach_codes,
                    ]
                )

            dashboard.add_table(
                id="cfo_liquidity_stress",
                title="Стресс-сценарии ликвидности",
                columns=[
                    ("id", "Сценарий"),
                    ("pnl_pct", "P&L, %"),
                    ("liquidity_ratio_after", "Ликвидн., %"),
                    ("covenant_breaches", "Ковенанты"),
                ],
                rows=rows,
                data_ref="data.cfo_report.stress_scenarios",
            )

    def _add_correlation_views(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить таблицу/график корреляций."""
        normalized = self._normalize_correlation_data(risk_data.get("correlation_matrix"))
        if not normalized:
            return

        tickers = normalized["tickers"]
        matrix = normalized["matrix"]

        columns = [("ticker", "Тикер")] + [(t, t) for t in tickers]
        rows: list[list[str]] = []
        for i, ticker in enumerate(tickers):
            row = [ticker]
            for j in range(len(tickers)):
                row.append(self._format_corr_value(matrix[i][j]))
            rows.append(row)

        dashboard.add_table(
            id="correlation_matrix",
            title="Матрица корреляций",
            columns=columns,
            rows=rows,
            data_ref="data.correlation_matrix",
        )

        dashboard.charts.append(
            ChartSpec(
                id="correlation_heatmap",
                type=ChartType.HEATMAP,
                title="Корреляции бумаг",
                x_axis=ChartAxis(field="ticker_x", label="Тикер X"),
                y_axis=ChartAxis(field="ticker_y", label="Тикер Y"),
                series=[
                    ChartSeries(
                        id="correlation_matrix",
                        label="Корреляции",
                        data_ref="data.correlation_matrix",
                    )
                ],
            )
        )

    def _add_tail_table(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Добавить таблицу хвоста индекса (Bottom-N)."""
        scenario = risk_data.get("scenario")
        has_tail = scenario == "index_tail_analysis" or risk_data.get("tail_constituents")
        per_instrument = risk_data.get("per_instrument") or []
        if not has_tail or not per_instrument:
            return

        normalized = self._normalize_per_instrument(per_instrument, weight_from_fraction=True)
        sorted_rows = sorted(
            normalized,
            key=lambda x: x.get("weight_pct") or 0,
            reverse=True,
        )

        rows: list[list[str]] = []
        for instr in sorted_rows:
            rows.append(
                [
                    str(instr.get("ticker", "")),
                    self._format_percent(instr.get("weight_pct")),
                    self._format_percent(instr.get("total_return_pct")),
                    self._format_percent(instr.get("annualized_volatility_pct")),
                    self._format_percent(instr.get("max_drawdown_pct")),
                ]
            )

        dashboard.add_table(
            id="index_tail_bottom",
            title="Bottom-N индекса",
            columns=[
                ("ticker", "Тикер"),
                ("weight_pct", "Вес, %"),
                ("total_return_pct", "Доходность, %"),
                ("annualized_volatility_pct", "Волатильность, %"),
                ("max_drawdown_pct", "Max DD, %"),
            ],
            rows=rows,
            data_ref="data.index_tail.per_instrument",
        )

    def _add_market_compare_table(
        self, dashboard: RiskDashboardSpec, market_data: dict[str, Any]
    ) -> None:
        """Добавить таблицу сравнения тикеров из market_data."""
        if not isinstance(market_data, dict):
            return

        securities_raw = market_data.get("securities")
        if not securities_raw and market_data.get("ticker"):
            ticker = market_data.get("ticker")
            securities_raw = {
                ticker: {
                    "snapshot": market_data.get("snapshot"),
                    "ohlcv": market_data.get("ohlcv"),
                }
            }

        if not securities_raw:
            return

        normalized: dict[str, dict[str, Any]] = {}
        for ticker, payload in securities_raw.items():
            if not isinstance(payload, dict):
                continue
            snapshot = payload.get("snapshot") or {}
            normalized[ticker] = {
                "last_price": snapshot.get("last_price"),
                "price_change_pct": snapshot.get("price_change_pct"),
                "value": snapshot.get("value"),
                "intraday_volatility_estimate": snapshot.get("intraday_volatility_estimate"),
            }

        if not normalized:
            return

        rows: list[list[str]] = []
        for ticker in sorted(normalized.keys()):
            snap = normalized[ticker]
            rows.append(
                [
                    ticker,
                    self._format_number(snap.get("last_price"), decimals=2),
                    self._format_percent(snap.get("price_change_pct")),
                    self._format_currency(snap.get("value")),
                    self._format_percent(snap.get("intraday_volatility_estimate")),
                ]
            )

        dashboard.add_table(
            id="market_compare",
            title="Сравнение тикеров",
            columns=[
                ("ticker", "Тикер"),
                ("last_price", "Цена"),
                ("price_change_pct", "Изм., %"),
                ("value", "Объём"),
                ("intraday_volatility_estimate", "Интрадейная вол., %"),
            ],
            rows=rows,
            data_ref="data.market_data.securities",
        )

    def _add_charts(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any], market_data: dict[str, Any]
    ) -> None:
        """Добавить графики на дашборд."""
        _ = market_data  # параметр может использоваться в расширениях
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
        self,
        dashboard: RiskDashboardSpec,
        risk_data: dict[str, Any],
        market_data: dict[str, Any],
    ) -> None:
        """Генерировать алерты на основе метрик."""
        _ = market_data  # зарезервировано под расширения
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

        self._generate_cfo_alerts(dashboard, risk_data)
        self._generate_tail_alerts(dashboard, risk_data)
        self._generate_correlation_alerts(dashboard, risk_data)

    def _generate_cfo_alerts(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Алерты для CFO-отчёта по ликвидности."""
        cfo_report = risk_data.get("cfo_report")
        if not isinstance(cfo_report, dict):
            return

        liquidity_profile = cfo_report.get("liquidity_profile") or {}
        metadata = cfo_report.get("metadata") or {}
        covenant_limits = (
            metadata.get("covenant_limits")
            or cfo_report.get("covenant_limits")
            or {}
        )

        min_liq_ratio = covenant_limits.get("min_liquidity_ratio")
        limit_pct = float(min_liq_ratio) * 100 if min_liq_ratio is not None else None
        short_term_ratio = liquidity_profile.get("short_term_ratio_pct")
        quick_ratio = liquidity_profile.get("quick_ratio_pct")

        if limit_pct is not None and short_term_ratio is not None:
            if short_term_ratio < limit_pct:
                dashboard.add_alert(
                    id="cfo_liquidity_covenant",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Коэффициент ликвидности {short_term_ratio:.1f}% ниже ковенанта {limit_pct:.1f}%.",
                    related_ids=["metric:cfo_liquidity_ratio_pct"],
                )

        if quick_ratio is not None and quick_ratio < 20:
            severity = AlertSeverity.CRITICAL if quick_ratio < 10 else AlertSeverity.WARNING
            dashboard.add_alert(
                id="cfo_liquidity_shortage",
                severity=severity,
                message=f"Низкая доля высоколиквидных активов: {quick_ratio:.1f}%.",
                related_ids=["metric:cfo_quick_ratio_pct"],
            )

        stress_scenarios = cfo_report.get("stress_scenarios") or []
        for scenario in stress_scenarios:
            if not isinstance(scenario, dict):
                continue
            breaches = scenario.get("covenant_breaches") or []
            for breach in breaches:
                if not isinstance(breach, dict):
                    continue
                if breach.get("code") == "LIQUIDITY_RATIO":
                    dashboard.add_alert(
                        id=f"cfo_stress_covenant_{scenario.get('id', 'unknown')}",
                        severity=AlertSeverity.CRITICAL,
                        message=breach.get("description", "Нарушение ковенанта ликвидности в стрессе"),
                        related_ids=[f"stress:{scenario.get('id')}"],
                    )
                    break

    def _generate_tail_alerts(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Алерты по хвостовым бумагам индекса."""
        scenario = risk_data.get("scenario")
        if scenario != "index_tail_analysis" and not risk_data.get("tail_constituents"):
            return

        per_instrument = risk_data.get("per_instrument") or []
        if not per_instrument:
            return

        risky: list[str] = []
        severity = AlertSeverity.WARNING
        for instr in per_instrument:
            if not isinstance(instr, dict):
                continue
            dd = instr.get("max_drawdown_pct")
            vol = instr.get("annualized_volatility_pct")
            dd_abs = abs(dd) if dd is not None else 0
            if (dd is not None and dd_abs > DRAWDOWN_WARNING_THRESHOLD) or (
                vol is not None and vol > VOLATILITY_HIGH_THRESHOLD
            ):
                risky.append(instr.get("ticker", ""))
                if dd_abs > DRAWDOWN_CRITICAL_THRESHOLD:
                    severity = AlertSeverity.CRITICAL

        if risky:
            dashboard.add_alert(
                id="index_tail_risk",
                severity=severity,
                message=f"Повышенный риск в хвосте индекса: {', '.join(sorted(filter(None, risky)))}.",
                related_ids=[f"ticker:{t}" for t in risky if t],
            )

    def _generate_correlation_alerts(
        self, dashboard: RiskDashboardSpec, risk_data: dict[str, Any]
    ) -> None:
        """Алерты по сильным корреляциям."""
        normalized = self._normalize_correlation_data(risk_data.get("correlation_matrix"))
        if not normalized:
            return

        tickers = normalized["tickers"]
        matrix = normalized["matrix"]

        max_val = 0.0
        pair: tuple[str, str] | None = None
        for i in range(len(tickers)):
            for j in range(len(tickers)):
                if i == j:
                    continue
                val = abs(matrix[i][j])
                if val > max_val:
                    max_val = val
                    pair = (tickers[i], tickers[j])

        if pair is None:
            return

        if max_val >= CORRELATION_CRITICAL_THRESHOLD:
            severity = AlertSeverity.CRITICAL
        elif max_val >= CORRELATION_WARNING_THRESHOLD:
            severity = AlertSeverity.WARNING
        else:
            return

        dashboard.add_alert(
            id="correlation_high",
            severity=severity,
            message=f"Сильная корреляция {max_val:.2f} между {pair[0]} и {pair[1]}.",
            related_ids=[f"ticker:{pair[0]}", f"ticker:{pair[1]}"],
        )

    def _build_data_payload(
        self, risk_data: dict[str, Any], market_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Сформировать словарь data/time_series для data_ref ссылок на фронте."""
        data: dict[str, Any] = {}

        normalized_instr = self._normalize_per_instrument(
            risk_data.get("per_instrument") or [],
            weight_from_fraction=True,
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

        corr_normalized = self._normalize_correlation_data(
            risk_data.get("correlation_matrix")
        )
        if corr_normalized:
            data["correlation_matrix"] = corr_normalized

        cfo_report = risk_data.get("cfo_report")
        if isinstance(cfo_report, dict):
            data["cfo_report"] = cfo_report

        if risk_data.get("scenario") == "index_tail_analysis" or risk_data.get("tail_constituents"):
            tail_instr = self._normalize_per_instrument(
                risk_data.get("per_instrument") or [], weight_from_fraction=True
            )
            if tail_instr:
                data["index_tail"] = {"per_instrument": tail_instr}

        market_securities = self._normalize_market_securities(market_data)
        if market_securities:
            data["market_data"] = {"securities": market_securities}

        return data

    def _build_time_series(
        self, risk_data: dict[str, Any], market_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Извлечь временные ряды в безопасном формате."""
        collected: dict[str, Any] = {}
        ts = risk_data.get("time_series")
        if isinstance(ts, dict):
            for k, v in ts.items():
                if isinstance(v, list):
                    collected[k] = v
                elif isinstance(v, dict) and all(isinstance(val, list) for val in v.values()):
                    collected[k] = {key: val for key, val in v.items() if isinstance(val, list)}

        if isinstance(market_data, dict):
            securities = market_data.get("securities")
            if isinstance(securities, dict):
                ohlcv = {
                    ticker: payload.get("ohlcv")
                    for ticker, payload in securities.items()
                    if isinstance(payload, dict) and isinstance(payload.get("ohlcv"), list)
                }
                if ohlcv:
                    collected["ohlcv"] = ohlcv

            tail_ohlcv = market_data.get("tail_ohlcv")
            if isinstance(tail_ohlcv, dict):
                filtered = {
                    k: v for k, v in tail_ohlcv.items() if isinstance(v, list)
                }
                if filtered:
                    collected["tail_ohlcv"] = filtered

        return collected

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

        for table in dashboard.tables:
            layout.append(
                LayoutItem(
                    id=f"table_{table.id}",
                    type=WidgetType.TABLE,
                    title=table.title,
                    table_id=table.id,
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

        if dashboard.alerts:
            layout.append(
                LayoutItem(
                    id="alerts",
                    type=WidgetType.ALERT_LIST,
                    title="Предупреждения",
                    alert_ids=[alert.id for alert in dashboard.alerts],
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
            weight = instr.get("weight", instr.get("weight_pct", 0))
            if weight and weight > max_weight:
                max_weight = weight
                top_ticker = instr.get("ticker", "Unknown")

        return top_ticker

    def _normalize_correlation_data(self, raw: Any) -> Optional[dict[str, Any]]:
        """Привести данные корреляций к детерминированному виду."""
        if not raw:
            return None
        corr = raw
        if isinstance(raw, dict) and "structuredContent" in raw:
            corr = raw.get("structuredContent", {}).get("data") or raw

        tickers = corr.get("tickers") if isinstance(corr, dict) else None
        matrix = corr.get("matrix") if isinstance(corr, dict) else None
        if not tickers or not matrix:
            return None

        try:
            order = sorted(range(len(tickers)), key=lambda i: str(tickers[i]))
            sorted_tickers = [tickers[i] for i in order]
            sorted_matrix = [
                [float(matrix[i][j]) for j in order] for i in order
            ]
        except Exception:
            return None

        return {"tickers": sorted_tickers, "matrix": sorted_matrix}

    def _normalize_per_instrument(
        self, per_instrument: list[Any], weight_from_fraction: bool
    ) -> list[dict[str, Any]]:
        """Нормализовать per_instrument в список метрик с weight_pct."""
        normalized: list[dict[str, Any]] = []
        for instr in per_instrument:
            if not isinstance(instr, dict):
                continue
            weight_pct = instr.get("weight_pct")
            if weight_pct is None:
                raw_weight = instr.get("weight")
                if raw_weight is not None:
                    try:
                        weight_val = float(raw_weight)
                        if weight_from_fraction or weight_val <= 1:
                            weight_pct = weight_val * 100
                        else:
                            weight_pct = weight_val
                    except Exception:
                        weight_pct = None
            normalized.append(
                {
                    "ticker": instr.get("ticker"),
                    "weight_pct": weight_pct,
                    "total_return_pct": instr.get("total_return_pct"),
                    "annualized_volatility_pct": instr.get("annualized_volatility_pct"),
                    "max_drawdown_pct": instr.get("max_drawdown_pct"),
                }
            )
        return normalized

    def _normalize_market_securities(
        self, market_data: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Нормализовать snapshots из market_data."""
        normalized: dict[str, dict[str, Any]] = {}
        if not isinstance(market_data, dict):
            return normalized

        securities = market_data.get("securities")
        if not securities and market_data.get("ticker"):
            ticker = market_data.get("ticker")
            securities = {
                ticker: {
                    "snapshot": market_data.get("snapshot"),
                    "ohlcv": market_data.get("ohlcv"),
                }
            }

        if not isinstance(securities, dict):
            return normalized

        for ticker, payload in securities.items():
            if not isinstance(payload, dict):
                continue
            snap = payload.get("snapshot") or {}
            normalized[ticker] = {
                "last_price": snap.get("last_price"),
                "price_change_pct": snap.get("price_change_pct"),
                "value": snap.get("value"),
                "intraday_volatility_estimate": snap.get("intraday_volatility_estimate"),
            }

        return normalized

    def _format_percent(self, value: Any, default: str = "нет данных") -> str:
        """Форматировать значение как процент с 2 знаками."""
        try:
            return f"{float(value):.2f}"
        except Exception:
            return default

    def _format_corr_value(self, value: Any, default: str = "нет данных") -> str:
        """Форматировать корреляцию (без умножения на 100)."""
        try:
            return f"{float(value):.2f}"
        except Exception:
            return default

    def _format_currency(self, value: Any, default: str = "нет данных") -> str:
        """Форматировать денежное значение с разделителем тысяч."""
        try:
            return f"{float(value):,.0f}".replace(",", " ")
        except Exception:
            return default

    def _format_number(
        self, value: Any, decimals: int = 0, default: str = "нет данных"
    ) -> str:
        """Форматировать число с заданной точностью."""
        try:
            fmt = f"{{:.{decimals}f}}"
            return fmt.format(float(value))
        except Exception:
            return default

    def _compute_worst_stress_value(
        self, base_value: float, stress_scenarios: Any
    ) -> Optional[float]:
        """Оценить стоимость портфеля в худшем стрессе."""
        worst_pct = self._compute_worst_pnl_pct(stress_scenarios)
        if worst_pct is None:
            return None
        return base_value * (1 + worst_pct / 100.0)

    def _compute_worst_pnl_pct(self, stress_scenarios: Any) -> Optional[float]:
        """Найти минимальный P&L % среди сценариев."""
        if not isinstance(stress_scenarios, list):
            return None
        pnls = []
        for scenario in stress_scenarios:
            if isinstance(scenario, dict) and scenario.get("pnl_pct") is not None:
                try:
                    pnls.append(float(scenario.get("pnl_pct")))
                except Exception:
                    continue
        if not pnls:
            return None
        return min(pnls)

