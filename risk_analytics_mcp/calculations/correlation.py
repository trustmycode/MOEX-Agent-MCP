"""
Расчёт матрицы корреляций по рядам дневных доходностей.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Iterable, List, Mapping, Sequence

from .returns import DailyReturn


class InsufficientDataError(ValueError):
    """Недостаточно данных для оценки корреляции."""

    error_type = "INSUFFICIENT_DATA"


def _aligned_dates(tickers: Sequence[str], returns_by_ticker: Mapping[str, Sequence[DailyReturn]]) -> List[date]:
    """
    Найти общие даты для всех тикеров и убедиться, что данных достаточно.
    """

    if not tickers:
        raise InsufficientDataError("Ticker list must not be empty")

    date_sets: List[set[date]] = []
    for ticker in tickers:
        series = returns_by_ticker.get(ticker)
        if not series or len(series) < 2:
            raise InsufficientDataError(f"Not enough returns for ticker {ticker}")
        date_sets.append({point_date for point_date, _ in series})

    common_dates = set.intersection(*date_sets) if date_sets else set()
    if len(common_dates) < 2:
        raise InsufficientDataError("Not enough overlapping observations to compute correlations")
    return sorted(common_dates)


def _extract_aligned_returns(
    tickers: Sequence[str],
    returns_by_ticker: Mapping[str, Sequence[DailyReturn]],
    aligned_dates: Iterable[date],
) -> Mapping[str, List[float]]:
    aligned_dates_list = list(aligned_dates)
    aligned = {}
    for ticker in tickers:
        series = returns_by_ticker.get(ticker) or []
        values_by_date = {point_date: value for point_date, value in series}
        aligned_values = [values_by_date[point_date] for point_date in aligned_dates_list if point_date in values_by_date]
        if len(aligned_values) != len(aligned_dates_list):
            raise InsufficientDataError(f"Missing returns for ticker {ticker} on aligned dates")
        aligned[ticker] = aligned_values
    return aligned


def _pearson_correlation(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) != len(y):
        raise ValueError("Input vectors must have the same length")
    n = len(x)
    if n < 2:
        raise InsufficientDataError("At least two observations are required")

    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y)) / (n - 1)

    var_x = sum((xi - mean_x) ** 2 for xi in x) / (n - 1)
    var_y = sum((yi - mean_y) ** 2 for yi in y) / (n - 1)
    if var_x <= 0 or var_y <= 0:
        raise InsufficientDataError("Zero variance in returns; correlation is undefined")

    corr = cov / math.sqrt(var_x * var_y)
    # Защита от накопленной погрешности
    return max(-1.0, min(1.0, corr))


def compute_correlation_matrix(
    tickers: Sequence[str],
    returns_by_ticker: Mapping[str, Sequence[DailyReturn]],
) -> tuple[list[list[float]], dict]:
    """
    Построить матрицу корреляций дневных доходностей для заданных тикеров.
    """

    aligned_dates = _aligned_dates(tickers, returns_by_ticker)
    aligned_returns = _extract_aligned_returns(tickers, returns_by_ticker, aligned_dates)

    matrix: list[list[float]] = []
    for i, ticker_i in enumerate(tickers):
        row: list[float] = []
        for j, ticker_j in enumerate(tickers):
            if i == j:
                row.append(1.0)
                continue
            corr = _pearson_correlation(aligned_returns[ticker_i], aligned_returns[ticker_j])
            row.append(corr)
        matrix.append(row)

    metadata = {
        "method": "pearson",
        "num_observations": len(aligned_dates),
        "dates": [point_date.isoformat() for point_date in aligned_dates],
    }
    return matrix, metadata


__all__ = ["InsufficientDataError", "compute_correlation_matrix"]
