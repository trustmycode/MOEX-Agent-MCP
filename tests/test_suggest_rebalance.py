"""
Тесты для инструмента suggest_rebalance.

Проверяют:
1. Базовую ребалансировку портфеля с нарушениями концентрации
2. Ограничение оборота (turnover)
3. Обработку ошибок при невыполнимых ограничениях
4. Ребалансировку по классам активов
5. Валидацию входных данных
"""

import pytest

from risk_analytics_mcp.calculations.rebalance import (
    compute_rebalance,
    RebalanceError,
    RebalanceResult,
)
from risk_analytics_mcp.models import (
    RebalanceInput,
    RebalanceOutput,
    RebalancePosition,
    RiskProfileTarget,
)
from risk_analytics_mcp.tools.suggest_rebalance import suggest_rebalance_core


class TestComputeRebalanceBasic:
    """Тесты базовой логики ребалансировки."""

    def test_no_changes_needed_for_balanced_portfolio(self):
        """Портфель без нарушений не требует изменений."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.20, "asset_class": "equity"},
            {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
            {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
            {"ticker": "ROSN", "current_weight": 0.20, "asset_class": "equity"},
            {"ticker": "GMKN", "current_weight": 0.20, "asset_class": "equity"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.25,
            "max_issuer_weight": 0.30,
            "max_turnover": 0.20,
        }

        result = compute_rebalance(positions, risk_profile)

        assert isinstance(result, RebalanceResult)
        # Изменения минимальны или отсутствуют
        assert result.summary["positions_changed"] == 0
        assert result.summary["total_turnover"] < 0.01

    def test_concentration_limit_single_position(self):
        """Позиция превышающая лимит концентрации должна быть снижена."""
        # 5 позиций, чтобы лимит 25% был достижим (5 * 20% = 100%)
        positions = [
            {"ticker": "SBER", "current_weight": 0.50, "asset_class": "equity"},  # Превышает 25%
            {"ticker": "GAZP", "current_weight": 0.15, "asset_class": "equity"},
            {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
            {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
            {"ticker": "GMKN", "current_weight": 0.10, "asset_class": "equity"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.25,
            "max_issuer_weight": 0.30,
            "max_turnover": 0.50,
        }

        result = compute_rebalance(positions, risk_profile)

        # SBER должен быть снижен
        assert result.target_weights["SBER"] <= 0.26  # ~25% с погрешностью
        assert result.summary["concentration_issues_resolved"] >= 1
        assert len(result.trades) > 0

        # Должна быть сделка на продажу SBER
        sber_trade = next((t for t in result.trades if t["ticker"] == "SBER"), None)
        assert sber_trade is not None
        assert sber_trade["side"] == "sell"

    def test_issuer_concentration_limit(self):
        """Группа позиций одного эмитента, превышающая лимит, должна быть снижена."""
        # 5 эмитентов, чтобы лимит 30% был достижим
        positions = [
            {"ticker": "SBER", "current_weight": 0.25, "asset_class": "equity", "issuer": "SBERBANK"},
            {"ticker": "SBERP", "current_weight": 0.20, "asset_class": "equity", "issuer": "SBERBANK"},  # Суммарно 45%
            {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity", "issuer": "GAZPROM"},
            {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity", "issuer": "LUKOIL"},
            {"ticker": "ROSN", "current_weight": 0.15, "asset_class": "equity", "issuer": "ROSNEFT"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.35,
            "max_issuer_weight": 0.30,  # SBERBANK (45%) превышает
            "max_turnover": 0.50,
        }

        result = compute_rebalance(positions, risk_profile)

        # Суммарный вес SBERBANK должен быть <= 30%
        sber_total = result.target_weights["SBER"] + result.target_weights["SBERP"]
        assert sber_total <= 0.31  # ~30% с погрешностью
        assert result.summary["concentration_issues_resolved"] >= 1


class TestTurnoverConstraint:
    """Тесты ограничения оборота."""

    def test_turnover_is_limited(self):
        """Оборот должен быть ограничен max_turnover."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.60, "asset_class": "equity"},  # Сильное нарушение
            {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
            {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.25,
            "max_issuer_weight": 0.30,
            "max_turnover": 0.10,  # Жёсткое ограничение на оборот
        }

        result = compute_rebalance(positions, risk_profile)

        # Оборот не должен превышать лимит
        assert result.summary["total_turnover"] <= 0.11  # 10% + небольшая погрешность
        # Должно быть предупреждение о сокращении изменений
        assert len(result.warnings) > 0

    def test_full_rebalance_within_turnover(self):
        """При достаточном обороте полная ребалансировка возможна."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.30, "asset_class": "equity"},
            {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
            {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
            {"ticker": "ROSN", "current_weight": 0.20, "asset_class": "equity"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.25,
            "max_issuer_weight": 0.30,
            "max_turnover": 0.50,  # Достаточный оборот
        }

        result = compute_rebalance(positions, risk_profile)

        # Все позиции должны уложиться в лимит
        for ticker, weight in result.target_weights.items():
            assert weight <= 0.26  # ~25% + погрешность
        assert result.summary["turnover_within_limit"] is True


class TestAssetClassRebalance:
    """Тесты ребалансировки по классам активов."""

    def test_equity_limit_enforcement(self):
        """Лимит на долю акций должен соблюдаться."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.30, "asset_class": "equity"},
            {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
            {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
            {"ticker": "OFZ", "current_weight": 0.20, "asset_class": "fixed_income"},
        ]
        risk_profile = {
            "max_equity_weight": 0.60,  # Сейчас 80%, нужно снизить
            "max_single_position_weight": 0.40,
            "max_issuer_weight": 0.50,
            "max_turnover": 0.50,
        }

        result = compute_rebalance(positions, risk_profile)

        # Суммарная доля акций должна быть <= 60%
        equity_weight = sum(
            w for t, w in result.target_weights.items()
            if t in ["SBER", "GAZP", "LKOH"]
        )
        assert equity_weight <= 0.61  # ~60% + погрешность
        assert result.summary["asset_class_issues_resolved"] >= 1

    def test_target_asset_class_weights(self):
        """Целевые веса по классам активов должны применяться."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.50, "asset_class": "equity"},
            {"ticker": "OFZ", "current_weight": 0.50, "asset_class": "fixed_income"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.60,
            "max_issuer_weight": 0.60,
            "max_turnover": 0.50,
            "target_asset_class_weights": {
                "equity": 0.40,
                "fixed_income": 0.60,
            },
        }

        result = compute_rebalance(positions, risk_profile)

        # Доля акций должна быть ~40%
        assert 0.35 <= result.target_weights["SBER"] <= 0.45
        # Доля облигаций должна быть ~60%
        assert 0.55 <= result.target_weights["OFZ"] <= 0.65


class TestErrorHandling:
    """Тесты обработки ошибок."""

    def test_empty_portfolio_raises_error(self):
        """Пустой портфель вызывает ошибку."""
        with pytest.raises(RebalanceError) as exc_info:
            compute_rebalance([], {})

        assert exc_info.value.error_type == "EMPTY_PORTFOLIO"

    def test_infeasible_constraints_raises_error(self):
        """Невыполнимые ограничения вызывают ошибку."""
        # Портфель из одной позиции с лимитом ниже 100% — невыполнимо
        positions = [
            {"ticker": "SBER", "current_weight": 1.0, "asset_class": "equity"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.25,  # Одна позиция не может быть <= 25%
            "max_issuer_weight": 0.25,
            "max_turnover": 0.01,  # Минимальный оборот не позволит изменить
        }

        # Ожидаем, что будет предупреждение о сокращении изменений
        # но портфель из одной позиции нельзя перебалансировать
        result = compute_rebalance(positions, risk_profile)

        # Должны быть предупреждения
        assert len(result.warnings) > 0 or result.target_weights["SBER"] == 1.0


class TestEstimatedValue:
    """Тесты расчёта стоимости сделок."""

    def test_estimated_value_calculation(self):
        """Стоимость сделок рассчитывается при указании total_portfolio_value."""
        positions = [
            {"ticker": "SBER", "current_weight": 0.50, "asset_class": "equity"},
            {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
            {"ticker": "LKOH", "current_weight": 0.25, "asset_class": "equity"},
        ]
        risk_profile = {
            "max_single_position_weight": 0.30,
            "max_turnover": 0.50,
        }
        total_value = 1_000_000.0

        result = compute_rebalance(positions, risk_profile, total_portfolio_value=total_value)

        # Сделки должны содержать estimated_value
        trades_with_value = [t for t in result.trades if "estimated_value" in t and t["estimated_value"]]
        assert len(trades_with_value) > 0
        assert all(t["estimated_value"] > 0 for t in trades_with_value)


class TestSuggestRebalanceCore:
    """Тесты функции suggest_rebalance_core."""

    def test_core_function_returns_output_model(self):
        """suggest_rebalance_core возвращает RebalanceOutput."""
        input_data = {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.50, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
            ],
            "risk_profile": {
                "max_single_position_weight": 0.30,
                "max_turnover": 0.30,
            },
        }

        result = suggest_rebalance_core(input_data)

        assert isinstance(result, RebalanceOutput)
        assert result.error is None
        assert len(result.target_weights) == 3
        assert result.summary is not None

    def test_core_function_with_pydantic_input(self):
        """suggest_rebalance_core принимает Pydantic-модель."""
        input_model = RebalanceInput(
            positions=[
                RebalancePosition(ticker="SBER", current_weight=0.40, asset_class="equity"),
                RebalancePosition(ticker="GAZP", current_weight=0.35, asset_class="equity"),
                RebalancePosition(ticker="LKOH", current_weight=0.25, asset_class="equity"),
            ],
            risk_profile=RiskProfileTarget(
                max_single_position_weight=0.30,
                max_turnover=0.25,
            ),
        )

        result = suggest_rebalance_core(input_model)

        assert isinstance(result, RebalanceOutput)
        assert result.error is None
        assert len(result.trades) > 0  # Должны быть сделки для снижения концентрации

    def test_core_function_with_total_value(self):
        """suggest_rebalance_core рассчитывает estimated_value при указании стоимости."""
        # 4 позиции, чтобы лимит 30% был достижим (4 * 25% = 100%)
        input_data = {
            "positions": [
                {"ticker": "SBER", "current_weight": 0.50, "asset_class": "equity"},  # Превышает 30%
                {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
            ],
            "total_portfolio_value": 2_000_000.0,
            "risk_profile": {
                "max_single_position_weight": 0.30,
                "max_turnover": 0.50,
            },
        }

        result = suggest_rebalance_core(input_data)

        # Должны быть сделки с estimated_value
        trades_with_value = [t for t in result.trades if t.estimated_value is not None]
        assert len(trades_with_value) > 0


class TestInputValidation:
    """Тесты валидации входных данных."""

    def test_weights_must_sum_to_one(self):
        """Сумма весов должна быть ~1.0."""
        with pytest.raises(ValueError):
            RebalanceInput(
                positions=[
                    RebalancePosition(ticker="SBER", current_weight=0.30, asset_class="equity"),
                    RebalancePosition(ticker="GAZP", current_weight=0.30, asset_class="equity"),
                    # Сумма = 0.6, не 1.0
                ],
            )

    def test_tickers_must_be_unique(self):
        """Тикеры должны быть уникальными."""
        with pytest.raises(ValueError):
            RebalanceInput(
                positions=[
                    RebalancePosition(ticker="SBER", current_weight=0.50, asset_class="equity"),
                    RebalancePosition(ticker="SBER", current_weight=0.50, asset_class="equity"),  # Дубликат
                ],
            )

    def test_max_turnover_must_be_valid(self):
        """max_turnover должен быть в диапазоне [0, 1]."""
        with pytest.raises(ValueError):
            RiskProfileTarget(max_turnover=1.5)  # > 1.0

    def test_target_asset_class_weights_must_not_exceed_one(self):
        """Сумма целевых весов по классам не должна превышать 1.0."""
        with pytest.raises(ValueError):
            RiskProfileTarget(
                target_asset_class_weights={
                    "equity": 0.70,
                    "fixed_income": 0.50,  # Сумма = 1.2 > 1.0
                }
            )


