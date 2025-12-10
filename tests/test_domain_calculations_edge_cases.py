"""
Граничные случаи для domain_calculations.
"""

from datetime import datetime, timezone

from moex_iss_mcp import domain_calculations as dc
from moex_iss_sdk.models import OhlcvBar


def _bar(close: float, open_: float | None = None, high: float | None = None, low: float | None = None, volume: float | None = None):
    return OhlcvBar(
        ts=datetime.now(timezone.utc),
        open=open_ if open_ is not None else close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=volume,
    )


def test_volatility_zero_when_prices_constant():
    bars = [_bar(100.0), _bar(100.0), _bar(100.0)]
    assert dc.calc_annualized_volatility(bars) == 0.0


def test_total_return_none_with_negative_first_close():
    bars = [_bar(-1.0), _bar(10.0)]
    assert dc.calc_total_return_pct(bars) is None


def test_avg_volume_ignores_zero_and_none():
    bars = [_bar(1.0, volume=0.0), _bar(1.0, volume=None)]
    assert dc.calc_avg_daily_volume(bars) is None


def test_intraday_volatility_all_none():
    assert dc.calc_intraday_volatility_estimate(None, None, None, 100.0) is None


def test_intraday_volatility_negative_prices():
    assert dc.calc_intraday_volatility_estimate(100.0, -1.0, -2.0, -1.0) is None


def test_intraday_volatility_high_lower_than_low():
    result = dc.calc_intraday_volatility_estimate(100.0, 90.0, 95.0, 105.0)
    assert result == 5.0  # fallback на open/close


def test_intraday_volatility_open_zero():
    assert dc.calc_intraday_volatility_estimate(0.0, 110.0, 90.0, 100.0) == 20.0
