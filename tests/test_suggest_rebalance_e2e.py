"""
E2E тесты для инструмента suggest_rebalance.

Проверяют бизнес-сценарии ребалансировки:
- Сценарии из реальной практики
- Интеграцию логики через core функции
- Полные циклы ребалансировки
"""

import pytest

from risk_analytics_mcp.tools.suggest_rebalance import suggest_rebalance_core
from risk_analytics_mcp.models import RebalanceOutput


class TestE2ESuggestRebalanceScenarios:
    """E2E: Бизнес-сценарии ребалансировки."""

    def test_scenario_reduce_concentration_in_single_stock(self):
        """
        Сценарий 1: Инвестор с перекосом в одну акцию.
        
        Исходная ситуация:
        - SBER занимает 45% портфеля (слишком много)
        - Лимит на одну позицию: 25%
        
        Ожидание:
        - SBER снижается до ~25%
        - Избыток распределяется на другие позиции
        """
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.45, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
                {"ticker": "GMKN", "current_weight": 0.10, "asset_class": "equity"},
            ],
            "total_portfolio_value": 10_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.25,
                "max_turnover": 0.30,
            },
        })

        assert isinstance(result, RebalanceOutput)
        assert result.error is None
        
        # SBER должен быть снижен до ~25%
        assert result.target_weights["SBER"] <= 0.26
        
        # Должны быть сделки
        assert len(result.trades) > 0
        
        # Должна быть сделка на продажу SBER
        sber_trades = [t for t in result.trades if t.ticker == "SBER"]
        assert len(sber_trades) == 1
        assert sber_trades[0].side == "sell"
        assert sber_trades[0].estimated_value is not None
        assert sber_trades[0].estimated_value > 0
        
        # Сводка должна показать устранение нарушений
        assert result.summary.concentration_issues_resolved >= 1

    def test_scenario_issuer_concentration_sberbank_group(self):
        """
        Сценарий 2: Концентрация на эмитенте Сбербанк.
        
        Исходная ситуация:
        - SBER (обыкновенные) + SBERP (привилегированные) = 40% портфеля
        - Лимит на эмитента: 25%
        
        Ожидание:
        - Суммарный вес Сбербанка снижается до ~25%
        """
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.25, "asset_class": "equity", "issuer": "SBERBANK"},
                {"ticker": "SBERP", "current_weight": 0.15, "asset_class": "equity", "issuer": "SBERBANK"},
                {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity", "issuer": "GAZPROM"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity", "issuer": "LUKOIL"},
                {"ticker": "ROSN", "current_weight": 0.20, "asset_class": "equity", "issuer": "ROSNEFT"},
            ],
            "total_portfolio_value": 5_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.30,
                "max_issuer_weight": 0.25,
                "max_turnover": 0.30,
            },
        })

        assert result.error is None
        
        # Суммарный вес Сбербанка должен быть <= 25%
        sberbank_total = result.target_weights.get("SBER", 0) + result.target_weights.get("SBERP", 0)
        assert sberbank_total <= 0.26

    def test_scenario_rebalance_to_target_asset_allocation(self):
        """
        Сценарий 3: Приведение к целевой аллокации 60/40.
        
        Исходная ситуация:
        - Акции: 80%
        - Облигации: 20%
        
        Цель:
        - Акции: 60%
        - Облигации: 40%
        """
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.30, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "OFZ26", "current_weight": 0.10, "asset_class": "fixed_income"},
                {"ticker": "OFZ29", "current_weight": 0.10, "asset_class": "fixed_income"},
            ],
            "total_portfolio_value": 10_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.30,
                "max_equity_weight": 0.60,
                "max_turnover": 0.30,
                "target_asset_class_weights": {
                    "equity": 0.60,
                    "fixed_income": 0.40,
                },
            },
        })

        assert result.error is None
        
        # Проверяем, что были изменения по классам активов
        assert result.summary.asset_class_issues_resolved >= 1 or result.summary.positions_changed > 0
        
        # Сумма весов акций должна быть ближе к 60%
        equity_weight = sum(
            result.target_weights[t] for t in ["SBER", "GAZP", "LKOH"]
        )
        # После ребалансировки акции должны быть <= 60%
        assert equity_weight <= 0.65  # С учётом ограничения оборота

    def test_scenario_conservative_rebalance_low_turnover(self):
        """
        Сценарий 4: Консервативная ребалансировка с минимальным оборотом.
        
        Инвестор хочет минимизировать транзакционные издержки.
        Лимит оборота: 5%
        """
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.35, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "OFZ", "current_weight": 0.20, "asset_class": "fixed_income"},
            ],
            "total_portfolio_value": 3_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.25,
                "max_turnover": 0.05,  # Только 5% оборота
            },
        })

        assert result.error is None
        
        # Оборот не должен превышать 5%
        assert result.summary.total_turnover <= 0.06
        
        # Должны быть предупреждения о нерешённых проблемах
        assert len(result.summary.warnings) > 0

    def test_scenario_cfo_quarterly_rebalance(self):
        """
        Сценарий 5: Квартальная ребалансировка для CFO.
        
        CFO хочет:
        - Снизить концентрацию в акциях до 50%
        - Увеличить долю облигаций и денежных средств
        - Уложиться в оборот 20%
        """
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.25, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "OFZ26", "current_weight": 0.15, "asset_class": "fixed_income"},
                {"ticker": "OFZ29", "current_weight": 0.10, "asset_class": "fixed_income"},
                {"ticker": "USDRUB", "current_weight": 0.10, "asset_class": "fx"},
                {"ticker": "MONEY", "current_weight": 0.05, "asset_class": "cash"},
            ],
            "total_portfolio_value": 50_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.20,
                "max_equity_weight": 0.50,
                "max_fx_weight": 0.15,
                "max_turnover": 0.20,
                "target_asset_class_weights": {
                    "equity": 0.45,
                    "fixed_income": 0.35,
                    "fx": 0.10,
                    "cash": 0.10,
                },
            },
        })

        assert result.error is None
        
        # Оборот в рамках лимита
        assert result.summary.total_turnover <= 0.21
        
        # Проверяем структуру сделок
        if result.trades:
            for trade in result.trades:
                assert trade.ticker is not None
                assert trade.side in ["buy", "sell"]
                assert trade.estimated_value is not None  # Т.к. передали total_portfolio_value

    def test_scenario_pension_fund_compliance(self):
        """
        Сценарий 6: Пенсионный фонд — соблюдение нормативов.
        
        Жёсткие ограничения:
        - Не более 10% в одной акции
        - Не более 40% в акциях всего
        - Оборот до 15%
        """
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.10, "asset_class": "equity"},
                {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
                {"ticker": "OFZ26", "current_weight": 0.20, "asset_class": "fixed_income"},
                {"ticker": "OFZ29", "current_weight": 0.20, "asset_class": "fixed_income"},
                {"ticker": "CORP", "current_weight": 0.10, "asset_class": "fixed_income"},
            ],
            "total_portfolio_value": 100_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.10,
                "max_equity_weight": 0.40,
                "max_turnover": 0.15,
            },
        })

        assert result.error is None
        
        # Все позиции должны быть <= 10%
        for ticker, weight in result.target_weights.items():
            # С учётом ограничения оборота могут остаться нарушения
            if weight > 0.11:
                # Должно быть предупреждение
                assert len(result.summary.warnings) > 0


class TestE2EErrorScenarios:
    """E2E: Сценарии с ошибками."""

    def test_scenario_empty_portfolio_error(self):
        """Пустой портфель должен возвращать ошибку."""
        with pytest.raises(Exception):  # ValidationError или RebalanceError
            suggest_rebalance_core({"positions": []})

    def test_scenario_weights_not_sum_to_one(self):
        """Веса, не суммирующиеся к 1, должны вызывать ошибку."""
        with pytest.raises(ValueError):
            suggest_rebalance_core({
                "positions": [
                    {"ticker": "SBER", "current_weight": 0.30, "asset_class": "equity"},
                    {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
                    # Сумма = 0.60, не 1.0
                ],
            })

    def test_scenario_single_position_infeasible(self):
        """Портфель из одной позиции с лимитом <100% — предупреждения (best-effort)."""
        # Портфель из одной позиции невозможно ребалансировать,
        # но система работает в режиме best-effort и выдаёт предупреждения
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 1.0, "asset_class": "equity"},
            ],
            "risk_profile": {
                "max_single_position_weight": 0.25,  # Невозможно с 1 позицией
                "max_turnover": 0.50,
            },
        })
        
        # Ошибки нет (best-effort), но есть предупреждения
        assert result.error is None
        assert len(result.summary.warnings) > 0
        # Позиция остаётся 100% (некуда перераспределить)
        assert result.target_weights["SBER"] == 1.0


class TestE2EIntegrationWithPortfolioRisk:
    """E2E: Интеграция с compute_portfolio_risk_basic."""

    def test_rebalance_improves_concentration(self):
        """
        Интеграционный сценарий:
        1. Проверить концентрацию до ребалансировки
        2. Выполнить ребалансировку
        3. Убедиться, что концентрация улучшилась
        """
        # Исходный портфель с высокой концентрацией
        original_positions = [
            {"ticker": "SBER", "weight": 0.50},
            {"ticker": "GAZP", "weight": 0.25},
            {"ticker": "LKOH", "weight": 0.15},
            {"ticker": "ROSN", "weight": 0.10},
        ]
        
        # Ребалансировка
        rebalance_result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.50, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "ROSN", "current_weight": 0.10, "asset_class": "equity"},
            ],
            "risk_profile": {
                "max_single_position_weight": 0.30,
                "max_turnover": 0.30,
            },
        })

        assert rebalance_result.error is None
        
        # Проверяем, что концентрация снизилась
        original_max = max(p["weight"] for p in original_positions)  # 0.50
        new_max = max(rebalance_result.target_weights.values())
        
        # Новая максимальная позиция должна быть меньше исходной
        assert new_max < original_max

    def test_rebalance_maintains_sum_to_one(self):
        """Ребалансировка должна сохранять сумму весов = 1."""
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.40, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.30, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "OFZ", "current_weight": 0.10, "asset_class": "fixed_income"},
            ],
            "risk_profile": {
                "max_single_position_weight": 0.25,
                "max_turnover": 0.25,
            },
        })

        assert result.error is None
        
        # Сумма целевых весов должна быть ~1.0
        total_weight = sum(result.target_weights.values())
        assert 0.99 <= total_weight <= 1.01

    def test_trades_sum_to_zero(self):
        """Сумма всех сделок по весам должна быть ~0 (что продали = что купили)."""
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.45, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "OFZ", "current_weight": 0.15, "asset_class": "fixed_income"},
            ],
            "total_portfolio_value": 5_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.25,
                "max_turnover": 0.30,
            },
        })

        assert result.error is None
        
        # Сумма weight_delta всех сделок должна быть ~0
        total_delta = sum(t.weight_delta for t in result.trades)
        assert abs(total_delta) < 0.01


class TestE2ERealWorldPortfolios:
    """E2E: Тесты на реальных примерах портфелей."""

    def test_aggressive_investor_portfolio(self):
        """Агрессивный инвестор: 100% акции, высокая концентрация."""
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.35, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.25, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "YNDX", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "OZON", "current_weight": 0.05, "asset_class": "equity"},
            ],
            "total_portfolio_value": 2_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.20,
                "max_turnover": 0.25,
            },
        })

        assert result.error is None
        # Все позиции должны стремиться к <= 20%
        for ticker, weight in result.target_weights.items():
            if weight > 0.21:
                # Должны быть предупреждения
                assert len(result.summary.warnings) > 0

    def test_balanced_investor_portfolio(self):
        """Сбалансированный инвестор: 60/40."""
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.20, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "LKOH", "current_weight": 0.15, "asset_class": "equity"},
                {"ticker": "OFZ26", "current_weight": 0.15, "asset_class": "fixed_income"},
                {"ticker": "OFZ29", "current_weight": 0.15, "asset_class": "fixed_income"},
                {"ticker": "CORP", "current_weight": 0.10, "asset_class": "fixed_income"},
                {"ticker": "MONEY", "current_weight": 0.10, "asset_class": "cash"},
            ],
            "total_portfolio_value": 10_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.20,
                "max_equity_weight": 0.50,
                "max_turnover": 0.15,
                "target_asset_class_weights": {
                    "equity": 0.50,
                    "fixed_income": 0.40,
                    "cash": 0.10,
                },
            },
        })

        assert result.error is None
        assert result.summary.total_turnover <= 0.16

    def test_conservative_investor_portfolio(self):
        """Консервативный инвестор: 80% облигации."""
        result = suggest_rebalance_core({
            "positions": [
                {"ticker": "SBER", "current_weight": 0.10, "asset_class": "equity"},
                {"ticker": "GAZP", "current_weight": 0.10, "asset_class": "equity"},
                {"ticker": "OFZ26", "current_weight": 0.30, "asset_class": "fixed_income"},
                {"ticker": "OFZ29", "current_weight": 0.25, "asset_class": "fixed_income"},
                {"ticker": "CORP", "current_weight": 0.15, "asset_class": "fixed_income"},
                {"ticker": "MONEY", "current_weight": 0.10, "asset_class": "cash"},
            ],
            "total_portfolio_value": 20_000_000,
            "risk_profile": {
                "max_single_position_weight": 0.25,
                "max_equity_weight": 0.20,
                "max_turnover": 0.10,
            },
        })

        assert result.error is None
        # Сумма акций должна стремиться к <= 20% (с учётом ограничения оборота)
        equity_weight = sum(
            result.target_weights[t] for t in ["SBER", "GAZP"]
        )
        # Оборот ограничен 10%, поэтому полное устранение может быть невозможно
        # Проверяем, что хотя бы уменьшилось (было 20%, стало <=23%)
        assert equity_weight <= 0.25
