"""
Инструмент compute_portfolio_risk_basic для расчёта базовых метрик риска портфеля.

Вычисляет метрики риска, доходности, концентрации и стресс-сценарии для портфеля.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence

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
    calc_concentration_metrics,
    calc_annualized_volatility_pct,
    calc_max_drawdown_pct,
    calc_total_return_pct,
    compute_var_light,
    run_stress_scenarios,
)
from ..mcp_instance import mcp
from ..models import (
    ConcentrationMetrics,
    PortfolioAggregates,
    PortfolioMetrics,
    PortfolioPosition,
    PortfolioRiskBasicOutput,
    PortfolioRiskInput,
    PortfolioRiskPerInstrument,
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


def _validate_limits(input_model: PortfolioRiskInput, *, max_tickers: int, max_lookback_days: int) -> None:
    if len(input_model.positions) > max_tickers:
        raise TooManyTickersError(
            f"Too many tickers: {len(input_model.positions)} > {max_tickers}",
            details={"tickers": [p.ticker for p in input_model.positions]},
        )
    validate_date_range(input_model.from_date, input_model.to_date, max_lookback_days=max_lookback_days)


def _fetch_ohlcv_for_positions(
    iss_client: IssClient,
    positions: Sequence[PortfolioPosition],
    *,
    from_date,
    to_date,
    max_lookback_days: int,
):
    """Синхронно получить ряды OHLCV для позиций портфеля."""
    data: Dict[str, Sequence] = {}
    for position in positions:
        board = position.board or iss_client.settings.default_board
        data[position.ticker] = iss_client.get_ohlcv_series(
            ticker=position.ticker,
            board=board,
            from_date=from_date,
            to_date=to_date,
            interval="1d",
            max_lookback_days=max_lookback_days,
        )
    return data


async def _fetch_ohlcv_for_positions_async(
    positions: Sequence[PortfolioPosition],
    *,
    from_date,
    to_date,
    max_lookback_days: int,
):
    """Асинхронная версия получения OHLCV данных для позиций."""
    data: Dict[str, Sequence] = {}
    for position in positions:
        board = position.board or _iss_client.settings.default_board
        data[position.ticker] = await asyncio.to_thread(
            _iss_client.get_ohlcv_series,
            ticker=position.ticker,
            board=board,
            from_date=from_date,
            to_date=to_date,
            interval="1d",
            max_lookback_days=max_lookback_days,
        )
    return data


def _per_instrument_metrics(
    returns_by_ticker: Mapping[str, list[tuple]],
    weights: Mapping[str, float],
) -> list[PortfolioRiskPerInstrument]:
    items: list[PortfolioRiskPerInstrument] = []
    for ticker, returns in returns_by_ticker.items():
        series = [value for _, value in returns]
        items.append(
            PortfolioRiskPerInstrument(
                ticker=ticker,
                weight=weights.get(ticker, 0.0),
                total_return_pct=calc_total_return_pct(series),
                annualized_volatility_pct=calc_annualized_volatility_pct(series),
                max_drawdown_pct=calc_max_drawdown_pct(series),
            )
    )
    return items


def _resolve_aggregates(input_model: PortfolioRiskInput) -> PortfolioAggregates:
    aggregates = input_model.aggregates or PortfolioAggregates()
    asset_class_weights = aggregates.asset_class_weights or {"equity": 1.0}
    fx_exposure_weights = aggregates.fx_exposure_weights or {}

    return PortfolioAggregates(
        base_currency=aggregates.base_currency,
        asset_class_weights=asset_class_weights,
        fx_exposure_weights=fx_exposure_weights,
        fixed_income_duration_years=aggregates.fixed_income_duration_years,
        credit_spread_duration_years=aggregates.credit_spread_duration_years,
    )


def compute_portfolio_risk_basic_core(
    input_payload,
    iss_client: IssClient,
    *,
    max_tickers: int,
    max_lookback_days: int,
) -> PortfolioRiskBasicOutput:
    """
    Выполнить расчёт портфельных метрик без привязки к FastMCP.
    """
    input_model = input_payload if isinstance(input_payload, PortfolioRiskInput) else PortfolioRiskInput.model_validate(input_payload)
    _validate_limits(input_model, max_tickers=max_tickers, max_lookback_days=max_lookback_days)

    ohlcv_by_ticker = _fetch_ohlcv_for_positions(
        iss_client,
        input_model.positions,
        from_date=input_model.from_date,
        to_date=input_model.to_date,
        max_lookback_days=max_lookback_days,
    )
    returns_by_ticker = build_returns_by_ticker(ohlcv_by_ticker)
    weight_map = {pos.ticker: pos.weight for pos in input_model.positions}

    per_instrument = _per_instrument_metrics(returns_by_ticker, weight_map)
    portfolio_returns = aggregate_portfolio_returns(returns_by_ticker, weight_map, rebalance=input_model.rebalance)
    portfolio_metrics = PortfolioMetrics(**calc_basic_portfolio_metrics([value for _, value in portfolio_returns]))
    concentration_metrics = ConcentrationMetrics(**calc_concentration_metrics(weight_map))
    aggregates = _resolve_aggregates(input_model)

    stress_results = run_stress_scenarios(aggregates, input_model.stress_scenarios or None)
    var_light = compute_var_light(portfolio_metrics.annualized_volatility_pct, input_model.var_config)

    metadata = {
        "as_of": utc_now().isoformat(),
        "from_date": input_model.from_date.isoformat(),
        "to_date": input_model.to_date.isoformat(),
        "rebalance": input_model.rebalance,
        "tickers": list(weight_map.keys()),
        "iss_base_url": iss_client.settings.base_url,
        "stress_scenarios": [result.id for result in stress_results],
        "var_light_params": {
            "confidence_level": input_model.var_config.confidence_level,
            "horizon_days": input_model.var_config.horizon_days,
        },
    }

    return PortfolioRiskBasicOutput.success(
        metadata=metadata,
        per_instrument=per_instrument,
        portfolio_metrics=portfolio_metrics,
        concentration_metrics=concentration_metrics,
        stress_results=stress_results,
        var_light=var_light,
    )


@mcp.tool(
    name="compute_portfolio_risk_basic",
    description="""📊 Вычислить базовые метрики риска портфеля.

Инструмент рассчитывает метрики риска, доходности, концентрации и стресс-сценарии
для указанного портфеля за заданный период.

Примеры использования:
- Оценить риск портфеля из нескольких акций
- Рассчитать VaR и стресс-сценарии
- Проанализировать концентрацию портфеля
""",
)
async def compute_portfolio_risk_basic(
    positions: List[Dict[str, Any]] = Field(
        ...,
        description="Список позиций портфеля с тикерами и весами",
    ),
    from_date: str = Field(
        ...,
        description="Начальная дата периода в формате YYYY-MM-DD (включительно)",
    ),
    to_date: str = Field(
        ...,
        description="Конечная дата периода в формате YYYY-MM-DD (включительно)",
    ),
    rebalance: str = Field(
        default="buy_and_hold",
        description="Стратегия ребалансировки: 'buy_and_hold' или 'monthly'",
    ),
    aggregates: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Агрегированные характеристики портфеля для стресс-сценариев",
    ),
    stress_scenarios: Optional[List[str]] = Field(
        default=None,
        description="Список идентификаторов стресс-сценариев для расчёта",
    ),
    var_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Параметры для расчёта VaR (уровень доверия, горизонт)",
    ),
    ctx: Context = None,
) -> ToolResult:
    """
    Вычислить базовые метрики риска портфеля.

    Args:
        positions: Список позиций портфеля с тикерами и весами
        from_date: Начальная дата периода в формате YYYY-MM-DD (включительно)
        to_date: Конечная дата периода в формате YYYY-MM-DD (включительно)
        rebalance: Стратегия ребалансировки: 'buy_and_hold' или 'monthly'
        aggregates: Агрегированные характеристики портфеля для стресс-сценариев
        stress_scenarios: Список идентификаторов стресс-сценариев для расчёта
        var_config: Параметры для расчёта VaR (уровень доверия, горизонт)
        ctx: Контекст для логирования и отслеживания прогресса

    Returns:
        ToolResult: Результат с метриками риска портфеля

    Raises:
        McpError: При ошибках выполнения или валидации параметров
    """
    tool_name = "compute_portfolio_risk_basic"
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
                await ctx.info(f"🚀 Начинаем расчёт метрик риска для портфеля из {len(positions)} позиций")
                await ctx.report_progress(progress=0, total=100)

            # Настройка атрибутов спана
            span.set_attribute("positions_count", len(positions))
            span.set_attribute("from_date", from_date)
            span.set_attribute("to_date", to_date)
            span.set_attribute("rebalance", rebalance)

            # Валидация входных данных
            if ctx:
                await ctx.info("🔍 Валидация параметров")
                await ctx.report_progress(progress=10, total=100)

            payload = {
                "positions": positions,
                "from_date": from_date,
                "to_date": to_date,
                "rebalance": rebalance,
            }
            if aggregates is not None:
                payload["aggregates"] = aggregates
            if stress_scenarios is not None:
                payload["stress_scenarios"] = stress_scenarios
            if var_config is not None:
                payload["var_config"] = var_config

            input_model = PortfolioRiskInput.model_validate(payload)
            _validate_limits(input_model, max_tickers=_max_tickers, max_lookback_days=_max_lookback_days)

            # Получение данных
            if ctx:
                await ctx.info("📡 Запрос исторических данных")
                await ctx.report_progress(progress=20, total=100)

            ohlcv_by_ticker = await _fetch_ohlcv_for_positions_async(
                input_model.positions,
                from_date=input_model.from_date,
                to_date=input_model.to_date,
                max_lookback_days=_max_lookback_days,
            )

            if ctx:
                await ctx.info("📊 Расчёт доходностей")
                await ctx.report_progress(progress=40, total=100)

            returns_by_ticker = await asyncio.to_thread(build_returns_by_ticker, ohlcv_by_ticker)
            weight_map = {pos.ticker: pos.weight for pos in input_model.positions}

            if ctx:
                await ctx.info("📈 Расчёт метрик портфеля")
                await ctx.report_progress(progress=60, total=100)

            per_instrument = await asyncio.to_thread(_per_instrument_metrics, returns_by_ticker, weight_map)
            portfolio_returns = await asyncio.to_thread(
                aggregate_portfolio_returns, returns_by_ticker, weight_map, rebalance=input_model.rebalance
            )
            portfolio_metrics = PortfolioMetrics(
                **await asyncio.to_thread(calc_basic_portfolio_metrics, [value for _, value in portfolio_returns])
            )
            concentration_metrics = ConcentrationMetrics(
                **await asyncio.to_thread(calc_concentration_metrics, weight_map)
            )
            aggregates = _resolve_aggregates(input_model)

            if ctx:
                await ctx.info("🔬 Расчёт стресс-сценариев и VaR")
                await ctx.report_progress(progress=80, total=100)

            stress_results = await asyncio.to_thread(run_stress_scenarios, aggregates, input_model.stress_scenarios or None)
            var_light = await asyncio.to_thread(
                compute_var_light, portfolio_metrics.annualized_volatility_pct, input_model.var_config
            )

            metadata = {
                "as_of": utc_now().isoformat(),
                "from_date": input_model.from_date.isoformat(),
                "to_date": input_model.to_date.isoformat(),
                "rebalance": input_model.rebalance,
                "tickers": list(weight_map.keys()),
                "iss_base_url": _iss_client.settings.base_url,
                "stress_scenarios": [result.id for result in stress_results],
                "var_light_params": {
                    "confidence_level": input_model.var_config.confidence_level,
                    "horizon_days": input_model.var_config.horizon_days,
                },
            }

            output = PortfolioRiskBasicOutput.success(
                metadata=metadata,
                per_instrument=per_instrument,
                portfolio_metrics=portfolio_metrics,
                concentration_metrics=concentration_metrics,
                stress_results=stress_results,
                var_light=var_light,
            )

            if ctx:
                await ctx.info("✅ Метрики риска рассчитаны успешно")
                await ctx.report_progress(progress=100, total=100)

            span.set_attribute("success", True)
            span.set_attribute("positions_count", len(positions))

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
            output = PortfolioRiskBasicOutput.from_error(error_model)
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
                "rebalance": rebalance,
                "tickers": [pos.get("ticker") for pos in positions if isinstance(pos, dict)],
            }
            output = PortfolioRiskBasicOutput.from_error(error_model, metadata=metadata)
            return ToolResult.from_dict(output.model_dump(mode="json"))

        finally:
            if _metrics and start_ts:
                _metrics.observe_latency(tool_name, time.perf_counter() - start_ts)


__all__ = ["compute_portfolio_risk_basic_core", "compute_portfolio_risk_basic"]
