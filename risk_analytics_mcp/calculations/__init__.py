"""
Расчётные функции для risk-analytics-mcp.
"""

from .portfolio_metrics import (
    calc_annualized_volatility_pct,
    calc_basic_portfolio_metrics,
    calc_concentration_metrics,
    calc_hhi,
    calc_max_drawdown_pct,
    calc_top_concentration_pct,
    calc_total_return_pct,
)
from .correlation import InsufficientDataError, compute_correlation_matrix
from .returns import (
    DailyReturn,
    aggregate_portfolio_returns,
    build_returns_by_ticker,
    compute_daily_returns,
    normalize_weights,
)
from .stress_var import (
    DEFAULT_FALLBACK_VOLATILITY_PCT,
    DEFAULT_SCENARIOS,
    compute_var_light,
    run_stress_scenarios,
)

__all__ = [
    "DailyReturn",
    "aggregate_portfolio_returns",
    "build_returns_by_ticker",
    "calc_annualized_volatility_pct",
    "calc_basic_portfolio_metrics",
    "calc_concentration_metrics",
    "calc_hhi",
    "calc_max_drawdown_pct",
    "calc_top_concentration_pct",
    "calc_total_return_pct",
    "compute_daily_returns",
    "compute_correlation_matrix",
    "InsufficientDataError",
    "normalize_weights",
    "DEFAULT_FALLBACK_VOLATILITY_PCT",
    "DEFAULT_SCENARIOS",
    "run_stress_scenarios",
    "compute_var_light",
]
