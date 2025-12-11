"""
Вспомогательные расчёты для сравнительного отчёта по эмитенту и пирам.
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional

from ..models import IssuerFundamentals, IssuerPeersComparePeer, MetricRank, PeersFlag

METRIC_PREFERENCES: Mapping[str, bool] = {
    "pe_ratio": False,  # ниже — лучше
    "ev_to_ebitda": False,
    "debt_to_ebitda": False,
    "roe_pct": True,  # выше — лучше
    "dividend_yield_pct": True,
}


def _is_finite(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value)


def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    if not math.isfinite(numerator) or not math.isfinite(denominator):
        return None
    return numerator / denominator


def _compute_market_cap(fundamentals: IssuerFundamentals) -> Optional[float]:
    if fundamentals.market_cap is not None:
        return fundamentals.market_cap
    if fundamentals.price is None or fundamentals.shares_outstanding is None:
        return None
    return fundamentals.price * float(fundamentals.shares_outstanding)


def build_peer_metrics(fundamentals: IssuerFundamentals, *, sector_hint: Optional[str] = None) -> IssuerPeersComparePeer:
    """
    Построить агрегированные метрики по эмитенту из IssuerFundamentals.
    """
    market_cap = _compute_market_cap(fundamentals)
    enterprise_value = fundamentals.enterprise_value
    if enterprise_value is None and market_cap is not None and fundamentals.net_debt is not None:
        enterprise_value = market_cap + fundamentals.net_debt

    pe_ratio = fundamentals.pe_ratio
    if pe_ratio is None and fundamentals.net_income is not None and fundamentals.shares_outstanding not in (None, 0):
        eps = _safe_div(fundamentals.net_income, fundamentals.shares_outstanding)
        if eps not in (None, 0):
            pe_ratio = _safe_div(fundamentals.price, eps)

    ev_to_ebitda = fundamentals.ev_to_ebitda
    if ev_to_ebitda is None and enterprise_value is not None:
        ev_to_ebitda = _safe_div(enterprise_value, fundamentals.ebitda)

    debt_to_ebitda = fundamentals.debt_to_ebitda
    if debt_to_ebitda is None and fundamentals.net_debt is not None:
        debt_to_ebitda = _safe_div(fundamentals.net_debt, fundamentals.ebitda)

    roe_pct = None
    if fundamentals.net_income is not None and fundamentals.total_equity not in (None, 0):
        roe_pct = _safe_div(fundamentals.net_income, fundamentals.total_equity)
        if roe_pct is not None:
            roe_pct *= 100.0

    sector = sector_hint or fundamentals.sector

    return IssuerPeersComparePeer(
        ticker=fundamentals.ticker,
        isin=fundamentals.isin,
        issuer_name=fundamentals.issuer_name,
        sector=sector,
        as_of=fundamentals.as_of,
        price=fundamentals.price,
        shares_outstanding=fundamentals.shares_outstanding,
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        net_debt=fundamentals.net_debt,
        ebitda=fundamentals.ebitda,
        net_income=fundamentals.net_income,
        pe_ratio=pe_ratio,
        ev_to_ebitda=ev_to_ebitda,
        debt_to_ebitda=debt_to_ebitda,
        roe_pct=roe_pct,
        dividend_yield_pct=fundamentals.dividend_yield_pct,
    )


def compute_metric_ranks(
    base_peer: IssuerPeersComparePeer,
    peers: Iterable[IssuerPeersComparePeer],
) -> list[MetricRank]:
    """
    Рассчитать ранжирование базового эмитента по ключевым метрикам среди пиров.
    """
    ranking: list[MetricRank] = []
    peers_list = list(peers)
    for metric, higher_is_better in METRIC_PREFERENCES.items():
        series = [
            getattr(p, metric) for p in [base_peer, *peers_list] if _is_finite(getattr(p, metric, None))
        ]
        base_value = getattr(base_peer, metric, None)
        rank_value = None
        percentile = None
        total = len(series)
        if _is_finite(base_value) and series:
            count_lower = sum(1 for v in series if v < base_value)
            count_greater = sum(1 for v in series if v > base_value)
            count_equal = total - count_lower - count_greater
            percentile = (count_lower + 0.5 * count_equal) / total if total else None
            rank_value = count_greater + 1 if higher_is_better else count_lower + 1

        ranking.append(
            MetricRank(
                metric=metric,
                value=base_value,
                rank=rank_value,
                total=total,
                percentile=percentile,
            )
        )
    return ranking


def derive_flags(base_peer: IssuerPeersComparePeer, ranking: Iterable[MetricRank]) -> list[PeersFlag]:
    """
    Сформировать простые эвристические флаги на основе ранжирования и метрик.
    """
    flags: list[PeersFlag] = []
    rank_map = {r.metric: r for r in ranking}

    def add_flag(code: str, severity: str, message: str, metric: Optional[str] = None) -> None:
        flags.append(PeersFlag(code=code, severity=severity, message=message, metric=metric))

    pe_rank = rank_map.get("pe_ratio")
    ev_rank = rank_map.get("ev_to_ebitda")
    dy_rank = rank_map.get("dividend_yield_pct")
    roe_rank = rank_map.get("roe_pct")

    if pe_rank and pe_rank.percentile is not None:
        if pe_rank.percentile >= 0.75:
            add_flag("OVERVALUED", "medium", "P/E выше 75% пиров", "pe_ratio")
        elif pe_rank.percentile <= 0.25:
            add_flag("UNDERVALUED", "low", "P/E в нижнем квартиле среди пиров", "pe_ratio")

    if ev_rank and ev_rank.percentile is not None and ev_rank.percentile <= 0.25:
        add_flag("CHEAP_EV_EBITDA", "low", "EV/EBITDA в нижнем квартиле", "ev_to_ebitda")

    if dy_rank and dy_rank.percentile is not None and dy_rank.percentile >= 0.75:
        add_flag("ATTRACTIVE_DIVIDEND", "medium", "Дивидендная доходность в верхнем квартиле", "dividend_yield_pct")

    if roe_rank and roe_rank.percentile is not None and roe_rank.percentile <= 0.25:
        add_flag("LOW_ROE", "medium", "ROE в нижнем квартиле среди пиров", "roe_pct")

    if base_peer.debt_to_ebitda is not None:
        if base_peer.debt_to_ebitda > 3:
            add_flag("HIGH_LEVERAGE", "high", "NetDebt/EBITDA выше 3x", "debt_to_ebitda")
        elif base_peer.debt_to_ebitda < 1:
            add_flag("LOW_LEVERAGE", "low", "NetDebt/EBITDA ниже 1x", "debt_to_ebitda")

    return flags


def has_meaningful_metrics(peer: IssuerPeersComparePeer) -> bool:
    """
    Проверить, есть ли у эмитента хоть какие-то ключевые метрики.
    """
    return any(
        _is_finite(value)
        for value in [
            peer.pe_ratio,
            peer.ev_to_ebitda,
            peer.debt_to_ebitda,
            peer.roe_pct,
            peer.dividend_yield_pct,
            peer.price,
            peer.market_cap,
        ]
    )


__all__ = [
    "build_peer_metrics",
    "compute_metric_ranks",
    "derive_flags",
    "has_meaningful_metrics",
    "METRIC_PREFERENCES",
]
