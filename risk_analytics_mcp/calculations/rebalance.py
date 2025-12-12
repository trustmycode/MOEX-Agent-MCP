"""
Логика эвристической ребалансировки портфеля.

Модуль реализует детерминированную ребалансировку с учётом ограничений:
- таргет-аллокация по классам активов,
- лимиты концентрации по позициям и эмитентам,
- ограничение на максимальный оборот (turnover).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PositionData:
    """Внутреннее представление позиции для расчётов."""

    ticker: str
    current_weight: float
    target_weight: float
    asset_class: str
    issuer: Optional[str] = None
    locked: bool = False  # Нельзя изменять (исчерпан turnover или другие причины)


@dataclass
class RebalanceResult:
    """Результат расчёта ребалансировки."""

    target_weights: dict[str, float]
    trades: list[dict]
    summary: dict
    warnings: list[str] = field(default_factory=list)


class RebalanceError(Exception):
    """Ошибка при невозможности выполнить ребалансировку."""

    def __init__(self, error_type: str, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.details = details or {}


def _group_by_asset_class(positions: list[PositionData]) -> dict[str, list[PositionData]]:
    """Группировка позиций по классам активов."""
    groups: dict[str, list[PositionData]] = {}
    for pos in positions:
        groups.setdefault(pos.asset_class, []).append(pos)
    return groups


def _group_by_issuer(positions: list[PositionData]) -> dict[str, list[PositionData]]:
    """Группировка позиций по эмитентам."""
    groups: dict[str, list[PositionData]] = {}
    for pos in positions:
        issuer = pos.issuer or pos.ticker
        groups.setdefault(issuer, []).append(pos)
    return groups


def _calc_asset_class_weights(positions: list[PositionData]) -> dict[str, float]:
    """Рассчитать веса по классам активов."""
    weights: dict[str, float] = {}
    for pos in positions:
        weights[pos.asset_class] = weights.get(pos.asset_class, 0.0) + pos.target_weight
    return weights


def _calc_issuer_weights(positions: list[PositionData]) -> dict[str, float]:
    """Рассчитать веса по эмитентам."""
    weights: dict[str, float] = {}
    for pos in positions:
        issuer = pos.issuer or pos.ticker
        weights[issuer] = weights.get(issuer, 0.0) + pos.target_weight
    return weights


def _normalize_weights(positions: list[PositionData]) -> None:
    """Нормализовать веса чтобы сумма была 1.0."""
    total = sum(p.target_weight for p in positions)
    if total <= 0:
        return
    for pos in positions:
        pos.target_weight = pos.target_weight / total


def _redistribute_excess(
    positions: list[PositionData],
    positions_to_reduce: list[str],
    excess: float,
    *,
    min_weight: float = 0.0,
) -> float:
    """
    Распределить избыток веса от позиций с нарушениями на остальные.

    Возвращает оставшийся нераспределённый избыток.
    """
    if excess <= 0:
        return 0.0

    reducible = [p for p in positions if p.ticker in positions_to_reduce and not p.locked]
    if not reducible:
        return excess

    # Сначала равномерно снижаем
    reduction_per_pos = excess / len(reducible)
    remaining_excess = 0.0

    for pos in reducible:
        available_reduction = max(0, pos.target_weight - min_weight)
        actual_reduction = min(reduction_per_pos, available_reduction)
        pos.target_weight -= actual_reduction
        remaining_excess += reduction_per_pos - actual_reduction

    return remaining_excess


def _apply_concentration_limits(
    positions: list[PositionData],
    max_single_position_weight: float,
    max_issuer_weight: float,
    max_iterations: int = 10,
) -> tuple[int, list[str]]:
    """
    Применить лимиты концентрации по позициям и эмитентам.

    Использует итеративный подход: снижает нарушающие позиции до лимита,
    распределяет избыток на позиции с запасом, повторяет до сходимости.

    Возвращает количество исправленных нарушений и предупреждения.
    """
    warnings: list[str] = []
    issues_resolved = 0

    for iteration in range(max_iterations):
        changes_made = False

        # Шаг 1: Лимит на одну позицию
        for pos in positions:
            if pos.target_weight > max_single_position_weight + 0.001:
                excess = pos.target_weight - max_single_position_weight
                pos.target_weight = max_single_position_weight
                issues_resolved += 1
                changes_made = True

                # Распределяем избыток на позиции, которые не превысят лимит
                other_positions = [
                    p for p in positions
                    if p.ticker != pos.ticker
                    and not p.locked
                    and p.target_weight < max_single_position_weight - 0.001
                ]
                if other_positions:
                    # Распределяем равномерно с учётом запаса
                    remaining_excess = excess
                    for other in other_positions:
                        headroom = max_single_position_weight - other.target_weight - 0.001
                        if headroom > 0:
                            add = min(remaining_excess / len(other_positions), headroom)
                            other.target_weight += add
                            remaining_excess -= add
                    # Если остался избыток, добавляем пропорционально всем (даже с превышением)
                    if remaining_excess > 0.001:
                        total_other = sum(p.target_weight for p in other_positions)
                        if total_other > 0:
                            for other in other_positions:
                                other.target_weight += remaining_excess * (other.target_weight / total_other)

        # Шаг 2: Лимит на эмитента
        issuer_weights = _calc_issuer_weights(positions)
        for issuer, total_weight in issuer_weights.items():
            if total_weight > max_issuer_weight + 0.001:
                excess = total_weight - max_issuer_weight
                issuer_positions = [p for p in positions if (p.issuer or p.ticker) == issuer]

                if issuer_positions:
                    scale = max_issuer_weight / total_weight
                    for pos in issuer_positions:
                        pos.target_weight = pos.target_weight * scale

                    issues_resolved += 1
                    changes_made = True

                    # Распределяем избыток на других эмитентов
                    other_positions = [
                        p for p in positions
                        if (p.issuer or p.ticker) != issuer and not p.locked
                    ]
                    if other_positions:
                        total_other = sum(p.target_weight for p in other_positions)
                        if total_other > 0:
                            for other in other_positions:
                                other.target_weight += excess * (other.target_weight / total_other)

        # Нормализуем после каждой итерации
        _normalize_weights(positions)

        if not changes_made:
            break

    return issues_resolved, warnings


def _apply_asset_class_limits(
    positions: list[PositionData],
    max_equity_weight: float,
    max_fixed_income_weight: float,
    max_fx_weight: float,
    target_asset_class_weights: dict[str, float],
) -> tuple[int, list[str]]:
    """
    Применить ограничения по классам активов.

    Возвращает количество исправленных нарушений и предупреждения.
    """
    warnings: list[str] = []
    issues_resolved = 0

    limits = {
        "equity": max_equity_weight,
        "fixed_income": max_fixed_income_weight,
        "fx": max_fx_weight,
    }

    current_class_weights = _calc_asset_class_weights(positions)

    # Проверяем превышения лимитов
    for asset_class, limit in limits.items():
        current = current_class_weights.get(asset_class, 0.0)
        if current > limit:
            excess = current - limit
            class_positions = [p for p in positions if p.asset_class == asset_class and not p.locked]

            if class_positions:
                # Пропорционально снижаем веса
                scale = limit / current if current > 0 else 0
                for pos in class_positions:
                    pos.target_weight = pos.target_weight * scale

                issues_resolved += 1

                # Распределяем избыток на другие классы
                other_positions = [p for p in positions if p.asset_class != asset_class and not p.locked]
                if other_positions:
                    total_other = sum(p.target_weight for p in other_positions)
                    if total_other > 0:
                        for other in other_positions:
                            other.target_weight += excess * (other.target_weight / total_other)

    # Применяем целевые веса по классам активов (если заданы)
    if target_asset_class_weights:
        for asset_class, target in target_asset_class_weights.items():
            current = current_class_weights.get(asset_class, 0.0)
            if abs(current - target) > 0.01:  # Порог 1%
                class_positions = [p for p in positions if p.asset_class == asset_class and not p.locked]
                if class_positions and current > 0:
                    scale = target / current
                    for pos in class_positions:
                        pos.target_weight = pos.target_weight * scale
                    issues_resolved += 1

    _normalize_weights(positions)

    return issues_resolved, warnings


def _apply_turnover_constraint(
    positions: list[PositionData],
    max_turnover: float,
) -> tuple[bool, list[str]]:
    """
    Проверить и при необходимости ограничить оборот.

    Оборот = сумма |delta| / 2, где delta = target - current.

    Возвращает (within_limit, warnings).
    """
    warnings: list[str] = []

    total_delta = sum(abs(p.target_weight - p.current_weight) for p in positions)
    turnover = total_delta / 2

    if turnover <= max_turnover:
        return True, warnings

    # Нужно сжать изменения
    if total_delta > 0:
        scale = (max_turnover * 2) / total_delta
        for pos in positions:
            delta = pos.target_weight - pos.current_weight
            pos.target_weight = pos.current_weight + delta * scale

    warnings.append(
        f"Оборот ({turnover:.1%}) превышает лимит ({max_turnover:.1%}), изменения сокращены."
    )

    _normalize_weights(positions)

    return False, warnings


def _build_trades(
    positions: list[PositionData],
    total_portfolio_value: Optional[float],
) -> list[dict]:
    """Построить список сделок на основе изменений весов."""
    trades = []

    for pos in positions:
        delta = pos.target_weight - pos.current_weight
        if abs(delta) < 0.001:  # Порог 0.1%
            continue

        side = "buy" if delta > 0 else "sell"

        trade = {
            "ticker": pos.ticker,
            "side": side,
            "weight_delta": round(delta, 6),
            "target_weight": round(pos.target_weight, 6),
            "reason": "rebalance",
        }

        if total_portfolio_value is not None:
            trade["estimated_value"] = round(abs(delta) * total_portfolio_value, 2)

        trades.append(trade)

    return trades


def _build_summary(
    positions: list[PositionData],
    max_turnover: float,
    concentration_issues: int,
    asset_class_issues: int,
    warnings: list[str],
) -> dict:
    """Построить сводку результата ребалансировки."""
    total_delta = sum(abs(p.target_weight - p.current_weight) for p in positions)
    turnover = total_delta / 2
    positions_changed = sum(1 for p in positions if abs(p.target_weight - p.current_weight) >= 0.001)

    return {
        "total_turnover": round(turnover, 6),
        "turnover_within_limit": turnover <= max_turnover,
        "positions_changed": positions_changed,
        "concentration_issues_resolved": concentration_issues,
        "asset_class_issues_resolved": asset_class_issues,
        "warnings": warnings,
    }


def compute_rebalance(
    positions: list[dict],
    risk_profile: dict,
    total_portfolio_value: Optional[float] = None,
) -> RebalanceResult:
    """
    Вычислить предложение по ребалансировке портфеля.

    Args:
        positions: Список позиций с текущими весами и метаданными.
        risk_profile: Целевой профиль риска и ограничения.
        total_portfolio_value: Общая стоимость портфеля (для расчёта сделок в рублях).

    Returns:
        RebalanceResult с целевыми весами, сделками и сводкой.

    Raises:
        RebalanceError: При невозможности выполнить ребалансировку.
    """
    if not positions:
        raise RebalanceError(
            error_type="EMPTY_PORTFOLIO",
            message="Портфель не содержит позиций для ребалансировки.",
        )

    # Парсинг профиля риска
    max_equity = risk_profile.get("max_equity_weight", 1.0)
    max_fi = risk_profile.get("max_fixed_income_weight", 1.0)
    max_fx = risk_profile.get("max_fx_weight", 1.0)
    max_single = risk_profile.get("max_single_position_weight", 0.25)
    max_issuer = risk_profile.get("max_issuer_weight", 0.30)
    max_turnover = risk_profile.get("max_turnover", 0.50)
    target_ac_weights = risk_profile.get("target_asset_class_weights", {})

    # Создание внутреннего представления
    pos_data = [
        PositionData(
            ticker=p["ticker"],
            current_weight=p["current_weight"],
            target_weight=p["current_weight"],  # Начинаем с текущих весов
            asset_class=p.get("asset_class", "equity"),
            issuer=p.get("issuer"),
        )
        for p in positions
    ]

    all_warnings: list[str] = []

    # Шаг 1: Применение лимитов по классам активов
    ac_issues, ac_warnings = _apply_asset_class_limits(
        pos_data, max_equity, max_fi, max_fx, target_ac_weights
    )
    all_warnings.extend(ac_warnings)

    # Шаг 2: Применение лимитов концентрации
    conc_issues, conc_warnings = _apply_concentration_limits(pos_data, max_single, max_issuer)
    all_warnings.extend(conc_warnings)

    # Шаг 3: Ограничение оборота
    within_limit, turnover_warnings = _apply_turnover_constraint(pos_data, max_turnover)
    all_warnings.extend(turnover_warnings)

    # Финальная проверка: есть ли нерешённые проблемы?
    # Ребалансировка — это best-effort процесс, а не гарантия полного устранения нарушений.
    # Мы предупреждаем о нарушениях, но не бросаем ошибку, если улучшения были сделаны.
    final_issuer_weights = _calc_issuer_weights(pos_data)

    # Проверяем нарушения после всех корректировок
    remaining_issues = []
    for pos in pos_data:
        if pos.target_weight > max_single + 0.01:
            remaining_issues.append(f"Позиция {pos.ticker} ({pos.target_weight:.1%}) превышает лимит ({max_single:.1%})")
    for issuer, weight in final_issuer_weights.items():
        if weight > max_issuer + 0.01:
            remaining_issues.append(f"Эмитент {issuer} ({weight:.1%}) превышает лимит ({max_issuer:.1%})")

    # Добавляем предупреждения о нарушениях (но не бросаем ошибку)
    # Ошибка только если портфель невозможно улучшить вообще (например, 1 позиция с лимитом <100%)
    if remaining_issues:
        # Проверяем, улучшилась ли ситуация по сравнению с исходной
        original_max_weight = max(p.current_weight for p in pos_data)
        final_max_weight = max(p.target_weight for p in pos_data)

        if final_max_weight >= original_max_weight and conc_issues == 0 and ac_issues == 0:
            # Никакого улучшения не было и не может быть — это ошибка
            # Но только если портфель из одной позиции или структурно невыполним
            if len(pos_data) == 1:
                raise RebalanceError(
                    error_type="CONSTRAINTS_INFEASIBLE",
                    message="Невозможно достичь целевого профиля: портфель из одной позиции не может быть ребалансирован.",
                    details={"unresolved_issues": remaining_issues},
                )

        # В остальных случаях — просто предупреждаем
        for issue in remaining_issues:
            all_warnings.append(f"Не полностью устранено: {issue}")

    # Построение результата
    target_weights = {p.ticker: round(p.target_weight, 6) for p in pos_data}
    trades = _build_trades(pos_data, total_portfolio_value)
    summary = _build_summary(pos_data, max_turnover, conc_issues, ac_issues, all_warnings)

    return RebalanceResult(
        target_weights=target_weights,
        trades=trades,
        summary=summary,
        warnings=all_warnings,
    )


__all__ = [
    "compute_rebalance",
    "RebalanceError",
    "RebalanceResult",
]


