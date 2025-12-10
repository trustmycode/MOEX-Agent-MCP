from datetime import datetime, timezone, date

import pytest

from moex_iss_sdk.models import OhlcvBar
from risk_analytics_mcp.calculations import (
    aggregate_portfolio_returns,
    build_returns_by_ticker,
    calc_annualized_volatility_pct,
    calc_basic_portfolio_metrics,
    calc_concentration_metrics,
    calc_hhi,
    calc_max_drawdown_pct,
    calc_top_concentration_pct,
    calc_total_return_pct,
    compute_daily_returns,
    normalize_weights,
)


def make_bar(day: int, close: float) -> OhlcvBar:
    return OhlcvBar(
        ts=datetime(2024, 1, day, tzinfo=timezone.utc),
        open=close,
        high=close,
        low=close,
        close=close,
    )


def test_compute_daily_returns_sorts_and_calculates():
    bars = [
        make_bar(2, 110.0),
        make_bar(1, 100.0),
    ]

    returns = compute_daily_returns(bars)

    assert returns == [(date(2024, 1, 2), 0.1)]


def test_compute_daily_returns_empty_when_not_enough_points():
    returns = compute_daily_returns([make_bar(1, 100.0)])
    assert returns == []


def test_build_returns_by_ticker_and_aggregate_buy_and_hold():
    ohlcv = {
        "AAA": [make_bar(1, 100.0), make_bar(2, 101.0), make_bar(3, 102.01)],
        "BBB": [make_bar(1, 200.0), make_bar(2, 204.0), make_bar(3, 204.0)],
    }
    returns_by_ticker = build_returns_by_ticker(ohlcv)

    portfolio_returns = aggregate_portfolio_returns(returns_by_ticker, {"AAA": 0.6, "BBB": 0.4})

    assert [point[0] for point in portfolio_returns] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert portfolio_returns[0][1] == pytest.approx(0.014)
    assert portfolio_returns[1][1] == pytest.approx(0.005976, rel=1e-3)


def test_aggregate_monthly_rebalance_resets_weights():
    returns_by_ticker = {
        "AAA": [(date(2024, 1, 2), 0.1), (date(2024, 2, 1), 0.0), (date(2024, 2, 2), 0.0)],
        "BBB": [(date(2024, 1, 2), 0.0), (date(2024, 2, 1), 0.0), (date(2024, 2, 2), -0.1)],
    }

    monthly = aggregate_portfolio_returns(returns_by_ticker, {"AAA": 0.5, "BBB": 0.5}, rebalance="monthly")
    buy_and_hold = aggregate_portfolio_returns(returns_by_ticker, {"AAA": 0.5, "BBB": 0.5}, rebalance="buy_and_hold")

    assert monthly[2][1] == pytest.approx(-0.05)
    assert buy_and_hold[2][1] == pytest.approx(-0.0476, rel=1e-3)


def test_aggregate_returns_missing_weights_and_disjoint_dates():
    returns_by_ticker = {
        "AAA": [(date(2024, 1, 2), 0.1)],
        "BBB": [(date(2024, 1, 3), -0.1)],
    }

    with pytest.raises(ValueError):
        aggregate_portfolio_returns(returns_by_ticker, {"AAA": 1.0}, rebalance="buy_and_hold")

    empty = aggregate_portfolio_returns(returns_by_ticker, {"AAA": 0.5, "BBB": 0.5}, rebalance="buy_and_hold")
    assert empty == []


def test_normalize_weights_and_concentration_metrics():
    normalized = normalize_weights({"AAA": 0.5, "BBB": 0.3, "CCC": 0.2})
    assert pytest.approx(sum(normalized.values())) == 1.0

    concentration = calc_concentration_metrics(normalized)
    assert concentration["top1_weight_pct"] == pytest.approx(50.0)
    assert concentration["top3_weight_pct"] == pytest.approx(100.0)
    assert concentration["top5_weight_pct"] == pytest.approx(100.0)
    assert concentration["hhi"] == pytest.approx(0.38)


def test_basic_portfolio_metrics_and_drawdown():
    returns = [0.1, -0.05, 0.02]

    total_return = calc_total_return_pct(returns)
    volatility = calc_annualized_volatility_pct(returns, trading_days_per_year=10)
    max_dd = calc_max_drawdown_pct(returns)
    metrics = calc_basic_portfolio_metrics(returns)

    assert total_return == pytest.approx(6.59, rel=1e-3)
    assert volatility is not None and volatility > 0
    assert max_dd == pytest.approx(5.0)
    assert metrics["total_return_pct"] == pytest.approx(total_return)
    assert metrics["max_drawdown_pct"] == pytest.approx(max_dd)


def test_basic_metrics_return_none_on_degenerate_inputs():
    assert calc_annualized_volatility_pct([0.1]) is None
    assert calc_max_drawdown_pct([]) is None
    assert calc_total_return_pct([]) is None


def test_top_concentration_and_hhi_handle_empty():
    assert calc_top_concentration_pct([], 3) is None
    assert calc_hhi([]) is None


def test_normalize_weights_raises_on_zero_sum():
    with pytest.raises(ValueError):
        normalize_weights({"AAA": 0.0})
