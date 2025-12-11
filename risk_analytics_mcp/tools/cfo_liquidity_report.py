"""
Инструмент build_cfo_liquidity_report для формирования CFO-ориентированного отчёта
по ликвидности и устойчивости портфеля.

Сценарий 9: CFO получает структурированный отчёт с:
- Профилем ликвидности по корзинам
- Дюрацией и валютной экспозицией
- Концентрациями
- Стресс-сценариями и ковенант-чеками
- Рекомендациями и executive summary
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from fastmcp import Context
from opentelemetry import trace
from pydantic import Field

from moex_iss_mcp.error_mapper import ErrorMapper
from moex_iss_sdk import IssClient
from moex_iss_sdk.exceptions import DateRangeTooLargeError, TooManyTickersError
from moex_iss_sdk.utils import validate_date_range, utc_now

from ..calculations import (
    aggregate_portfolio_returns,
    build_returns_by_ticker,
    calc_basic_portfolio_metrics,
    compute_var_light,
    run_stress_scenarios,
    # CFO-специфичные функции
    build_liquidity_profile,
    build_duration_profile,
    build_currency_exposure,
    build_concentration_profile,
    build_cfo_stress_scenarios,
    build_recommendations,
    build_executive_summary,
)
from ..mcp_instance import mcp
from ..models import (
    CfoLiquidityPosition,
    CfoLiquidityReport,
    CfoLiquidityReportInput,
    CfoRiskMetrics,
    CovenantLimits,
    PortfolioAggregates,
    PortfolioPosition,
    VarLightConfig,
    VarLightResult,
)
from ..tools.utils import ToolResult
from ..telemetry import NullTracing

# Глобальные зависимости (инициализируются при запуске сервера)
_iss_client = None
_metrics = None
_tracing = NullTracing()
_max_tickers = None
_max_lookback_days = None
_NOOP_SPAN = type("NoopSpan", (), {"set_attribute": lambda self, *args, **kwargs: None})()


def init_tool_dependencies(iss_client, metrics, tracing, max_tickers, max_lookback_days):
    """Инициализировать зависимости для инструментов."""
    global _iss_client, _metrics, _tracing, _max_tickers, _max_lookback_days
    _iss_client = iss_client
    _metrics = metrics
    _tracing = tracing or NullTracing()
    _max_tickers = max_tickers
    _max_lookback_days = max_lookback_days


tracer = trace.get_tracer(__name__)


def _validate_limits(input_model: CfoLiquidityReportInput, *, max_tickers: int, max_lookback_days: int) -> None:
    if len(input_model.positions) > max_tickers:
        raise TooManyTickersError(
            f"Too many tickers: {len(input_model.positions)} > {max_tickers}",
            details={"tickers": [p.ticker for p in input_model.positions]},
        )
    validate_date_range(input_model.from_date, input_model.to_date, max_lookback_days=max_lookback_days)


async def _fetch_ohlcv_for_positions_async(
    positions: list[CfoLiquidityPosition],
    *,
    from_date,
    to_date,
    max_lookback_days: int,
    ctx: Context = None,
) -> tuple[Dict[str, list], list[str]]:
    """
    Асинхронная версия получения OHLCV данных для позиций.
    
    Returns:
        tuple: (данные по тикерам, список тикеров с ошибками)
    """
    data: Dict[str, list] = {}
    failed_tickers: list[str] = []
    
    for position in positions:
        board = position.board or _iss_client.settings.default_board
        try:
            data[position.ticker] = await asyncio.to_thread(
                _iss_client.get_ohlcv_series,
                ticker=position.ticker,
                board=board,
                from_date=from_date,
                to_date=to_date,
                interval="1d",
                max_lookback_days=max_lookback_days,
            )
        except Exception as e:
            failed_tickers.append(position.ticker)
            if ctx:
                await ctx.info(f"⚠️ Нет данных MOEX ISS для {position.ticker}: {e}")
    
    return data, failed_tickers


def _resolve_aggregates(
    input_model: CfoLiquidityReportInput,
    positions: list[CfoLiquidityPosition],
) -> PortfolioAggregates:
    """
    Построить агрегаты портфеля из позиций или использовать явно заданные.
    """
    if input_model.aggregates:
        return input_model.aggregates

    # Автоматическое построение агрегатов из позиций
    asset_class_weights: dict[str, float] = {}
    fx_exposure_weights: dict[str, float] = {}

    for pos in positions:
        asset_class_weights[pos.asset_class] = asset_class_weights.get(pos.asset_class, 0.0) + pos.weight
        currency = pos.currency.upper()
        fx_exposure_weights[currency] = fx_exposure_weights.get(currency, 0.0) + pos.weight

    return PortfolioAggregates(
        base_currency=input_model.base_currency,
        asset_class_weights=asset_class_weights,
        fx_exposure_weights=fx_exposure_weights,
        fixed_income_duration_years=None,
        credit_spread_duration_years=None,
    )


def build_cfo_liquidity_report_core(
    input_payload,
    iss_client: IssClient,
    *,
    max_tickers: int,
    max_lookback_days: int,
) -> CfoLiquidityReport:
    """
    Выполнить формирование CFO-отчёта без привязки к FastMCP.
    """
    input_model = (
        input_payload
        if isinstance(input_payload, CfoLiquidityReportInput)
        else CfoLiquidityReportInput.model_validate(input_payload)
    )
    _validate_limits(input_model, max_tickers=max_tickers, max_lookback_days=max_lookback_days)

    positions = input_model.positions
    aggregates = _resolve_aggregates(input_model, positions)

    # 1. Профиль ликвидности
    liquidity_profile = build_liquidity_profile(
        positions, total_portfolio_value=input_model.total_portfolio_value
    )

    # 2. Профиль дюрации
    duration_profile = build_duration_profile(positions, aggregates)

    # 3. Валютная экспозиция
    currency_exposure = build_currency_exposure(
        positions,
        base_currency=input_model.base_currency,
        total_portfolio_value=input_model.total_portfolio_value,
    )

    # 4. Концентрации
    concentration_profile = build_concentration_profile(positions)

    # 5. Получить OHLCV и рассчитать метрики риска
    ohlcv_by_ticker = {}
    for position in positions:
        board = position.board or iss_client.settings.default_board
        ohlcv_by_ticker[position.ticker] = iss_client.get_ohlcv_series(
            ticker=position.ticker,
            board=board,
            from_date=input_model.from_date,
            to_date=input_model.to_date,
            interval="1d",
            max_lookback_days=max_lookback_days,
        )

    returns_by_ticker = build_returns_by_ticker(ohlcv_by_ticker)
    weight_map = {pos.ticker: pos.weight for pos in positions}
    portfolio_returns = aggregate_portfolio_returns(returns_by_ticker, weight_map, rebalance="buy_and_hold")

    portfolio_metrics_dict = calc_basic_portfolio_metrics([value for _, value in portfolio_returns])

    var_config = VarLightConfig()
    var_light = compute_var_light(portfolio_metrics_dict.get("annualized_volatility_pct"), var_config)

    risk_metrics = CfoRiskMetrics(
        total_return_pct=portfolio_metrics_dict.get("total_return_pct"),
        annualized_volatility_pct=portfolio_metrics_dict.get("annualized_volatility_pct"),
        max_drawdown_pct=portfolio_metrics_dict.get("max_drawdown_pct"),
        var_light=var_light,
    )

    # 6. Стресс-сценарии
    scenario_ids = [s for s in input_model.stress_scenarios if s != "base_case"]
    stress_results = run_stress_scenarios(aggregates, scenario_ids or None)

    cfo_stress_scenarios = build_cfo_stress_scenarios(
        stress_results,
        total_portfolio_value=input_model.total_portfolio_value,
        liquidity_profile=liquidity_profile,
        covenant_limits=input_model.covenant_limits,
    )

    # 7. Рекомендации
    recommendations = build_recommendations(
        liquidity_profile,
        concentration_profile,
        currency_exposure,
        duration_profile,
        cfo_stress_scenarios,
    )

    # 8. Executive Summary
    executive_summary = build_executive_summary(
        liquidity_profile,
        concentration_profile,
        cfo_stress_scenarios,
        recommendations,
    )

    metadata = {
        "as_of": utc_now().isoformat(),
        "from_date": input_model.from_date.isoformat(),
        "to_date": input_model.to_date.isoformat(),
        "horizon_months": input_model.horizon_months,
        "base_currency": input_model.base_currency,
        "total_portfolio_value": input_model.total_portfolio_value,
        "positions_count": len(positions),
        "iss_base_url": iss_client.settings.base_url,
        "stress_scenarios": [s.id for s in cfo_stress_scenarios],
    }

    return CfoLiquidityReport.success(
        metadata=metadata,
        liquidity_profile=liquidity_profile,
        duration_profile=duration_profile,
        currency_exposure=currency_exposure,
        concentration_profile=concentration_profile,
        risk_metrics=risk_metrics,
        stress_scenarios=cfo_stress_scenarios,
        recommendations=recommendations,
        executive_summary=executive_summary,
    )


@mcp.tool(
    name="build_cfo_liquidity_report",
    description="""📋 Сформировать CFO-ориентированный отчёт по ликвидности и устойчивости портфеля.

Инструмент создаёт структурированный отчёт для CFO, включающий:
- Профиль ликвидности по корзинам (0-7d, 8-30d, 31-90d, 90d+)
- Дюрацию и валютную экспозицию
- Концентрации по позициям и классам активов
- Стресс-сценарии с проверкой ковенант
- Рекомендации и executive summary

Сценарий 9: CFO Liquidity Report для оценки устойчивости и принятия решений.

Примеры использования:
- Ежемесячный отчёт для совета директоров
- Оценка рисков рефинансирования
- Анализ устойчивости к стресс-сценариям
""",
)
async def build_cfo_liquidity_report(
    positions: List[Dict[str, Any]] = Field(
        ...,
        description="Позиции портфеля с тикерами, весами, классами активов и корзинами ликвидности",
    ),
    from_date: str = Field(
        ...,
        description="Начальная дата периода анализа в формате YYYY-MM-DD",
    ),
    to_date: str = Field(
        ...,
        description="Конечная дата периода анализа в формате YYYY-MM-DD",
    ),
    base_currency: str = Field(
        default="RUB",
        description="Базовая валюта отчёта (ISO 4217)",
    ),
    total_portfolio_value: Optional[float] = Field(
        default=None,
        description="Общая стоимость портфеля для расчёта абсолютных значений",
    ),
    horizon_months: int = Field(
        default=12,
        description="Горизонт прогнозирования ликвидности (месяцы, 1-36)",
    ),
    stress_scenarios: Optional[List[str]] = Field(
        default=None,
        description="Список стресс-сценариев (по умолчанию: base_case, equity_-10_fx_+20, rates_+300bp)",
    ),
    aggregates: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Агрегированные характеристики портфеля для стресс-сценариев",
    ),
    covenant_limits: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Лимиты ковенант для проверки (max_net_debt_ebitda, min_liquidity_ratio)",
    ),
    ctx: Context = None,
) -> ToolResult:
    """
    Сформировать CFO-ориентированный отчёт по ликвидности и устойчивости портфеля.

    Args:
        positions: Позиции портфеля с тикерами, весами, классами активов и корзинами ликвидности
        from_date: Начальная дата периода анализа в формате YYYY-MM-DD
        to_date: Конечная дата периода анализа в формате YYYY-MM-DD
        base_currency: Базовая валюта отчёта (ISO 4217)
        total_portfolio_value: Общая стоимость портфеля для расчёта абсолютных значений
        horizon_months: Горизонт прогнозирования ликвидности (месяцы, 1-36)
        stress_scenarios: Список стресс-сценариев
        aggregates: Агрегированные характеристики портфеля для стресс-сценариев
        covenant_limits: Лимиты ковенант для проверки
        ctx: Контекст для логирования и отслеживания прогресса

    Returns:
        ToolResult: CFO Liquidity Report со всеми секциями

    Raises:
        McpError: При ошибках выполнения или валидации параметров
    """
    tool_name = "build_cfo_liquidity_report"
    start_ts = None

    if _metrics:
        start_ts = time.perf_counter()
        _metrics.inc_tool_call(tool_name)

    if _tracing:
        span_context = _tracing.start_span(tool_name)
    else:
        span_context = tracer.start_as_current_span(tool_name)

    with span_context as span:
        if span is None:
            span = _NOOP_SPAN
        try:
            if ctx:
                await ctx.info(f"🚀 Формирование CFO Liquidity Report для {len(positions)} позиций")
                await ctx.report_progress(progress=0, total=100)

            # Настройка атрибутов спана
            span.set_attribute("positions_count", len(positions))
            span.set_attribute("from_date", from_date)
            span.set_attribute("to_date", to_date)
            span.set_attribute("base_currency", base_currency)

            # Валидация входных данных
            if ctx:
                await ctx.info("🔍 Валидация параметров")
                await ctx.report_progress(progress=10, total=100)

            payload = {
                "positions": positions,
                "from_date": from_date,
                "to_date": to_date,
                "base_currency": base_currency,
            }
            if total_portfolio_value is not None:
                payload["total_portfolio_value"] = total_portfolio_value
            if horizon_months is not None:
                payload["horizon_months"] = horizon_months
            if stress_scenarios is not None:
                payload["stress_scenarios"] = stress_scenarios
            if aggregates is not None:
                payload["aggregates"] = aggregates
            if covenant_limits is not None:
                payload["covenant_limits"] = covenant_limits

            input_model = CfoLiquidityReportInput.model_validate(payload)
            _validate_limits(input_model, max_tickers=_max_tickers, max_lookback_days=_max_lookback_days)

            positions_list = input_model.positions
            resolved_aggregates = _resolve_aggregates(input_model, positions_list)

            # Построение профилей
            if ctx:
                await ctx.info("📊 Построение профиля ликвидности")
                await ctx.report_progress(progress=20, total=100)

            liquidity_profile = await asyncio.to_thread(
                build_liquidity_profile,
                positions_list,
                total_portfolio_value=input_model.total_portfolio_value,
            )

            duration_profile = await asyncio.to_thread(
                build_duration_profile,
                positions_list,
                resolved_aggregates,
            )

            currency_exposure = await asyncio.to_thread(
                build_currency_exposure,
                positions_list,
                base_currency=input_model.base_currency,
                total_portfolio_value=input_model.total_portfolio_value,
            )

            concentration_profile = await asyncio.to_thread(
                build_concentration_profile,
                positions_list,
            )

            if ctx:
                await ctx.info("📡 Запрос исторических данных")
                await ctx.report_progress(progress=40, total=100)

            ohlcv_by_ticker, failed_tickers = await _fetch_ohlcv_for_positions_async(
                positions_list,
                from_date=input_model.from_date,
                to_date=input_model.to_date,
                max_lookback_days=_max_lookback_days,
                ctx=ctx,
            )

            # Риск-метрики рассчитываем только если есть данные хотя бы для одного тикера
            risk_metrics = None
            if ohlcv_by_ticker:
                if ctx:
                    await ctx.info("📈 Расчёт метрик риска")
                    await ctx.report_progress(progress=60, total=100)

                returns_by_ticker = await asyncio.to_thread(build_returns_by_ticker, ohlcv_by_ticker)
                
                # Используем только тикеры с данными для расчёта портфельных метрик
                available_tickers = set(returns_by_ticker.keys())
                weight_map = {pos.ticker: pos.weight for pos in positions_list if pos.ticker in available_tickers}
                
                # Нормализуем веса если часть тикеров отсутствует
                if weight_map:
                    total_weight = sum(weight_map.values())
                    if total_weight > 0 and total_weight != 1.0:
                        weight_map = {k: v / total_weight for k, v in weight_map.items()}
                    
                    portfolio_returns = await asyncio.to_thread(
                        aggregate_portfolio_returns, returns_by_ticker, weight_map, rebalance="buy_and_hold"
                    )

                    portfolio_metrics_dict = await asyncio.to_thread(
                        calc_basic_portfolio_metrics, [value for _, value in portfolio_returns]
                    )

                    var_config = VarLightConfig()
                    var_light = await asyncio.to_thread(
                        compute_var_light, portfolio_metrics_dict.get("annualized_volatility_pct"), var_config
                    )

                    risk_metrics = CfoRiskMetrics(
                        total_return_pct=portfolio_metrics_dict.get("total_return_pct"),
                        annualized_volatility_pct=portfolio_metrics_dict.get("annualized_volatility_pct"),
                        max_drawdown_pct=portfolio_metrics_dict.get("max_drawdown_pct"),
                        var_light=var_light,
                    )
            else:
                if ctx:
                    await ctx.info("⚠️ Нет данных MOEX ISS для расчёта риск-метрик")

            if ctx:
                await ctx.info("🔬 Расчёт стресс-сценариев")
                await ctx.report_progress(progress=75, total=100)

            scenario_ids = [s for s in input_model.stress_scenarios if s != "base_case"]
            stress_results = await asyncio.to_thread(
                run_stress_scenarios, resolved_aggregates, scenario_ids or None
            )

            cfo_stress_scenarios = await asyncio.to_thread(
                build_cfo_stress_scenarios,
                stress_results,
                total_portfolio_value=input_model.total_portfolio_value,
                liquidity_profile=liquidity_profile,
                covenant_limits=input_model.covenant_limits,
            )

            if ctx:
                await ctx.info("💡 Формирование рекомендаций")
                await ctx.report_progress(progress=90, total=100)

            recommendations = await asyncio.to_thread(
                build_recommendations,
                liquidity_profile,
                concentration_profile,
                currency_exposure,
                duration_profile,
                cfo_stress_scenarios,
            )

            executive_summary = await asyncio.to_thread(
                build_executive_summary,
                liquidity_profile,
                concentration_profile,
                cfo_stress_scenarios,
                recommendations,
            )

            metadata = {
                "as_of": utc_now().isoformat(),
                "from_date": input_model.from_date.isoformat(),
                "to_date": input_model.to_date.isoformat(),
                "horizon_months": input_model.horizon_months,
                "base_currency": input_model.base_currency,
                "total_portfolio_value": input_model.total_portfolio_value,
                "positions_count": len(positions_list),
                "iss_base_url": _iss_client.settings.base_url,
                "stress_scenarios": [s.id for s in cfo_stress_scenarios],
            }
            if failed_tickers:
                metadata["missing_iss_data"] = failed_tickers
                metadata["note"] = f"Риск-метрики рассчитаны без тикеров: {', '.join(failed_tickers)} (нет данных на MOEX ISS)"

            output = CfoLiquidityReport.success(
                metadata=metadata,
                liquidity_profile=liquidity_profile,
                duration_profile=duration_profile,
                currency_exposure=currency_exposure,
                concentration_profile=concentration_profile,
                risk_metrics=risk_metrics,
                stress_scenarios=cfo_stress_scenarios,
                recommendations=recommendations,
                executive_summary=executive_summary,
            )

            if ctx:
                await ctx.info(f"✅ CFO Liquidity Report сформирован: статус {executive_summary.overall_liquidity_status}")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("liquidity_status", executive_summary.overall_liquidity_status)
            span.set_attribute("recommendations_count", len(recommendations))

            return ToolResult.from_dict(output.model_dump(mode="json"))

        except ValueError as e:
            error_type = ErrorMapper.get_error_type_for_exception(e)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(e))
            span.set_attribute("error_type", error_type)
            if ctx:
                await ctx.error(f"❌ Ошибка валидации: {e}")
            error_model = ErrorMapper.map_exception(e)
            output = CfoLiquidityReport.from_error(error_model)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        except Exception as exc:
            error_type = ErrorMapper.get_error_type_for_exception(exc)
            if _metrics:
                _metrics.inc_tool_error(tool_name, error_type)
            span.set_attribute("error", str(exc))
            span.set_attribute("error_type", error_type)

            if ctx:
                await ctx.error(f"❌ Ошибка выполнения: {exc}")

            error_model = ErrorMapper.map_exception(exc)
            metadata = {
                "from_date": from_date,
                "to_date": to_date,
                "base_currency": base_currency,
                "positions_count": len(positions) if positions else 0,
            }
            output = CfoLiquidityReport.from_error(error_model, metadata=metadata)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)


__all__ = ["build_cfo_liquidity_report_core", "build_cfo_liquidity_report"]
