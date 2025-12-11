"""
Абстракция источника фундаментальных и рыночных данных и её
MOEX-ориентированная реализация.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from moex_iss_sdk import IssClient
from moex_iss_sdk.exceptions import InvalidTickerError
from moex_iss_sdk.utils import TTLCache, build_cache_key, utc_now

from ..models import IssuerFundamentals


class FundamentalsDataProvider(ABC):
    """
    Интерфейс для получения фундаментальных и базовых рыночных метрик по эмитентам.

    Все сценарии, использующие фундаментал (issuer_peers_compare, portfolio_risk,
    cfo_liquidity_report), должны работать через этот интерфейс.
    """

    @abstractmethod
    def get_issuer_fundamentals(self, ticker: str) -> IssuerFundamentals:  # pragma: no cover - интерфейс
        """Вернуть фундаментальные и рыночные метрики по одному тикеру."""

    @abstractmethod
    def get_issuer_fundamentals_many(self, tickers: Sequence[str]) -> Dict[str, IssuerFundamentals]:  # pragma: no cover - интерфейс  # noqa: E501
        """Вернуть метрики сразу для нескольких тикеров."""


class MoexIssFundamentalsProvider(FundamentalsDataProvider):
    """
    Реализация FundamentalsDataProvider поверх moex_iss_sdk.IssClient.

    Для MVP использует только публичные JSON-ресурсы ISS:
    - /engines/stock/markets/shares/... (get_security_snapshot)
    - /securities/{ticker}.json (описание бумаги — issuesize, ISIN и т.п.)
    - /securities/{ticker}/dividends.json (история дивидендов для див. доходности)
    """

    def __init__(
        self,
        iss_client: IssClient,
        *,
        cache: Optional[TTLCache] = None,
        dividend_lookback_days: Optional[int] = None,
    ) -> None:
        self._iss_client = iss_client
        ttl_seconds = int(os.getenv("RISK_FUNDAMENTALS_CACHE_TTL_SECONDS", "900"))
        max_size = int(os.getenv("RISK_FUNDAMENTALS_CACHE_MAX_SIZE", "256"))
        self._cache = cache or TTLCache(max_size=max_size, ttl_seconds=ttl_seconds)
        self._dividend_lookback_days = dividend_lookback_days or int(
            os.getenv("RISK_FUNDAMENTALS_DIVIDEND_LOOKBACK_DAYS", "365")
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_issuer_fundamentals(self, ticker: str) -> IssuerFundamentals:
        normalized_ticker = self._normalize_ticker(ticker)
        cache_key = build_cache_key("fundamentals", normalized_ticker)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        fundamentals = self._load_from_iss(normalized_ticker)
        self._cache.set(cache_key, fundamentals)
        return fundamentals

    def get_issuer_fundamentals_many(self, tickers: Sequence[str]) -> Dict[str, IssuerFundamentals]:
        results: Dict[str, IssuerFundamentals] = {}
        for ticker in tickers:
            fundamentals = self.get_issuer_fundamentals(ticker)
            results[fundamentals.ticker] = fundamentals
        return results

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        value = (ticker or "").strip().upper()
        if not value:
            raise ValueError("ticker cannot be empty")
        return value

    def _load_from_iss(self, ticker: str) -> IssuerFundamentals:
        """
        Загрузить данные из MOEX ISS и построить IssuerFundamentals.

        В текущем MVP реализованы:
        - цена и капитализация (через snapshot + issuesize);
        - дивидендная доходность (по сумме дивидендов за lookback / цену).
        Отчётные показатели (revenue, EBITDA и др.) оставляются None до
        появления стабильного JSON-источника (CCI/MSFO или аналогичный).
        """
        # Бросает InvalidTickerError, которая далее будет замаплена в error_type.
        snapshot = self._iss_client.get_security_snapshot(ticker, board=None)

        # Статическое описание бумаги: ISIN, ISSUESIZE, FACEUNIT и др.
        # Реализовано в IssClient поверх /securities/{ticker}.json.
        security_info = self._iss_client.get_security_info(ticker)

        price = snapshot.last_price
        shares_outstanding = security_info.issue_size
        market_cap = None
        if price is not None and shares_outstanding is not None:
            market_cap = float(price) * float(shares_outstanding)

        dividend_yield_pct = self._compute_dividend_yield_pct(ticker, price)

        return IssuerFundamentals(
            ticker=ticker,
            isin=security_info.isin,
            issuer_name=security_info.short_name,
            reporting_currency=security_info.face_unit or "RUB",
            as_of=snapshot.as_of,
            # Отчётные показатели (revenue/EBITDA/net_income/долг) остаются None
            # до появления надёжного JSON-источника (CCI/MSFO).
            price=price,
            shares_outstanding=shares_outstanding,
            market_cap=market_cap,
            dividend_yield_pct=dividend_yield_pct,
        )

    def _compute_dividend_yield_pct(self, ticker: str, price: Optional[float]) -> Optional[float]:
        """
        Оценить дивидендную доходность по сумме дивидендов за lookback / цену.

        Если цена отсутствует или ISS не возвращает дивиденды за период,
        возвращается None.
        """
        if price is None or price <= 0:
            return None

        to_date = utc_now().date()
        from_date = to_date - timedelta(days=self._dividend_lookback_days)

        try:
            dividends = self._iss_client.get_security_dividends(ticker, from_date, to_date)
        except InvalidTickerError:
            # Если у бумаги нет дивидендной истории, считаем доходность неопределённой.
            return None

        total_dividend = 0.0
        for record in dividends:
            if record.dividend is not None:
                total_dividend += float(record.dividend)

        if total_dividend <= 0:
            return None
        return (total_dividend / float(price)) * 100.0


__all__ = ["FundamentalsDataProvider", "MoexIssFundamentalsProvider"]

