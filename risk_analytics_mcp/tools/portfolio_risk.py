"""
Реализация инструмента compute_portfolio_risk_basic.
"""

from __future__ import annotations

from typing import Dict, Mapping, Sequence

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
from ..models import (
    ConcentrationMetrics,
    PortfolioAggregates,
    PortfolioMetrics,
    PortfolioPosition,
    PortfolioRiskBasicOutput,
    PortfolioRiskInput,
    PortfolioRiskPerInstrument,
)


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


def compute_portfolio_risk_basic_tool(
    payload,
    iss_client: IssClient,
    *,
    max_tickers: int,
    max_lookback_days: int,
) -> dict:
    """
    Обёртка, преобразующая исключения в стандартный формат ошибки инструмента.
    """
    try:
        output_model = compute_portfolio_risk_basic_core(
            payload,
            iss_client,
            max_tickers=max_tickers,
            max_lookback_days=max_lookback_days,
        )
        return output_model.model_dump(mode="json")
    except Exception as exc:
        error_type = ErrorMapper.get_error_type_for_exception(exc)
        error_model = ErrorMapper.map_exception(exc)
        metadata = {}
        if isinstance(payload, dict):
            metadata = {
                "from_date": payload.get("from_date"),
                "to_date": payload.get("to_date"),
                "rebalance": payload.get("rebalance"),
                "tickers": [pos.get("ticker") for pos in payload.get("positions", []) if isinstance(pos, dict)],
            }
        return PortfolioRiskBasicOutput.from_error(error_model, metadata=metadata).model_dump(mode="json")


__all__ = ["compute_portfolio_risk_basic_core", "compute_portfolio_risk_basic_tool"]
