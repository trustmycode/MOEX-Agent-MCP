"""
Unit-тесты для модуля domain_calculations.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Импорт напрямую из файла, минуя __init__.py
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "domain_calculations",
    ROOT / "moex_iss_mcp" / "domain_calculations.py"
)
domain_calculations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(domain_calculations)

calc_total_return_pct = domain_calculations.calc_total_return_pct
calc_annualized_volatility = domain_calculations.calc_annualized_volatility
calc_avg_daily_volume = domain_calculations.calc_avg_daily_volume
calc_top5_weight_pct = domain_calculations.calc_top5_weight_pct
calc_intraday_volatility_estimate = domain_calculations.calc_intraday_volatility_estimate

from moex_iss_sdk.models import IndexConstituent, OhlcvBar


class TestCalcTotalReturnPct:
    """Тесты для calc_total_return_pct."""

    def test_empty_list_returns_none(self):
        """Пустой список должен вернуть None."""
        assert calc_total_return_pct([]) is None

    def test_single_bar_returns_none(self):
        """Один бар недостаточен для расчёта доходности."""
        bar = OhlcvBar(
            ts=datetime.now(timezone.utc),
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
        )
        assert calc_total_return_pct([bar]) is None

    def test_positive_return(self):
        """Проверка расчёта положительной доходности."""
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=105.0, low=95.0, close=100.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=100.0, high=110.0, low=100.0, close=110.0),
        ]
        result = calc_total_return_pct(bars)
        assert result == 10.0  # (110 - 100) / 100 * 100

    def test_negative_return(self):
        """Проверка расчёта отрицательной доходности."""
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=105.0, low=95.0, close=100.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=100.0, high=100.0, low=90.0, close=90.0),
        ]
        result = calc_total_return_pct(bars)
        assert result == -10.0  # (90 - 100) / 100 * 100

    def test_zero_first_close_returns_none(self):
        """Если первая цена закрытия равна нулю, должен вернуться None."""
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=0.0, high=0.0, low=0.0, close=0.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=100.0, high=110.0, low=100.0, close=110.0),
        ]
        assert calc_total_return_pct(bars) is None


class TestCalcAnnualizedVolatility:
    """Тесты для calc_annualized_volatility."""

    def test_empty_list_returns_none(self):
        """Пустой список должен вернуть None."""
        assert calc_annualized_volatility([]) is None

    def test_single_bar_returns_none(self):
        """Один бар недостаточен для расчёта волатильности."""
        bar = OhlcvBar(
            ts=datetime.now(timezone.utc),
            open=100.0,
            high=105.0,
            low=95.0,
            close=100.0,
        )
        assert calc_annualized_volatility([bar]) is None

    def test_volatility_calculation(self):
        """Проверка расчёта волатильности на простом примере."""
        # Создаём ряд с небольшой волатильностью
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=101.0, low=99.0, close=100.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=100.0, high=101.0, low=99.0, close=100.5),
            OhlcvBar(ts=datetime(2024, 1, 3, tzinfo=timezone.utc), open=100.5, high=101.5, low=99.5, close=101.0),
        ]
        result = calc_annualized_volatility(bars)
        assert result is not None
        assert result >= 0  # Волатильность не может быть отрицательной

    def test_zero_prices_returns_none(self):
        """Если есть нулевые цены, должен вернуться None."""
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=0.0, high=0.0, low=0.0, close=0.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=0.0, high=0.0, low=0.0, close=0.0),
        ]
        assert calc_annualized_volatility(bars) is None


class TestCalcAvgDailyVolume:
    """Тесты для calc_avg_daily_volume."""

    def test_empty_list_returns_none(self):
        """Пустой список должен вернуть None."""
        assert calc_avg_daily_volume([]) is None

    def test_average_calculation(self):
        """Проверка расчёта среднего объёма."""
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=105.0, low=95.0, close=100.0, volume=1000.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=100.0, high=110.0, low=100.0, close=110.0, volume=2000.0),
            OhlcvBar(ts=datetime(2024, 1, 3, tzinfo=timezone.utc), open=110.0, high=115.0, low=110.0, close=115.0, volume=3000.0),
        ]
        result = calc_avg_daily_volume(bars)
        assert result == 2000.0  # (1000 + 2000 + 3000) / 3

    def test_ignores_none_volumes(self):
        """None объёмы должны игнорироваться."""
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=105.0, low=95.0, close=100.0, volume=1000.0),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=100.0, high=110.0, low=100.0, close=110.0, volume=None),
            OhlcvBar(ts=datetime(2024, 1, 3, tzinfo=timezone.utc), open=110.0, high=115.0, low=110.0, close=115.0, volume=3000.0),
        ]
        result = calc_avg_daily_volume(bars)
        assert result == 2000.0  # (1000 + 3000) / 2

    def test_all_none_volumes_returns_none(self):
        """Если все объёмы None, должен вернуться None."""
        bars = [
            OhlcvBar(ts=datetime(2024, 1, 1, tzinfo=timezone.utc), open=100.0, high=105.0, low=95.0, close=100.0, volume=None),
            OhlcvBar(ts=datetime(2024, 1, 2, tzinfo=timezone.utc), open=100.0, high=110.0, low=100.0, close=110.0, volume=None),
        ]
        assert calc_avg_daily_volume(bars) is None


class TestCalcTop5WeightPct:
    """Тесты для calc_top5_weight_pct."""

    def test_empty_list_returns_none(self):
        """Пустой список должен вернуть None."""
        assert calc_top5_weight_pct([]) is None

    def test_less_than_5_constituents(self):
        """Если компонентов меньше 5, должны суммироваться все."""
        constituents = [
            IndexConstituent(ticker="A", weight_pct=10.0),
            IndexConstituent(ticker="B", weight_pct=20.0),
            IndexConstituent(ticker="C", weight_pct=15.0),
        ]
        result = calc_top5_weight_pct(constituents)
        assert result == 45.0  # 10 + 20 + 15

    def test_exactly_5_constituents(self):
        """Если компонентов ровно 5, должны суммироваться все."""
        constituents = [
            IndexConstituent(ticker="A", weight_pct=10.0),
            IndexConstituent(ticker="B", weight_pct=20.0),
            IndexConstituent(ticker="C", weight_pct=15.0),
            IndexConstituent(ticker="D", weight_pct=12.0),
            IndexConstituent(ticker="E", weight_pct=8.0),
        ]
        result = calc_top5_weight_pct(constituents)
        assert result == 65.0  # 10 + 20 + 15 + 12 + 8

    def test_more_than_5_constituents(self):
        """Если компонентов больше 5, должны суммироваться только топ-5."""
        constituents = [
            IndexConstituent(ticker="A", weight_pct=25.0),  # топ-1
            IndexConstituent(ticker="B", weight_pct=20.0),  # топ-2
            IndexConstituent(ticker="C", weight_pct=15.0),  # топ-3
            IndexConstituent(ticker="D", weight_pct=12.0),  # топ-4
            IndexConstituent(ticker="E", weight_pct=8.0),   # топ-5
            IndexConstituent(ticker="F", weight_pct=5.0),   # не входит
            IndexConstituent(ticker="G", weight_pct=3.0),   # не входит
        ]
        result = calc_top5_weight_pct(constituents)
        assert result == 80.0  # 25 + 20 + 15 + 12 + 8


class TestCalcIntradayVolatilityEstimate:
    """Тесты для calc_intraday_volatility_estimate."""

    def test_with_high_low(self):
        """Расчёт на основе high и low."""
        result = calc_intraday_volatility_estimate(
            open_price=100.0,
            high_price=110.0,
            low_price=90.0,
            close_price=105.0,
        )
        assert result is not None
        assert result == 20.0  # (110 - 90) / 100 * 100

    def test_with_open_close_only(self):
        """Расчёт на основе open и close, если нет high/low."""
        result = calc_intraday_volatility_estimate(
            open_price=100.0,
            high_price=None,
            low_price=None,
            close_price=105.0,
        )
        assert result is not None
        assert result == 5.0  # abs(105 - 100) / 100 * 100

    def test_zero_close_price_returns_none(self):
        """Если цена закрытия равна нулю, должен вернуться None."""
        result = calc_intraday_volatility_estimate(
            open_price=100.0,
            high_price=110.0,
            low_price=90.0,
            close_price=0.0,
        )
        assert result is None

    def test_insufficient_data_returns_none(self):
        """Если данных недостаточно, должен вернуться None."""
        result = calc_intraday_volatility_estimate(
            open_price=None,
            high_price=None,
            low_price=None,
            close_price=100.0,
        )
        assert result is None


