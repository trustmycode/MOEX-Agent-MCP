"""
Расчётные функции для CFO Liquidity Report (Scenario 9).

Модуль реализует:
- Агрегацию профиля ликвидности по корзинам
- Расчёт валютной экспозиции
- Формирование рекомендаций для CFO
- Определение executive summary
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal, Mapping, Sequence

from ..models import (
    AssetClassWeight,
    CfoConcentrationProfile,
    CfoExecutiveSummary,
    CfoLiquidityPosition,
    CfoRecommendation,
    CfoRiskMetrics,
    CfoStressScenarioResult,
    CovenantBreach,
    CovenantLimits,
    CurrencyExposure,
    CurrencyExposureItem,
    DurationProfile,
    LiquidityBucket,
    LiquidityProfile,
    PortfolioAggregates,
    StressScenarioResult,
    VarLightResult,
)

LIQUIDITY_BUCKETS_ORDER: list[Literal["0-7d", "8-30d", "31-90d", "90d+"]] = [
    "0-7d",
    "8-30d",
    "31-90d",
    "90d+",
]


def build_liquidity_profile(
    positions: Sequence[CfoLiquidityPosition],
    total_portfolio_value: float | None = None,
) -> LiquidityProfile:
    """
    Построить профиль ликвидности из позиций портфеля.
    """
    bucket_weights: dict[str, float] = defaultdict(float)
    bucket_tickers: dict[str, list[str]] = defaultdict(list)

    for pos in positions:
        bucket = pos.liquidity_bucket
        bucket_weights[bucket] += pos.weight
        bucket_tickers[bucket].append(pos.ticker)

    buckets: list[LiquidityBucket] = []
    for bucket_id in LIQUIDITY_BUCKETS_ORDER:
        weight = bucket_weights.get(bucket_id, 0.0)
        value = weight * total_portfolio_value if total_portfolio_value else None
        buckets.append(
            LiquidityBucket(
                bucket=bucket_id,
                weight_pct=round(weight * 100, 2),
                value=round(value, 2) if value else None,
                tickers=bucket_tickers.get(bucket_id, []),
            )
        )

    quick_ratio = bucket_weights.get("0-7d", 0.0)
    short_term_ratio = quick_ratio + bucket_weights.get("8-30d", 0.0)

    return LiquidityProfile(
        buckets=buckets,
        quick_ratio_pct=round(quick_ratio * 100, 2),
        short_term_ratio_pct=round(short_term_ratio * 100, 2),
    )


def build_duration_profile(
    positions: Sequence[CfoLiquidityPosition],
    aggregates: PortfolioAggregates | None = None,
) -> DurationProfile | None:
    """
    Построить профиль дюрации для fixed income части портфеля.
    """
    fixed_income_weight = sum(
        pos.weight for pos in positions if pos.asset_class in ("fixed_income", "credit")
    )

    if fixed_income_weight <= 0:
        return None

    duration = None
    credit_duration = None

    if aggregates:
        duration = aggregates.fixed_income_duration_years
        credit_duration = aggregates.credit_spread_duration_years

    return DurationProfile(
        portfolio_duration_years=duration,
        fixed_income_weight_pct=round(fixed_income_weight * 100, 2),
        credit_spread_duration_years=credit_duration,
    )


def build_currency_exposure(
    positions: Sequence[CfoLiquidityPosition],
    base_currency: str = "RUB",
    total_portfolio_value: float | None = None,
) -> CurrencyExposure:
    """
    Построить валютную структуру портфеля.
    """
    currency_weights: dict[str, float] = defaultdict(float)

    for pos in positions:
        currency = pos.currency.upper()
        currency_weights[currency] += pos.weight

    by_currency: list[CurrencyExposureItem] = []
    fx_risk_weight = 0.0

    for currency, weight in sorted(currency_weights.items(), key=lambda x: -x[1]):
        value = weight * total_portfolio_value if total_portfolio_value else None
        by_currency.append(
            CurrencyExposureItem(
                currency=currency,
                weight_pct=round(weight * 100, 2),
                value=round(value, 2) if value else None,
            )
        )
        if currency != base_currency.upper():
            fx_risk_weight += weight

    return CurrencyExposure(
        by_currency=by_currency,
        fx_risk_pct=round(fx_risk_weight * 100, 2) if fx_risk_weight > 0 else 0.0,
    )


def build_concentration_profile(
    positions: Sequence[CfoLiquidityPosition],
) -> CfoConcentrationProfile:
    """
    Построить профиль концентрации для CFO-отчёта.
    """
    weights = [pos.weight for pos in positions]
    sorted_weights = sorted(weights, reverse=True)

    top1 = sorted_weights[0] if len(sorted_weights) >= 1 else 0.0
    top3 = sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else sum(sorted_weights)
    top5 = sum(sorted_weights[:5]) if len(sorted_weights) >= 5 else sum(sorted_weights)

    # HHI = sum(weight^2)
    hhi = sum(w * w for w in weights)

    # Агрегация по классам активов
    asset_class_weights: dict[str, float] = defaultdict(float)
    for pos in positions:
        asset_class_weights[pos.asset_class] += pos.weight

    by_asset_class = [
        AssetClassWeight(asset_class=ac, weight_pct=round(w * 100, 2))
        for ac, w in sorted(asset_class_weights.items(), key=lambda x: -x[1])
    ]

    return CfoConcentrationProfile(
        top1_weight_pct=round(top1 * 100, 2),
        top3_weight_pct=round(top3 * 100, 2),
        top5_weight_pct=round(top5 * 100, 2),
        hhi=round(hhi, 4),
        by_asset_class=by_asset_class,
    )


def build_cfo_stress_scenarios(
    stress_results: list[StressScenarioResult],
    total_portfolio_value: float | None = None,
    liquidity_profile: LiquidityProfile | None = None,
    covenant_limits: CovenantLimits | None = None,
) -> list[CfoStressScenarioResult]:
    """
    Трансформировать результаты стресс-сценариев в CFO-формат с ковенант-чеками.
    """
    # Добавляем base_case
    cfo_scenarios: list[CfoStressScenarioResult] = [
        CfoStressScenarioResult(
            id="base_case",
            description="Базовый сценарий — без стрессов.",
            pnl_pct=0.0,
            pnl_value=0.0,
            liquidity_ratio_after=liquidity_profile.short_term_ratio_pct if liquidity_profile else None,
            covenant_breaches=[],
            drivers={},
        )
    ]

    for result in stress_results:
        pnl_value = (result.pnl_pct / 100.0) * total_portfolio_value if total_portfolio_value else None

        # Простая эвристика: ликвидность после стресса
        liquidity_after = None
        if liquidity_profile and liquidity_profile.short_term_ratio_pct:
            # При стрессе ликвидность может снижаться пропорционально потерям
            stress_factor = max(0, 1 + result.pnl_pct / 100.0)
            liquidity_after = liquidity_profile.short_term_ratio_pct * stress_factor

        # Проверка ковенант
        breaches = _check_covenant_breaches(result, covenant_limits, liquidity_after)

        cfo_scenarios.append(
            CfoStressScenarioResult(
                id=result.id,
                description=result.description,
                pnl_pct=round(result.pnl_pct, 2),
                pnl_value=round(pnl_value, 2) if pnl_value else None,
                liquidity_ratio_after=round(liquidity_after, 2) if liquidity_after else None,
                covenant_breaches=breaches,
                drivers=result.drivers,
            )
        )

    return cfo_scenarios


def _check_covenant_breaches(
    stress_result: StressScenarioResult,
    limits: CovenantLimits | None,
    liquidity_after: float | None,
) -> list[CovenantBreach]:
    """
    Проверить нарушения ковенант при стресс-сценарии.
    """
    breaches: list[CovenantBreach] = []

    if not limits:
        return breaches

    # Проверка ликвидности
    if limits.min_liquidity_ratio and liquidity_after is not None:
        if liquidity_after < limits.min_liquidity_ratio * 100:
            breaches.append(
                CovenantBreach(
                    code="LIQUIDITY_RATIO",
                    description=f"Коэффициент ликвидности ({liquidity_after:.1f}%) ниже минимального ({limits.min_liquidity_ratio * 100:.1f}%)",
                    limit=limits.min_liquidity_ratio * 100,
                    actual=liquidity_after,
                )
            )

    return breaches


def build_recommendations(
    liquidity_profile: LiquidityProfile,
    concentration_profile: CfoConcentrationProfile,
    currency_exposure: CurrencyExposure,
    duration_profile: DurationProfile | None,
    stress_scenarios: list[CfoStressScenarioResult],
) -> list[CfoRecommendation]:
    """
    Сформировать рекомендации для CFO на основе анализа портфеля.
    """
    recommendations: list[CfoRecommendation] = []

    # Ликвидность
    if liquidity_profile.quick_ratio_pct and liquidity_profile.quick_ratio_pct < 20:
        recommendations.append(
            CfoRecommendation(
                priority="high",
                category="liquidity",
                title="Низкая доля высоколиквидных активов",
                description=f"Доля активов с ликвидностью 0-7 дней составляет {liquidity_profile.quick_ratio_pct}%, что ниже рекомендуемых 20%.",
                action="Рассмотреть увеличение доли денежных средств или краткосрочных облигаций.",
            )
        )
    elif liquidity_profile.quick_ratio_pct and liquidity_profile.quick_ratio_pct < 30:
        recommendations.append(
            CfoRecommendation(
                priority="medium",
                category="liquidity",
                title="Умеренный уровень ликвидности",
                description=f"Доля высоколиквидных активов ({liquidity_profile.quick_ratio_pct}%) находится на приемлемом, но не оптимальном уровне.",
                action="Мониторить уровень ликвидности и иметь план по оперативному увеличению при необходимости.",
            )
        )

    # Концентрация
    if concentration_profile.top1_weight_pct and concentration_profile.top1_weight_pct > 25:
        recommendations.append(
            CfoRecommendation(
                priority="high",
                category="concentration",
                title="Высокая концентрация в одной позиции",
                description=f"Крупнейшая позиция занимает {concentration_profile.top1_weight_pct}% портфеля, что создаёт существенный идиосинкратический риск.",
                action="Снизить долю крупнейшей позиции до уровня не более 20-25%.",
            )
        )

    if concentration_profile.hhi and concentration_profile.hhi > 0.18:
        recommendations.append(
            CfoRecommendation(
                priority="medium",
                category="concentration",
                title="Повышенная концентрация портфеля",
                description=f"Индекс Херфиндаля-Хиршмана ({concentration_profile.hhi:.3f}) указывает на недостаточную диверсификацию.",
                action="Увеличить количество позиций или перераспределить веса для улучшения диверсификации.",
            )
        )

    # Валютный риск
    if currency_exposure.fx_risk_pct and currency_exposure.fx_risk_pct > 30:
        recommendations.append(
            CfoRecommendation(
                priority="medium",
                category="fx_risk",
                title="Существенная валютная экспозиция",
                description=f"Доля активов в иностранной валюте составляет {currency_exposure.fx_risk_pct}%, что создаёт валютный риск.",
                action="Рассмотреть хеджирование валютного риска или снижение FX-экспозиции.",
            )
        )

    # Дюрация
    if duration_profile and duration_profile.portfolio_duration_years:
        if duration_profile.portfolio_duration_years > 5:
            recommendations.append(
                CfoRecommendation(
                    priority="medium",
                    category="duration",
                    title="Высокая дюрация долгового портфеля",
                    description=f"Дюрация {duration_profile.portfolio_duration_years:.1f} лет создаёт значительную чувствительность к изменению процентных ставок.",
                    action="При ожидании роста ставок рассмотреть сокращение дюрации.",
                )
            )

    # Стресс-сценарии
    worst_scenario = min(stress_scenarios, key=lambda s: s.pnl_pct, default=None)
    if worst_scenario and worst_scenario.pnl_pct < -10:
        recommendations.append(
            CfoRecommendation(
                priority="high",
                category="stress_resilience",
                title="Высокая чувствительность к стресс-сценариям",
                description=f"В сценарии '{worst_scenario.id}' потери могут составить {abs(worst_scenario.pnl_pct):.1f}%.",
                action="Проработать план действий при реализации стресс-сценария, рассмотреть хеджирование.",
            )
        )

    # Проверка нарушений ковенант
    scenarios_with_breaches = [s for s in stress_scenarios if s.covenant_breaches]
    if scenarios_with_breaches:
        recommendations.append(
            CfoRecommendation(
                priority="high",
                category="stress_resilience",
                title="Риск нарушения ковенант при стрессе",
                description=f"В {len(scenarios_with_breaches)} стресс-сценарии(ях) возможно нарушение ковенант.",
                action="Подготовить план по поддержанию ковенант в кризисных условиях.",
            )
        )

    return recommendations


def build_executive_summary(
    liquidity_profile: LiquidityProfile,
    concentration_profile: CfoConcentrationProfile,
    stress_scenarios: list[CfoStressScenarioResult],
    recommendations: list[CfoRecommendation],
) -> CfoExecutiveSummary:
    """
    Сформировать executive summary для CFO.
    """
    # Определение общего статуса ликвидности
    status: Literal["healthy", "adequate", "warning", "critical"] = "healthy"

    high_priority_count = sum(1 for r in recommendations if r.priority == "high")
    worst_pnl = min((s.pnl_pct for s in stress_scenarios), default=0)
    has_covenant_breaches = any(s.covenant_breaches for s in stress_scenarios)

    if high_priority_count >= 3 or worst_pnl < -20 or has_covenant_breaches:
        status = "critical"
    elif high_priority_count >= 2 or worst_pnl < -15:
        status = "warning"
    elif high_priority_count >= 1 or worst_pnl < -10:
        status = "adequate"

    # Ключевые риски
    key_risks: list[str] = []

    if liquidity_profile.quick_ratio_pct and liquidity_profile.quick_ratio_pct < 20:
        key_risks.append("Низкий уровень высоколиквидных активов")

    if concentration_profile.top1_weight_pct and concentration_profile.top1_weight_pct > 25:
        key_risks.append("Высокая концентрация в отдельных позициях")

    worst_scenario = min(stress_scenarios, key=lambda s: s.pnl_pct, default=None)
    if worst_scenario and worst_scenario.pnl_pct < -10:
        key_risks.append(f"Потенциальные потери до {abs(worst_scenario.pnl_pct):.0f}% при стрессе")

    if has_covenant_breaches:
        key_risks.append("Риск нарушения ковенант при стресс-сценариях")

    if not key_risks:
        key_risks.append("Существенных рисков не выявлено")

    # Ключевые сильные стороны
    key_strengths: list[str] = []

    if liquidity_profile.quick_ratio_pct and liquidity_profile.quick_ratio_pct >= 30:
        key_strengths.append("Высокий уровень ликвидности")

    if concentration_profile.hhi and concentration_profile.hhi < 0.1:
        key_strengths.append("Хорошая диверсификация портфеля")

    if worst_pnl > -5:
        key_strengths.append("Устойчивость к стресс-сценариям")

    # Приоритетные действия
    action_items = [r.action for r in recommendations if r.priority == "high" and r.action]

    return CfoExecutiveSummary(
        overall_liquidity_status=status,
        key_risks=key_risks,
        key_strengths=key_strengths,
        action_items=action_items[:5],  # Топ-5 действий
    )


__all__ = [
    "LIQUIDITY_BUCKETS_ORDER",
    "build_liquidity_profile",
    "build_duration_profile",
    "build_currency_exposure",
    "build_concentration_profile",
    "build_cfo_stress_scenarios",
    "build_recommendations",
    "build_executive_summary",
]
