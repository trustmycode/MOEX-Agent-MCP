"""
Базовые численные расчёты для compute_portfolio_risk_basic.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional, Sequence


def calc_total_return_pct(returns: Sequence[float]) -> Optional[float]:
    """
    Совокупная доходность (в процентах) по ряду дневных доходностей.
    """
    if not returns:
        return None
    wealth = 1.0
    for ret in returns:
        wealth *= 1 + ret
    return (wealth - 1.0) * 100


def calc_annualized_volatility_pct(returns: Sequence[float], *, trading_days_per_year: int = 252) -> Optional[float]:
    """
    Годовая волатильность (в процентах) на основе дневных доходностей.
    """
    if len(returns) < 2:
        return None
    mean_ret = sum(returns) / len(returns)
    variance = sum((ret - mean_ret) ** 2 for ret in returns) / (len(returns) - 1)
    volatility = math.sqrt(variance) * math.sqrt(trading_days_per_year)
    return volatility * 100


def calc_max_drawdown_pct(returns: Sequence[float]) -> Optional[float]:
    """
    Максимальная просадка (в процентах) по ряду доходностей.
    """
    if not returns:
        return None
    peak = 1.0
    equity = 1.0
    max_drawdown = 0.0
    for ret in returns:
        equity *= 1 + ret
        if equity > peak:
            peak = equity
        if peak > 0:
            drawdown = (equity / peak) - 1.0
            max_drawdown = min(max_drawdown, drawdown)
    return abs(max_drawdown) * 100


def calc_top_concentration_pct(weights: Iterable[float], top_n: int) -> Optional[float]:
    """
    Суммарный вес топ-N бумаг в процентах.
    """
    weights_list = [w for w in weights if w is not None and w >= 0]
    if not weights_list:
        return None
    sorted_weights = sorted(weights_list, reverse=True)
    top_slice = sorted_weights[:top_n]
    return sum(top_slice) * 100


def calc_hhi(weights: Iterable[float]) -> Optional[float]:
    """
    Индекс Херфиндаля–Хиршмана для набора весов (0..1).
    """
    weights_list = [w for w in weights if w is not None and w >= 0]
    if not weights_list:
        return None
    total = sum(weights_list)
    if total <= 0:
        return None
    normalized = [w / total for w in weights_list]
    return sum(weight ** 2 for weight in normalized)


def calc_concentration_metrics(weights: Mapping[str, float]) -> dict[str, Optional[float]]:
    """
    Собрать концентрационные метрики на основе словаря весов.
    """
    weights_values = list(weights.values())
    return {
        "top1_weight_pct": calc_top_concentration_pct(weights_values, 1),
        "top3_weight_pct": calc_top_concentration_pct(weights_values, 3),
        "top5_weight_pct": calc_top_concentration_pct(weights_values, 5),
        "hhi": calc_hhi(weights_values),
    }


def calc_basic_portfolio_metrics(returns: Sequence[float]) -> dict[str, Optional[float]]:
    """
    Рассчитать базовые метрики портфеля по ряду дневных доходностей.
    """
    return {
        "total_return_pct": calc_total_return_pct(returns),
        "annualized_volatility_pct": calc_annualized_volatility_pct(returns),
        "max_drawdown_pct": calc_max_drawdown_pct(returns),
    }


__all__ = [
    "calc_annualized_volatility_pct",
    "calc_basic_portfolio_metrics",
    "calc_concentration_metrics",
    "calc_hhi",
    "calc_max_drawdown_pct",
    "calc_top_concentration_pct",
    "calc_total_return_pct",
]
