"""
Модуль доменных расчётов для базовых метрик финансовых инструментов.

Функции этого модуля используются MCP-инструментами для вычисления метрик
без дублирования логики расчётов.
"""

from __future__ import annotations

import math
from typing import Optional

from moex_iss_sdk.models import IndexConstituent, OhlcvBar


def calc_total_return_pct(bars: list[OhlcvBar]) -> Optional[float]:
    """
    Вычислить общую доходность (total return) в процентах по временному ряду OHLCV.

    Args:
        bars: Список баров OHLCV, отсортированный по времени (от старых к новым).

    Returns:
        Процентная доходность от первого закрытия к последнему, или None если данных недостаточно.
    """
    if not bars or len(bars) < 2:
        return None

    first_close = bars[0].close
    last_close = bars[-1].close

    if first_close <= 0:
        return None

    return ((last_close - first_close) / first_close) * 100.0


def calc_annualized_volatility(bars: list[OhlcvBar]) -> Optional[float]:
    """
    Вычислить годовую волатильность (annualized volatility) в процентах по временному ряду OHLCV.

    Используется формула на основе логарифмических доходностей (log returns).

    Args:
        bars: Список баров OHLCV, отсортированный по времени (от старых к новым).

    Returns:
        Годовая волатильность в процентах, или None если данных недостаточно.
    """
    if not bars or len(bars) < 2:
        return None

    # Вычисляем логарифмические доходности
    log_returns: list[float] = []
    for i in range(1, len(bars)):
        prev_close = bars[i - 1].close
        curr_close = bars[i].close
        if prev_close > 0 and curr_close > 0:
            log_return = math.log(curr_close / prev_close)
            log_returns.append(log_return)

    if len(log_returns) < 2:
        return None

    # Среднее значение логарифмических доходностей
    mean_log_return = sum(log_returns) / len(log_returns)

    # Дисперсия
    variance = sum((lr - mean_log_return) ** 2 for lr in log_returns) / (len(log_returns) - 1)

    # Стандартное отклонение (дневное)
    daily_std = math.sqrt(variance)

    # Предполагаем, что данные дневные (252 торговых дня в году)
    # Если интервал другой, нужно скорректировать множитель
    trading_days_per_year = 252.0
    annualized_vol = daily_std * math.sqrt(trading_days_per_year)

    # Конвертируем в проценты
    return annualized_vol * 100.0


def calc_avg_daily_volume(bars: list[OhlcvBar]) -> Optional[float]:
    """
    Вычислить средний дневной объём торгов по временному ряду OHLCV.

    Args:
        bars: Список баров OHLCV.

    Returns:
        Средний объём за период, или None если данных недостаточно.
    """
    if not bars:
        return None

    volumes = [bar.volume for bar in bars if bar.volume is not None and bar.volume > 0]

    if not volumes:
        return None

    return sum(volumes) / len(volumes)


def calc_top5_weight_pct(constituents: list[IndexConstituent]) -> Optional[float]:
    """
    Вычислить суммарный вес топ-5 бумаг в индексе.

    Args:
        constituents: Список компонентов индекса с весами.

    Returns:
        Суммарный вес топ-5 в процентах, или None если данных недостаточно.
    """
    if not constituents:
        return None

    # Сортируем по весу (по убыванию) и берём топ-5
    sorted_by_weight = sorted(constituents, key=lambda c: c.weight_pct, reverse=True)
    top5 = sorted_by_weight[:5]

    return sum(c.weight_pct for c in top5)


def calc_intraday_volatility_estimate(
    open_price: Optional[float],
    high_price: Optional[float],
    low_price: Optional[float],
    close_price: float,
) -> Optional[float]:
    """
    Оценить внутридневную волатильность на основе цен OHLC одного дня.

    Используется упрощённая формула на основе диапазона (high - low).

    Args:
        open_price: Цена открытия (опционально).
        high_price: Максимальная цена за день (опционально).
        low_price: Минимальная цена за день (опционально).
        close_price: Цена закрытия.

    Returns:
        Оценка внутридневной волатильности в процентах, или None если данных недостаточно.
    """
    if close_price <= 0:
        return None

    # Если есть high и low, используем их
    if high_price is not None and low_price is not None and high_price > low_price:
        price_range = high_price - low_price
        # Нормализуем на цену открытия, если она есть, иначе на закрытие
        base_price = open_price if open_price is not None and open_price > 0 else close_price
        if base_price <= 0:
            return None
        return (price_range / base_price) * 100.0

    # Если есть только open и close, используем их разницу
    if open_price is not None and open_price > 0:
        price_range = abs(close_price - open_price)
        return (price_range / open_price) * 100.0

    return None


