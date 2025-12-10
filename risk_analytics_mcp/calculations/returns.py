"""
Функции построения рядов доходностей по OHLCV.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from moex_iss_sdk.models import OhlcvBar

DailyReturn = Tuple[date, float]


def compute_daily_returns(bars: Sequence[OhlcvBar]) -> List[DailyReturn]:
    """
    Построить ряд дневных доходностей (simple returns) из OHLCV.
    """
    if len(bars) < 2:
        return []
    sorted_bars = sorted(bars, key=lambda bar: bar.ts)
    returns: List[DailyReturn] = []
    prev_close = sorted_bars[0].close
    for bar in sorted_bars[1:]:
        if prev_close and prev_close != 0:
            ret = (bar.close - prev_close) / prev_close
            returns.append((bar.ts.date(), ret))
        prev_close = bar.close
    return returns


def normalize_weights(weights: Mapping[str, float]) -> Dict[str, float]:
    """
    Нормализовать веса в пределах [0, 1] так, чтобы сумма была равна 1.0.
    """
    total = sum(max(weight, 0.0) for weight in weights.values())
    if total <= 0:
        raise ValueError("Weights must sum to a positive value")
    return {ticker: max(weight, 0.0) / total for ticker, weight in weights.items()}


def build_returns_by_ticker(ohlcv_by_ticker: Mapping[str, Sequence[OhlcvBar]]) -> Dict[str, List[DailyReturn]]:
    """
    Построить карту тикер → дневные доходности.
    """
    return {ticker: compute_daily_returns(bars) for ticker, bars in ohlcv_by_ticker.items()}


def _common_dates(returns_by_ticker: Mapping[str, List[DailyReturn]]) -> List[date]:
    if not returns_by_ticker:
        return []
    if any(len(series) == 0 for series in returns_by_ticker.values()):
        return []
    date_sets = [set(return_date for return_date, _ in series) for series in returns_by_ticker.values()]
    if not date_sets:
        return []
    common = set.intersection(*date_sets)
    return sorted(common)


def aggregate_portfolio_returns(
    returns_by_ticker: Mapping[str, List[DailyReturn]],
    weights: Mapping[str, float],
    *,
    rebalance: str = "buy_and_hold",
) -> List[DailyReturn]:
    """
    Сагрегировать доходности портфеля по дневным рядам тикеров и весам.
    """
    if rebalance not in {"buy_and_hold", "monthly"}:
        raise ValueError(f"Unsupported rebalance policy: {rebalance}")
    if not returns_by_ticker:
        return []

    missing_weights = [ticker for ticker in returns_by_ticker.keys() if ticker not in weights]
    if missing_weights:
        raise ValueError(f"Missing weights for tickers: {', '.join(sorted(missing_weights))}")

    base_weights = normalize_weights({ticker: weights[ticker] for ticker in returns_by_ticker.keys()})
    date_index = _common_dates(returns_by_ticker)
    if not date_index:
        return []

    returns_map: Dict[str, Dict[date, float]] = {
        ticker: {point_date: value for point_date, value in series} for ticker, series in returns_by_ticker.items()
    }
    wealth: Dict[str, float] = {ticker: weight for ticker, weight in base_weights.items()}
    portfolio_returns: List[DailyReturn] = []
    prev_month = date_index[0].month

    for point_date in date_index:
        total_wealth = sum(wealth.values())
        if total_wealth <= 0:
            break

        day_return = 0.0
        for ticker, current_wealth in wealth.items():
            ticker_return = returns_map[ticker].get(point_date)
            if ticker_return is None:
                continue
            effective_weight = current_wealth / total_wealth if total_wealth else 0.0
            day_return += effective_weight * ticker_return

        # Обновляем стоимость каждой бумаги после применения дневной доходности
        for ticker in wealth.keys():
            ticker_return = returns_map[ticker].get(point_date)
            if ticker_return is None:
                continue
            wealth[ticker] = wealth[ticker] * (1 + ticker_return)

        total_wealth = sum(wealth.values())
        if rebalance == "monthly" and point_date.month != prev_month:
            prev_month = point_date.month
            wealth = {ticker: total_wealth * weight for ticker, weight in base_weights.items()}

        portfolio_returns.append((point_date, day_return))

    return portfolio_returns


__all__ = [
    "DailyReturn",
    "aggregate_portfolio_returns",
    "build_returns_by_ticker",
    "compute_daily_returns",
    "normalize_weights",
]
