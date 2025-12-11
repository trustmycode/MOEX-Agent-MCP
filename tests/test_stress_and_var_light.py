from datetime import date, datetime, timezone
from types import SimpleNamespace
from statistics import NormalDist

import pytest

from moex_iss_sdk.models import OhlcvBar
from risk_analytics_mcp.calculations import compute_var_light, run_stress_scenarios
from risk_analytics_mcp.models import PortfolioAggregates, PortfolioPosition, PortfolioRiskInput, VarLightConfig
from risk_analytics_mcp.tools import compute_portfolio_risk_basic_core


class _StubIssClient:
    def __init__(self):
        self.settings = SimpleNamespace(base_url="http://stub-iss/", default_board="TQBR")

    def get_ohlcv_series(self, ticker: str, board: str, from_date, to_date, interval: str, max_lookback_days: int):
        base = 100.0 if ticker == "AAA" else 200.0
        return [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=base, high=base, low=base, close=base),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=base * 1.02, high=base * 1.02, low=base * 1.02, close=base * 1.02),
        ]


def test_equity_fx_stress_combines_equity_and_fx():
    aggregates = PortfolioAggregates(
        base_currency="RUB",
        asset_class_weights={"equity": 0.6},
        fx_exposure_weights={"USD": 0.4, "RUB": 0.6},
    )

    results = run_stress_scenarios(aggregates, ["equity_-10_fx_+20"])

    assert len(results) == 1
    assert results[0].id == "equity_-10_fx_+20"
    assert results[0].pnl_pct == pytest.approx(2.0)  # -10% * 0.6 + 20% * 0.4 = +2%


def test_rates_stress_uses_duration():
    aggregates = PortfolioAggregates(asset_class_weights={"fixed_income": 0.5}, fixed_income_duration_years=4.0)

    [rates] = run_stress_scenarios(aggregates, ["rates_+300bp"])

    assert rates.pnl_pct == pytest.approx(-6.0)  # -4y * 3% * 50% = -6%
    assert rates.drivers["duration_years"] == 4.0


def test_credit_stress_falls_back_to_fixed_income_weight():
    aggregates = PortfolioAggregates(asset_class_weights={"fixed_income": 0.4}, fixed_income_duration_years=3.0)

    [credit] = run_stress_scenarios(aggregates, ["credit_spreads_+150bp"])

    assert credit.pnl_pct == pytest.approx(-1.8)  # -3y * 1.5% * 40% = -1.8%
    assert "spread_shift_bps" in credit.drivers


def test_var_light_with_portfolio_volatility():
    config = VarLightConfig(confidence_level=0.99, horizon_days=10)
    var = compute_var_light(20.0, config)

    expected = NormalDist().inv_cdf(0.99) * (0.20 / 252 ** 0.5) * (10 ** 0.5) * 100
    assert var.var_pct == pytest.approx(expected, rel=1e-3)
    assert var.annualized_volatility_pct == pytest.approx(20.0)


def test_var_light_uses_reference_when_missing_vol():
    config = VarLightConfig(confidence_level=0.95, horizon_days=1, reference_volatility_pct=15.0)
    var = compute_var_light(None, config)

    assert var.annualized_volatility_pct == pytest.approx(15.0)
    assert var.var_pct > 0


def test_portfolio_risk_core_respects_requested_scenarios():
    iss = _StubIssClient()
    input_model = PortfolioRiskInput(
        positions=[PortfolioPosition(ticker="AAA", weight=1.0)],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 1, 2),
        stress_scenarios=["rates_+300bp"],
        aggregates=PortfolioAggregates(asset_class_weights={"fixed_income": 1.0}, fixed_income_duration_years=2.0),
        var_config=VarLightConfig(confidence_level=0.9, horizon_days=1),
    )

    output = compute_portfolio_risk_basic_core(input_model, iss, max_tickers=3, max_lookback_days=10)

    assert [scenario.id for scenario in output.stress_results] == ["rates_+300bp"]
    assert output.var_light is not None
    assert output.var_light.confidence_level == pytest.approx(0.9)
