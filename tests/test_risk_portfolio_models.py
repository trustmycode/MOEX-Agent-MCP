from datetime import date

import pytest

from moex_iss_sdk.error_mapper import ToolErrorModel
from risk_analytics_mcp.models import (
    ConcentrationMetrics,
    PortfolioMetrics,
    PortfolioPosition,
    PortfolioRiskBasicOutput,
    PortfolioRiskInput,
    PortfolioRiskPerInstrument,
    StressScenarioResult,
    VarLightResult,
)


def test_portfolio_risk_input_validates_weights_and_uniqueness():
    payload = PortfolioRiskInput(
        positions=[
            PortfolioPosition(ticker="sber", weight=0.6),
            PortfolioPosition(ticker="gazp", weight=0.4),
        ],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 2, 1),
        rebalance="monthly",
    )

    assert payload.positions[0].ticker == "SBER"
    assert payload.rebalance == "monthly"


def test_portfolio_risk_input_rejects_bad_weights_and_duplicates():
    with pytest.raises(ValueError):
        PortfolioRiskInput(
            positions=[
                PortfolioPosition(ticker="SBER", weight=0.5),
                PortfolioPosition(ticker="GAZP", weight=0.3),
            ],
            from_date=date(2024, 1, 1),
            to_date=date(2024, 2, 1),
        )

    with pytest.raises(ValueError):
        PortfolioRiskInput(
            positions=[
                PortfolioPosition(ticker="SBER", weight=0.5),
                PortfolioPosition(ticker="SBER", weight=0.5),
            ],
            from_date=date(2024, 1, 1),
            to_date=date(2024, 2, 1),
        )


def test_portfolio_risk_input_invalid_rebalance_and_dates():
    with pytest.raises(ValueError):
        PortfolioRiskInput(
            positions=[PortfolioPosition(ticker="SBER", weight=1.0)],
            from_date=date(2024, 2, 1),
            to_date=date(2024, 1, 1),
        )

    with pytest.raises(ValueError):
        PortfolioRiskInput(
            positions=[PortfolioPosition(ticker="SBER", weight=1.0)],
            from_date=date(2024, 1, 1),
            to_date=date(2024, 1, 2),
            rebalance="weekly",  # неподдерживаемое значение
        )


def test_portfolio_position_rejects_empty_ticker_and_non_positive_weight():
    with pytest.raises(ValueError):
        PortfolioPosition(ticker="   ", weight=0.5)

    with pytest.raises(ValueError):
        PortfolioPosition(ticker="SBER", weight=0.0)

    with pytest.raises(ValueError):
        PortfolioPosition(ticker="SBER", weight=-0.1)

    with pytest.raises(ValueError):
        PortfolioPosition(ticker="SBER", weight=0.1, board="   ")


def test_portfolio_risk_basic_output_helpers():
    error = ToolErrorModel(error_type="INVALID_TICKER", message="bad ticker")
    per_instrument = [PortfolioRiskPerInstrument(ticker="SBER", weight=0.6)]
    output = PortfolioRiskBasicOutput.success(
        metadata={"from_date": "2024-01-01"},
        per_instrument=per_instrument,
        portfolio_metrics=PortfolioMetrics(total_return_pct=5.0),
        concentration_metrics=ConcentrationMetrics(top1_weight_pct=60.0),
        stress_results=[
            StressScenarioResult(
                id="equity_-10_fx_+20",
                description="equity crash",
                pnl_pct=-10.0,
                drivers={"equity_weight_pct": 100.0},
            )
        ],
        var_light=VarLightResult(
            method="parametric_normal",
            confidence_level=0.95,
            horizon_days=1,
            annualized_volatility_pct=15.0,
            var_pct=2.0,
        ),
    )
    assert output.error is None
    assert output.per_instrument[0].ticker == "SBER"
    assert output.var_light is not None
    assert output.stress_results

    errored = PortfolioRiskBasicOutput.from_error(error, metadata={"from_date": "2024-01-01"})
    assert errored.error.error_type == "INVALID_TICKER"
    assert errored.per_instrument == []
    assert errored.var_light is None
    assert errored.stress_results == []
