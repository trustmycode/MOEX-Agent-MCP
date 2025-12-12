"""
RiskAnalyticsSubagent — сабагент для риск-аналитики через risk-analytics-mcp.

Инкапсулирует взаимодействие с MCP-сервером risk-analytics-mcp:
- compute_portfolio_risk_basic — базовый портфельный риск
- compute_correlation_matrix — матрица корреляций
- suggest_rebalance — рекомендации по ребалансировке
- cfo_liquidity_report — CFO-отчёт по ликвидности
- issuer_peers_compare — сравнение эмитента с пирами
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

from ..core.base_subagent import BaseSubagent
from ..core.context import AgentContext
from ..core.result import SubagentResult
from ..mcp.client import McpClient
from ..mcp.types import McpConfig, ToolCallResult

logger = logging.getLogger(__name__)

# Константы и лимиты
DEFAULT_LOOKBACK_DAYS = 365
DEFAULT_REBALANCE = "buy_and_hold"


class RiskAnalyticsSubagent(BaseSubagent):
    """
    Сабагент для риск-аналитики через risk-analytics-mcp.

    Отвечает за:
    - Расчёт базовых метрик портфельного риска
    - Построение матрицы корреляций
    - Формирование рекомендаций по ребалансировке
    - Генерация CFO-отчёта по ликвидности
    - Сравнение эмитента с пирами

    Attributes:
        mcp_client: Клиент для взаимодействия с risk-analytics-mcp.
    """

    # Имя сабагента для реестра
    SUBAGENT_NAME = "risk_analytics"

    # MCP инструменты
    TOOL_PORTFOLIO_RISK = "compute_portfolio_risk_basic"
    TOOL_CORRELATION = "compute_correlation_matrix"
    TOOL_REBALANCE = "suggest_rebalance"
    TOOL_CFO_LIQUIDITY = "cfo_liquidity_report"
    TOOL_ISSUER_PEERS = "issuer_peers_compare"
    TOOL_TAIL_METRICS = "compute_tail_metrics"

    def __init__(
        self,
        mcp_client: Optional[McpClient] = None,
        mcp_config: Optional[McpConfig] = None,
    ) -> None:
        """
        Инициализация RiskAnalyticsSubagent.

        Args:
            mcp_client: Предконфигурированный MCP-клиент (опционально).
            mcp_config: Конфигурация MCP-сервера (если mcp_client не передан).
        """
        super().__init__(
            name=self.SUBAGENT_NAME,
            description="Риск-аналитика и расчёт портфельных метрик через risk-analytics-mcp",
            capabilities=[
                self.TOOL_PORTFOLIO_RISK,
                self.TOOL_CORRELATION,
                self.TOOL_REBALANCE,
                self.TOOL_CFO_LIQUIDITY,
                self.TOOL_ISSUER_PEERS,
            ],
        )

        if mcp_client is not None:
            self._mcp_client = mcp_client
        elif mcp_config is not None:
            self._mcp_client = McpClient(mcp_config)
        else:
            # Используем ENV для конфигурации
            url = os.getenv("RISK_ANALYTICS_MCP_URL", "http://localhost:8010")
            config = McpConfig(name="risk-analytics-mcp", url=url)
            self._mcp_client = McpClient(config)

    @property
    def mcp_client(self) -> McpClient:
        """Получить MCP-клиент."""
        return self._mcp_client

    async def execute(self, context: AgentContext) -> SubagentResult:
        """
        Выполнить основную логику сабагента.

        Анализирует контекст и вызывает соответствующие MCP-инструменты
        для расчёта риск-метрик.

        Args:
            context: AgentContext с данными запроса и промежуточными результатами.

        Returns:
            SubagentResult с данными или ошибкой.
        """
        # Валидация контекста
        validation_error = self.validate_context(context)
        if validation_error:
            return SubagentResult.create_error(error=validation_error)

        # Плановый шаг от LLM-планировщика (plan-first)
        planned_step = self._pick_planned_step(context.get_metadata("planned_steps", []))
        if planned_step:
            planned_result = await self._execute_planned_step(planned_step)
            if planned_result:
                return planned_result

        scenario_type = context.scenario_type

        try:
            if scenario_type in ("portfolio_risk_basic", "portfolio_risk"):
                return await self._handle_portfolio_risk(context)

            elif scenario_type == "portfolio_correlation":
                return await self._handle_correlation(context)

            elif scenario_type == "rebalance":
                return await self._handle_rebalance(context)

            elif scenario_type == "cfo_liquidity_report":
                return await self._handle_cfo_liquidity(context)

            elif scenario_type == "issuer_peers_compare":
                return await self._handle_issuer_peers(context)

            elif scenario_type in ("single_security_overview", "compare_securities"):
                # Для этих сценариев вычисляем корреляции если есть несколько тикеров
                return await self._handle_securities_risk(context)

            elif scenario_type == "index_risk_scan":
                return await self._handle_index_risk(context)

            else:
                # Пытаемся определить сценарий по данным в контексте
                return await self._handle_generic_risk(context)

        except Exception as e:
            error_msg = f"RiskAnalyticsSubagent error: {type(e).__name__}: {e}"
            logger.exception(error_msg)
            return SubagentResult.create_error(error=error_msg)

    async def _handle_portfolio_risk(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария portfolio_risk_basic.

        Вызывает compute_portfolio_risk_basic для расчёта метрик портфеля.
        """
        params = context.get_result("parsed_params", {})
        positions = params.get("positions", [])

        if not positions:
            return SubagentResult.create_error(
                error="Не указаны позиции портфеля для расчёта риска"
            )

        from_date = params.get("from_date") or self._default_from_date()
        to_date = params.get("to_date") or self._default_to_date()
        rebalance = params.get("rebalance", DEFAULT_REBALANCE)

        result = await self.compute_portfolio_risk_basic(
            positions=positions,
            from_date=from_date,
            to_date=to_date,
            rebalance=rebalance,
        )

        if not result.success:
            return SubagentResult.create_error(
                error=f"Ошибка расчёта портфельного риска: "
                f"{result.error.message if result.error else 'Unknown'}",
            )

        risk_report = result.data or {}
        structured = risk_report.get("structuredContent") or {}
        structured_data = structured.get("data") or {}
        structured_meta = structured.get("metadata") or {}
        outer_meta = risk_report.get("_meta") or {}

        # Расплющиваем payload MCP в плоскую структуру, понятную dashboard/explainer
        merged_payload: dict[str, Any] = {}
        merged_payload.update(structured_data)

        # Добавляем metadata, если есть
        if structured_meta:
            merged_payload["metadata"] = structured_meta
        elif outer_meta:
            merged_payload["metadata"] = outer_meta

        # Сохраняем сырой ответ для возможного дебага
        merged_payload["raw_risk_report"] = risk_report

        return SubagentResult.success(
            data={
                **merged_payload,
                "scenario": "portfolio_risk_basic",
            },
            next_agent_hint="dashboard",
        )

    async def _handle_correlation(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария portfolio_correlation.

        Строит матрицу корреляций для тикеров.
        """
        params = context.get_result("parsed_params", {})
        tickers = params.get("tickers", [])

        if not tickers or len(tickers) < 2:
            return SubagentResult.create_error(
                error="Для расчёта корреляций нужно минимум 2 тикера"
            )

        from_date = params.get("from_date") or self._default_from_date()
        to_date = params.get("to_date") or self._default_to_date()

        result = await self.compute_correlation_matrix(
            tickers=tickers,
            from_date=from_date,
            to_date=to_date,
        )

        if not result.success:
            return SubagentResult.create_error(
                error=f"Ошибка расчёта корреляций: "
                f"{result.error.message if result.error else 'Unknown'}",
            )

        return SubagentResult.success(
            data={
                "correlation_matrix": result.data,
                "scenario": "portfolio_correlation",
            },
            next_agent_hint="dashboard",
        )

    async def _handle_rebalance(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария rebalance.

        Формирует рекомендации по ребалансировке портфеля.
        """
        params = context.get_result("parsed_params", {})
        positions = params.get("positions", [])

        if not positions:
            return SubagentResult.create_error(
                error="Не указаны позиции портфеля для ребалансировки"
            )

        total_value = params.get("total_portfolio_value")
        risk_profile = params.get("risk_profile", {})

        result = await self.suggest_rebalance(
            positions=positions,
            total_portfolio_value=total_value,
            risk_profile=risk_profile,
        )

        if not result.success:
            return SubagentResult.create_error(
                error=f"Ошибка расчёта ребалансировки: "
                f"{result.error.message if result.error else 'Unknown'}",
            )

        return SubagentResult.success(
            data={
                "rebalance_proposal": result.data,
                "scenario": "rebalance",
            },
            next_agent_hint="explainer",
        )

    async def _handle_cfo_liquidity(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария cfo_liquidity_report.

        Генерирует CFO-отчёт по ликвидности портфеля.
        """
        params = context.get_result("parsed_params", {})
        positions = params.get("positions", [])

        if not positions:
            return SubagentResult.create_error(
                error="Не указаны позиции портфеля для CFO-отчёта"
            )

        from_date = params.get("from_date") or self._default_from_date()
        to_date = params.get("to_date") or self._default_to_date()
        total_value = params.get("total_portfolio_value")
        base_currency = params.get("base_currency", "RUB")
        horizon_months = params.get("horizon_months", 12)
        stress_scenarios = params.get("stress_scenarios")
        aggregates = params.get("aggregates")
        covenant_limits = params.get("covenant_limits")

        result = await self.cfo_liquidity_report(
            positions=positions,
            from_date=from_date,
            to_date=to_date,
            total_portfolio_value=total_value,
            base_currency=base_currency,
            horizon_months=horizon_months,
            stress_scenarios=stress_scenarios,
            aggregates=aggregates,
            covenant_limits=covenant_limits,
        )

        if not result.success:
            return SubagentResult.create_error(
                error=f"Ошибка генерации CFO-отчёта: "
                f"{result.error.message if result.error else 'Unknown'}",
            )

        return SubagentResult.success(
            data={
                "cfo_report": result.data,
                "scenario": "cfo_liquidity_report",
            },
            next_agent_hint="dashboard",
        )

    async def _handle_issuer_peers(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка сценария issuer_peers_compare.

        Сравнивает эмитента с пирами.
        """
        params = context.get_result("parsed_params", {})
        ticker = params.get("ticker")
        isin = params.get("isin")
        issuer_id = params.get("issuer_id")

        if not ticker and not isin and not issuer_id:
            return SubagentResult.create_error(
                error="Необходимо указать ticker, isin или issuer_id"
            )

        index_ticker = params.get("index_ticker", "IMOEX")
        sector = params.get("sector")
        peer_tickers = params.get("peer_tickers")
        max_peers = params.get("max_peers", 10)
        as_of_date = params.get("as_of_date")

        result = await self.issuer_peers_compare(
            ticker=ticker,
            isin=isin,
            issuer_id=issuer_id,
            index_ticker=index_ticker,
            sector=sector,
            peer_tickers=peer_tickers,
            max_peers=max_peers,
            as_of_date=as_of_date,
        )

        if not result.success:
            return SubagentResult.create_error(
                error=f"Ошибка сравнения с пирами: "
                f"{result.error.message if result.error else 'Unknown'}",
            )

        return SubagentResult.success(
            data={
                "peers_report": result.data,
                "scenario": "issuer_peers_compare",
            },
            next_agent_hint="dashboard",
        )

    async def _handle_securities_risk(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка риск-аналитики для single/compare securities.

        Если есть несколько тикеров — вычисляет корреляции.
        """
        market_data = context.get_result("market_data", {})
        tickers = market_data.get("tickers", [])

        if not tickers:
            # Нет данных от market_data
            return SubagentResult.success(
                data={"message": "Нет данных для риск-аналитики"},
                next_agent_hint="dashboard",
            )

        if len(tickers) >= 2:
            # Вычисляем корреляции
            from_date = market_data.get("from_date") or self._default_from_date()
            to_date = market_data.get("to_date") or self._default_to_date()

            corr_result = await self.compute_correlation_matrix(
                tickers=tickers,
                from_date=from_date,
                to_date=to_date,
            )

            if corr_result.success:
                return SubagentResult.success(
                    data={"correlation_matrix": corr_result.data},
                    next_agent_hint="dashboard",
                )

        return SubagentResult.success(
            data={"tickers": tickers},
            next_agent_hint="dashboard",
        )

    async def _handle_index_risk(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Обработка риск-аналитики для индекса.

        Вычисляет корреляции для top бумаг индекса.
        """
        market_data = context.get_result("market_data", {})
        index_data = market_data.get("index_data", {})
        constituents = index_data.get("data", [])

        if not constituents:
            return SubagentResult.success(
                data={"message": "Нет данных о составе индекса"},
                next_agent_hint="dashboard",
            )

        # Берём top-10 бумаг по весу для корреляции
        sorted_constituents = sorted(
            constituents,
            key=lambda x: x.get("weight_pct", 0),
            reverse=True,
        )[:10]
        tickers = [c.get("ticker") for c in sorted_constituents if c.get("ticker")]

        if len(tickers) >= 2:
            from_date = self._default_from_date()
            to_date = self._default_to_date()

            corr_result = await self.compute_correlation_matrix(
                tickers=tickers,
                from_date=from_date,
                to_date=to_date,
            )

            if corr_result.success:
                return SubagentResult.success(
                    data={
                        "top_constituents": sorted_constituents,
                        "correlation_matrix": corr_result.data,
                    },
                    next_agent_hint="dashboard",
                )

        return SubagentResult.success(
            data={"top_constituents": sorted_constituents},
            next_agent_hint="dashboard",
        )

    async def _handle_generic_risk(
        self, context: AgentContext
    ) -> SubagentResult:
        """
        Общая обработка риск-запросов.

        Пытается определить сценарий по данным в контексте.
        """
        params = context.get_result("parsed_params", {})

        # Проверяем наличие позиций — это портфельный сценарий
        if params.get("positions"):
            context.scenario_type = "portfolio_risk_basic"
            return await self._handle_portfolio_risk(context)

        # Проверяем наличие тикеров — это корреляционный сценарий
        market_data = context.get_result("market_data", {})
        if market_data.get("tickers"):
            return await self._handle_securities_risk(context)

        return SubagentResult.success(
            data={"message": "Недостаточно данных для риск-анализа"},
            next_agent_hint="dashboard",
        )

    # ------------------------------------------------------------------ #
    # Плановый режим (plan-first)
    # ------------------------------------------------------------------ #
    def _pick_planned_step(self, planned_steps: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Выбрать шаг плана для данного сабагента."""
        if not planned_steps:
            return None
        for step in planned_steps:
            if isinstance(step, dict) and step.get("subagent") == self.SUBAGENT_NAME:
                return step
        return None

    async def _execute_planned_step(self, step: dict[str, Any]) -> Optional[SubagentResult]:
        """
        Выполнить шаг, явно указанный планировщиком.
        """
        tool = (step.get("tool") or "").strip()
        args = step.get("args") if isinstance(step.get("args"), dict) else {}

        try:
            if tool == self.TOOL_CORRELATION:
                tickers = args.get("tickers") or []
                if not tickers or len(tickers) < 2:
                    return SubagentResult.create_error(error="План требует минимум 2 тикера для compute_correlation_matrix")
                from_date = args.get("from_date") or self._default_from_date()
                to_date = args.get("to_date") or self._default_to_date()
                result = await self.compute_correlation_matrix(
                    tickers=tickers,
                    from_date=from_date,
                    to_date=to_date,
                )
                if not result.success:
                    return SubagentResult.create_error(
                        error=f"Ошибка расчёта корреляций: {result.error.message if result.error else 'Unknown'}"
                    )
                return SubagentResult.success(
                    data={"correlation_matrix": result.data, "tickers": tickers},
                    next_agent_hint="dashboard",
                )

            if tool == self.TOOL_PORTFOLIO_RISK:
                positions = args.get("positions") or []
                if not positions:
                    return SubagentResult.create_error(error="План требует positions для compute_portfolio_risk_basic")
                from_date = args.get("from_date") or self._default_from_date()
                to_date = args.get("to_date") or self._default_to_date()
                rebalance = args.get("rebalance") or DEFAULT_REBALANCE
                result = await self.compute_portfolio_risk_basic(
                    positions=positions,
                    from_date=from_date,
                    to_date=to_date,
                    rebalance=rebalance,
                )
                if not result.success:
                    return SubagentResult.create_error(
                        error=f"Ошибка расчёта портфельного риска: {result.error.message if result.error else 'Unknown'}"
                    )
                return SubagentResult.success(
                    data={"portfolio_risk": result.data, "from_date": from_date, "to_date": to_date},
                    next_agent_hint="dashboard",
                )

            if tool == self.TOOL_REBALANCE:
                positions = args.get("positions") or []
                if not positions:
                    return SubagentResult.create_error(error="План требует positions для suggest_rebalance")
                total_value = args.get("total_portfolio_value")
                risk_profile = args.get("risk_profile")
                result = await self.suggest_rebalance(
                    positions=positions,
                    total_portfolio_value=total_value,
                    risk_profile=risk_profile,
                )
                if not result.success:
                    return SubagentResult.create_error(
                        error=f"Ошибка ребалансировки: {result.error.message if result.error else 'Unknown'}"
                    )
                return SubagentResult.success(
                    data={"rebalance_proposal": result.data},
                    next_agent_hint="explainer",
                )

            if tool == self.TOOL_CFO_LIQUIDITY:
                positions = args.get("positions") or []
                if not positions:
                    return SubagentResult.create_error(error="План требует positions для cfo_liquidity_report")
                from_date = args.get("from_date") or self._default_from_date()
                to_date = args.get("to_date") or self._default_to_date()
                total_value = args.get("total_portfolio_value")
                base_currency = args.get("base_currency") or "RUB"
                horizon_months = args.get("horizon_months") or 12
                stress_scenarios = args.get("stress_scenarios")
                aggregates = args.get("aggregates")
                covenant_limits = args.get("covenant_limits")
                result = await self.cfo_liquidity_report(
                    positions=positions,
                    from_date=from_date,
                    to_date=to_date,
                    total_portfolio_value=total_value,
                    base_currency=base_currency,
                    horizon_months=horizon_months,
                    stress_scenarios=stress_scenarios,
                    aggregates=aggregates,
                    covenant_limits=covenant_limits,
                )
                if not result.success:
                    return SubagentResult.create_error(
                        error=f"Ошибка CFO-отчёта: {result.error.message if result.error else 'Unknown'}"
                    )
                return SubagentResult.success(
                    data={"cfo_report": result.data},
                    next_agent_hint="dashboard",
                )

            if tool == self.TOOL_ISSUER_PEERS:
                ticker = args.get("ticker")
                isin = args.get("isin")
                issuer_id = args.get("issuer_id")
                if not ticker and not isin and not issuer_id:
                    return SubagentResult.create_error(
                        error="План требует ticker/isin/issuer_id для issuer_peers_compare"
                    )
                index_ticker = args.get("index_ticker", "IMOEX")
                sector = args.get("sector")
                peer_tickers = args.get("peer_tickers")
                max_peers = args.get("max_peers", 10)
                as_of_date = args.get("as_of_date")
                result = await self.issuer_peers_compare(
                    ticker=ticker,
                    isin=isin,
                    issuer_id=issuer_id,
                    index_ticker=index_ticker,
                    sector=sector,
                    peer_tickers=peer_tickers,
                    max_peers=max_peers,
                    as_of_date=as_of_date,
                )
                if not result.success:
                    return SubagentResult.create_error(
                        error=f"Ошибка сравнения с пирами: {result.error.message if result.error else 'Unknown'}"
                    )
                return SubagentResult.success(
                    data={"peers_report": result.data},
                    next_agent_hint="dashboard",
                )

            if tool == self.TOOL_TAIL_METRICS:
                return await self._compute_tail_metrics_planned(args, context)

            if tool:
                return SubagentResult.create_error(error=f"Неизвестный tool для risk_analytics: {tool}")
        except Exception as exc:  # pragma: no cover - защита от неожиданных ошибок
            logger.exception("RiskAnalytics planned step failed: %s", exc)
            return SubagentResult.create_error(error=f"Ошибка выполнения планового шага: {type(exc).__name__}: {exc}")

        return None

    async def _compute_tail_metrics_planned(self, args: dict[str, Any], context: AgentContext) -> SubagentResult:
        """
        Посчитать метрики хвоста индекса через MCP; при недоступности MCP — fallback на локальный расчёт.
        """
        market_data = context.get_result("market_data", {})
        ohlcv = args.get("ohlcv") or market_data.get("tail_ohlcv")
        constituents = args.get("constituents") or market_data.get("tail_constituents") or []

        if not ohlcv:
            return SubagentResult.create_error(error="Нет OHLCV для хвоста индекса")

        # Попытка через MCP
        try:
            mcp_args = {"ohlcv": ohlcv, "constituents": constituents}
            result = await self.compute_tail_metrics(mcp_args)  # type: ignore[attr-defined]
            if result.success:
                data = result.data or {}
                return SubagentResult.success(data=data, next_agent_hint="explainer")
            if result.error:
                return SubagentResult.create_error(error=result.error.message if result.error else "Ошибка compute_tail_metrics")
        except Exception:
            logger.warning("compute_tail_metrics MCP недоступен, используем локальный fallback", exc_info=True)

        # Fallback на локальную математику
        fallback = self._compute_tail_metrics_local(ohlcv, constituents)
        if fallback["errors"]:
            return SubagentResult.partial(
                data=fallback["data"],
                error="; ".join(fallback["errors"]),
                next_agent_hint="explainer",
            )
        return SubagentResult.success(data=fallback["data"], next_agent_hint="explainer")

    def _compute_tail_metrics_local(self, ohlcv: dict[str, Any], constituents: list[Any]) -> dict[str, Any]:
        weight_map: dict[str, Optional[float]] = {}
        if constituents and isinstance(constituents, list):
            for c in constituents:
                if isinstance(c, dict) and c.get("ticker") is not None:
                    weight_pct = c.get("weight_pct")
                    weight_map[c.get("ticker")] = weight_pct

        per_instrument: list[dict[str, Any]] = []
        errors: list[str] = []

        for ticker, series in ohlcv.items():
            try:
                metrics = self._compute_basic_metrics_from_ohlcv_local(series)
            except Exception as exc:  # pragma: no cover
                errors.append(f"{ticker}: {type(exc).__name__}")
                continue

            weight_pct = weight_map.get(ticker)
            weight_fraction = (float(weight_pct) / 100.0) if weight_pct is not None else None

            per_instrument.append(
                {
                    "ticker": ticker,
                    "weight": weight_fraction,
                    "total_return_pct": metrics.get("return_pct"),
                    "annualized_volatility_pct": metrics.get("ann_vol_pct"),
                    "max_drawdown_pct": metrics.get("max_dd_pct"),
                }
            )

        data = {"per_instrument": per_instrument, "scenario": "index_tail_analysis"}
        return {"data": data, "errors": errors}

    def _compute_basic_metrics_from_ohlcv_local(self, series: Any) -> dict[str, float]:
        """
        Рассчитать месячную доходность, годовую волатильность и max drawdown из OHLCV (fallback).
        """
        if not series or not isinstance(series, list):
            raise ValueError("Пустая серия OHLCV")

        closes: list[float] = []
        for bar in series:
            if isinstance(bar, dict):
                close_val = bar.get("close") or bar.get("Close") or bar.get("CLOSE")
                if close_val is not None:
                    try:
                        closes.append(float(close_val))
                    except Exception:
                        continue

        if len(closes) < 2:
            raise ValueError("Недостаточно точек OHLCV")

        first, last = closes[0], closes[-1]
        return_pct = (last / first - 1.0) * 100 if first else 0.0

        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            if prev:
                returns.append((curr / prev - 1.0))
        if returns:
            mean = sum(returns) / len(returns)
            var = sum((r - mean) ** 2 for r in returns) / len(returns)
            import math

            ann_vol_pct = (var ** 0.5) * (math.sqrt(252)) * 100
        else:
            ann_vol_pct = 0.0

        peak = closes[0]
        max_dd = 0.0
        for price in closes:
            if price > peak:
                peak = price
            dd = (price / peak - 1.0) * 100
            if dd < max_dd:
                max_dd = dd

        return {
            "return_pct": return_pct,
            "ann_vol_pct": ann_vol_pct,
            "max_dd_pct": max_dd,
        }

    # --- MCP Tool Wrappers ---

    async def compute_portfolio_risk_basic(
        self,
        positions: list[dict[str, Any]],
        from_date: str,
        to_date: str,
        rebalance: str = DEFAULT_REBALANCE,
    ) -> ToolCallResult:
        """
        Расчёт базовых метрик портфельного риска.

        Args:
            positions: Список позиций [{ticker, weight, board?}].
            from_date: Начальная дата (YYYY-MM-DD).
            to_date: Конечная дата (YYYY-MM-DD).
            rebalance: Политика ребалансировки ("buy_and_hold" или "monthly").

        Returns:
            ToolCallResult с отчётом или ошибкой.
        """
        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_PORTFOLIO_RISK,
            args={
                "positions": positions,
                "from_date": from_date,
                "to_date": to_date,
                "rebalance": rebalance,
            },
        )

    async def compute_correlation_matrix(
        self,
        tickers: list[str],
        from_date: str,
        to_date: str,
    ) -> ToolCallResult:
        """
        Построение матрицы корреляций.

        Args:
            tickers: Список тикеров (минимум 2).
            from_date: Начальная дата (YYYY-MM-DD).
            to_date: Конечная дата (YYYY-MM-DD).

        Returns:
            ToolCallResult с матрицей или ошибкой.
        """
        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_CORRELATION,
            args={
                "tickers": [t.upper() for t in tickers],
                "from_date": from_date,
                "to_date": to_date,
            },
        )

    async def compute_tail_metrics(
        self,
        payload: dict[str, Any],
    ) -> ToolCallResult:
        """
        Расчёт метрик хвоста индекса по OHLCV (через MCP).
        """
        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_TAIL_METRICS,
            args=payload,
        )

    async def suggest_rebalance(
        self,
        positions: list[dict[str, Any]],
        total_portfolio_value: Optional[float] = None,
        risk_profile: Optional[dict[str, Any]] = None,
    ) -> ToolCallResult:
        """
        Формирование рекомендаций по ребалансировке.

        Args:
            positions: Текущие позиции [{ticker, current_weight, asset_class?}].
            total_portfolio_value: Общая стоимость портфеля.
            risk_profile: Профиль риска с ограничениями.

        Returns:
            ToolCallResult с предложением или ошибкой.
        """
        args: dict[str, Any] = {"positions": positions}

        if total_portfolio_value is not None:
            args["total_portfolio_value"] = total_portfolio_value

        if risk_profile:
            args["risk_profile"] = risk_profile

        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_REBALANCE,
            args=args,
        )

    async def cfo_liquidity_report(
        self,
        positions: list[dict[str, Any]],
        from_date: str,
        to_date: str,
        total_portfolio_value: Optional[float] = None,
        base_currency: str = "RUB",
        horizon_months: int = 12,
        stress_scenarios: Optional[list[str]] = None,
        aggregates: Optional[dict[str, Any]] = None,
        covenant_limits: Optional[dict[str, Any]] = None,
    ) -> ToolCallResult:
        """
        Генерация CFO-отчёта по ликвидности.

        Args:
            positions: Позиции с характеристиками ликвидности.
            from_date: Начальная дата анализа.
            to_date: Конечная дата анализа.
            total_portfolio_value: Общая стоимость портфеля.
            base_currency: Базовая валюта отчёта.
            horizon_months: Горизонт прогноза в месяцах.
            stress_scenarios: Список сценариев для стресс-тестов.
            aggregates: Агрегированные характеристики.
            covenant_limits: Ковенантные ограничения.

        Returns:
            ToolCallResult с отчётом или ошибкой.
        """
        args: dict[str, Any] = {
            "positions": positions,
            "from_date": from_date,
            "to_date": to_date,
            "base_currency": base_currency,
            "horizon_months": horizon_months,
        }

        if total_portfolio_value is not None:
            args["total_portfolio_value"] = total_portfolio_value

        if stress_scenarios:
            args["stress_scenarios"] = stress_scenarios

        if aggregates:
            args["aggregates"] = aggregates

        if covenant_limits:
            args["covenant_limits"] = covenant_limits

        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_CFO_LIQUIDITY,
            args=args,
        )

    async def issuer_peers_compare(
        self,
        ticker: Optional[str] = None,
        isin: Optional[str] = None,
        issuer_id: Optional[str] = None,
        index_ticker: str = "IMOEX",
        sector: Optional[str] = None,
        peer_tickers: Optional[list[str]] = None,
        max_peers: int = 10,
        as_of_date: Optional[str] = None,
    ) -> ToolCallResult:
        """
        Сравнение эмитента с пирами.

        Args:
            ticker: Тикер эмитента.
            isin: ISIN эмитента.
            issuer_id: ID эмитента в MOEX.
            index_ticker: Индекс для выбора пиров.
            sector: Фильтр по сектору.
            peer_tickers: Явный список пиров.
            max_peers: Максимальное количество пиров.
            as_of_date: Дата для снимка данных.

        Returns:
            ToolCallResult с отчётом или ошибкой.
        """
        args: dict[str, Any] = {
            "index_ticker": index_ticker,
            "max_peers": max_peers,
        }

        if ticker:
            args["ticker"] = ticker.upper()
        if isin:
            args["isin"] = isin
        if issuer_id:
            args["issuer_id"] = issuer_id
        if sector:
            args["sector"] = sector
        if peer_tickers:
            args["peer_tickers"] = [t.upper() for t in peer_tickers]
        if as_of_date:
            args["as_of_date"] = as_of_date

        return await self._mcp_client.call_tool(
            tool_name=self.TOOL_ISSUER_PEERS,
            args=args,
        )

    # --- Helper Methods ---

    def _default_from_date(self) -> str:
        """Получить дату начала по умолчанию (год назад)."""
        d = date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
        return d.isoformat()

    def _default_to_date(self) -> str:
        """Получить дату окончания по умолчанию (сегодня)."""
        return date.today().isoformat()
