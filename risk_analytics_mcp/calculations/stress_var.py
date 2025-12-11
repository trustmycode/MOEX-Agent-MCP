"""
Стресс-сценарии и лёгкий Var_light для портфельного риска.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Mapping, Sequence

from ..models import PortfolioAggregates, StressScenarioResult, VarLightConfig, VarLightResult

DEFAULT_SCENARIOS = [
    {
        "id": "equity_-10_fx_+20",
        "description": "Падение акций на 10% и ослабление базовой валюты на 20% для FX-экспозиции.",
    },
    {
        "id": "rates_+300bp",
        "description": "Сдвиг доходностей облигаций на +300 bps с учётом дюрации долгового портфеля.",
    },
    {
        "id": "credit_spreads_+150bp",
        "description": "Расширение кредитных спредов на +150 bps для кредитной части портфеля.",
    },
]

DEFAULT_FALLBACK_VOLATILITY_PCT = 20.0


def _normalized_asset_weights(aggregates: PortfolioAggregates) -> Mapping[str, float]:
    """
    Нормализовать карту весов классов активов и задать дефолт (equity=1.0), если не указано.
    """
    weights = {key.lower(): max(value, 0.0) for key, value in aggregates.asset_class_weights.items()}
    if not weights:
        weights = {"equity": 1.0}
    return weights


def _fx_exposed_weight(aggregates: PortfolioAggregates) -> float:
    fx_weights = {currency.upper(): max(weight, 0.0) for currency, weight in aggregates.fx_exposure_weights.items()}
    base_currency = (aggregates.base_currency or "RUB").upper()
    return sum(weight for currency, weight in fx_weights.items() if currency != base_currency)


def _weight_lookup(weights: Mapping[str, float], keys: Sequence[str]) -> float:
    for key in keys:
        if key in weights:
            return weights[key]
    return 0.0


def _scenario_equity_fx(aggregates: PortfolioAggregates, asset_weights: Mapping[str, float]) -> StressScenarioResult:
    equity_weight = _weight_lookup(asset_weights, ["equity", "stocks"])
    fx_weight = _fx_exposed_weight(aggregates)

    equity_shock = -0.10
    fx_shock = 0.20
    pnl = (equity_weight * equity_shock) + (fx_weight * fx_shock)

    return StressScenarioResult(
        id="equity_-10_fx_+20",
        description="Падение акций на 10% и ослабление базовой валюты на 20%.",
        pnl_pct=pnl * 100.0,
        drivers={
            "equity_weight_pct": equity_weight * 100.0,
            "fx_exposed_weight_pct": fx_weight * 100.0,
            "equity_shock_pct": equity_shock * 100.0,
            "fx_shock_pct": fx_shock * 100.0,
        },
    )


def _scenario_rates(aggregates: PortfolioAggregates, asset_weights: Mapping[str, float]) -> StressScenarioResult:
    fixed_income_weight = _weight_lookup(asset_weights, ["fixed_income", "bonds", "gov_bonds", "corp_bonds"])
    duration = aggregates.fixed_income_duration_years or 0.0
    rate_shift = 0.03  # 300 bps
    pnl = -duration * rate_shift * fixed_income_weight

    return StressScenarioResult(
        id="rates_+300bp",
        description="Рост ставок на 300 bps с учётом дюрации долгового портфеля.",
        pnl_pct=pnl * 100.0,
        drivers={
            "fixed_income_weight_pct": fixed_income_weight * 100.0,
            "duration_years": duration,
            "rate_shift_bps": rate_shift * 10_000,
        },
    )


def _scenario_credit(aggregates: PortfolioAggregates, asset_weights: Mapping[str, float]) -> StressScenarioResult:
    credit_weight = _weight_lookup(asset_weights, ["credit", "credit_spreads", "corp_bonds"])
    if credit_weight == 0.0:
        credit_weight = _weight_lookup(asset_weights, ["fixed_income", "bonds"])

    duration = aggregates.credit_spread_duration_years or aggregates.fixed_income_duration_years or 0.0
    spread_shift = 0.015  # 150 bps
    pnl = -duration * spread_shift * credit_weight

    return StressScenarioResult(
        id="credit_spreads_+150bp",
        description="Расширение кредитных спредов на 150 bps по кредитной части портфеля.",
        pnl_pct=pnl * 100.0,
        drivers={
            "credit_weight_pct": credit_weight * 100.0,
            "spread_duration_years": duration,
            "spread_shift_bps": spread_shift * 10_000,
        },
    )


SCENARIO_HANDLERS = {
    "equity_-10_fx_+20": _scenario_equity_fx,
    "rates_+300bp": _scenario_rates,
    "credit_spreads_+150bp": _scenario_credit,
}


def run_stress_scenarios(aggregates: PortfolioAggregates, scenario_ids: Sequence[str] | None = None) -> list[StressScenarioResult]:
    """
    Запустить набор фиксированных стресс-сценариев и вернуть список результатов.
    """
    asset_weights = _normalized_asset_weights(aggregates)
    ids = list(scenario_ids) if scenario_ids else [item["id"] for item in DEFAULT_SCENARIOS]

    results: list[StressScenarioResult] = []
    for scenario_id in ids:
        handler = SCENARIO_HANDLERS.get(scenario_id)
        if handler is None:
            continue
        results.append(handler(aggregates, asset_weights))
    return results


def compute_var_light(
    portfolio_volatility_pct: float | None,
    config: VarLightConfig,
    *,
    fallback_volatility_pct: float = DEFAULT_FALLBACK_VOLATILITY_PCT,
) -> VarLightResult:
    """
    Parametric VaR (Var_light) на основе годовой волатильности и уровня доверия.
    """
    volatility_pct = portfolio_volatility_pct or config.reference_volatility_pct or fallback_volatility_pct
    volatility_pct = float(volatility_pct)

    if volatility_pct <= 0:
        return VarLightResult(
            method=config.method,
            confidence_level=config.confidence_level,
            horizon_days=config.horizon_days,
            annualized_volatility_pct=0.0,
            var_pct=0.0,
        )

    z_score = NormalDist().inv_cdf(config.confidence_level)
    daily_vol = volatility_pct / 100.0 / math.sqrt(252.0)
    horizon_scale = math.sqrt(config.horizon_days)
    var_pct = z_score * daily_vol * horizon_scale * 100.0

    return VarLightResult(
        method=config.method,
        confidence_level=config.confidence_level,
        horizon_days=config.horizon_days,
        annualized_volatility_pct=volatility_pct,
        var_pct=var_pct,
    )


__all__ = ["run_stress_scenarios", "compute_var_light", "DEFAULT_SCENARIOS", "DEFAULT_FALLBACK_VOLATILITY_PCT"]
