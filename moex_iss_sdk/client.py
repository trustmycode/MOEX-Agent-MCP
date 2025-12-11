"""
HTTP‑клиент для MOEX ISS с типизированными моделями, опциональным кэшем
и rate limiting.

Наружу отдаются только несколько высокоуровневых методов; внутренняя логика
HTTP/обработки ошибок сосредоточена здесь, чтобы слой MCP оставался тонким.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

# Загружаем .env.sdk (приоритет) и затем общий .env
load_dotenv(dotenv_path=".env.sdk")
load_dotenv()

from . import endpoints
from .exceptions import InvalidTickerError, IssServerError, IssTimeoutError, UnknownIssError
from .models import DividendRecord, IndexConstituent, OhlcvBar, SecurityInfo, SecuritySnapshot
from .utils import MAX_LOOKBACK_DAYS, RateLimiter, TTLCache, coerce_date, parse_iss_table, utc_now, validate_date_range

# Значения по умолчанию берутся из окружения, чтобы не держать их захардкоженными.
DEFAULT_RATE_LIMIT_RPS = float(os.getenv("MOEX_ISS_RATE_LIMIT_RPS", "3"))
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("MOEX_ISS_TIMEOUT_SECONDS", "10"))
DEFAULT_ENABLE_CACHE = os.getenv("ENABLE_CACHE", "false").lower() == "true"
DEFAULT_CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "30"))
DEFAULT_CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "256"))
DEFAULT_MAX_RETRIES = int(os.getenv("MOEX_ISS_MAX_RETRIES", "2"))
DEFAULT_RETRY_BACKOFF_SECONDS = float(os.getenv("MOEX_ISS_RETRY_BACKOFF_SECONDS", "0.5"))


@dataclass
class IssClientSettings:
    """Настройки `IssClient`."""

    base_url: str = endpoints.DEFAULT_BASE_URL
    rate_limit_rps: float = DEFAULT_RATE_LIMIT_RPS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    enable_cache: bool = DEFAULT_ENABLE_CACHE
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
    cache_max_size: int = DEFAULT_CACHE_MAX_SIZE
    default_board: str = endpoints.DEFAULT_BOARD
    default_interval: str = endpoints.DEFAULT_INTERVAL
    max_lookback_days: int = MAX_LOOKBACK_DAYS
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS

    @classmethod
    def from_env(cls) -> "IssClientSettings":
        """Сконструировать настройки из переменных окружения."""
        return cls(
            base_url=os.getenv("MOEX_ISS_BASE_URL", endpoints.DEFAULT_BASE_URL),
            rate_limit_rps=float(os.getenv("MOEX_ISS_RATE_LIMIT_RPS", str(DEFAULT_RATE_LIMIT_RPS))),
            timeout_seconds=float(os.getenv("MOEX_ISS_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))),
            enable_cache=os.getenv("ENABLE_CACHE", str(DEFAULT_ENABLE_CACHE)).lower() == "true",
            cache_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS))),
            cache_max_size=int(os.getenv("CACHE_MAX_SIZE", str(DEFAULT_CACHE_MAX_SIZE))),
            default_board=os.getenv("MOEX_ISS_DEFAULT_BOARD", endpoints.DEFAULT_BOARD),
            default_interval=os.getenv("MOEX_ISS_DEFAULT_INTERVAL", endpoints.DEFAULT_INTERVAL),
            max_lookback_days=int(os.getenv("MOEX_ISS_MAX_LOOKBACK_DAYS", str(MAX_LOOKBACK_DAYS))),
            max_retries=int(os.getenv("MOEX_ISS_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))),
            retry_backoff_seconds=float(os.getenv("MOEX_ISS_RETRY_BACKOFF_SECONDS", str(DEFAULT_RETRY_BACKOFF_SECONDS))),
        )


class IssClient:
    """
    Типизированный клиент MOEX ISS с общими настройками, rate limiting и
    опциональным TTL‑кэшем.

    Класс сознательно синхронный ради простоты; при желании его можно обернуть
    в асинхронный адаптер. Значения по умолчанию соответствуют SPEC:
    - базовый URL `https://iss.moex.com/iss/`;
    - дефолтный борд `TQBR`;
    - интервалы `"1d"` (24) и `"1h"` (60);
    - допустимый диапазон дат валидируется публичными методами.
    """

    def __init__(
        self,
        settings: Optional[IssClientSettings] = None,
        *,
        cache: Optional[TTLCache] = None,
        rate_limiter: Optional[RateLimiter] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.settings = settings or IssClientSettings.from_env()
        self._rate_limiter = rate_limiter or RateLimiter(self.settings.rate_limit_rps)
        self._sleep = sleep_func or time.sleep
        self._cache = cache or (TTLCache(self.settings.cache_max_size, self.settings.cache_ttl_seconds) if self.settings.enable_cache else None)

    # ------------------------------------------------------------------ #
    # Публичное API
    # ------------------------------------------------------------------ #
    def get_security_snapshot(self, ticker: str, board: Optional[str] = None) -> SecuritySnapshot:
        """
        Получить краткий снимок инструмента из секции marketdata ISS.

        Args:
            ticker: Тикер бумаги, например `"SBER"`.
            board: Борд MOEX (по умолчанию берётся из настроек/ENV, например `"TQBR"`).

        Returns:
            `SecuritySnapshot` с последней ценой, изменением, ликвидностью
            и сырым рядом ISS (если доступно).

        Raises:
            InvalidTickerError: ISS вернул пустую marketdata для пары.
            IssTimeoutError: ISS не ответил за `timeout_seconds`.
            IssServerError: ISS вернул 5xx.
            UnknownIssError: любая иная транспортная/JSON ошибка.
        """
        board_value = board or self.settings.default_board or endpoints.DEFAULT_BOARD
        cache_key = f"snapshot::{ticker}::{board_value}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        spec = endpoints.build_security_snapshot_endpoint(
            ticker=ticker,
            board=board_value,
            base_url=self.settings.base_url,
        )
        payload = self._get_json(spec)
        rows = parse_iss_table(payload.get("marketdata"))
        if not rows:
            raise InvalidTickerError(f"No ISS marketdata rows for {ticker}/{board}", details={"ticker": ticker, "board": board})

        row = rows[0]
        as_of = _coerce_datetime(row.get("TIME") or row.get("SYSTIME")) or utc_now()
        snapshot = SecuritySnapshot(
            ticker=ticker,
            board=board_value,
            as_of=as_of,
            last_price=_first_of(row, ["LAST", "LASTPRICE", "LCLOSEPRICE"], default=0.0),
            price_change_abs=_first_of(row, ["LASTCHANGE", "CHANGE"], default=0.0),
            price_change_pct=_first_of(row, ["LASTCHANGEPRC", "PRC"], default=0.0),
            open_price=_first_of(row, ["OPEN"]),
            high_price=_first_of(row, ["HIGH"]),
            low_price=_first_of(row, ["LOW"]),
            volume=_first_of(row, ["VOLUME", "VOLTODAY"]),
            value=_first_of(row, ["VALTODAY", "VALUE"]),
            raw=row,
        )
        if self._cache:
            self._cache.set(cache_key, snapshot)
        return snapshot

    def get_security_info(self, ticker: str) -> SecurityInfo:
        """
        Получить статическое описание бумаги из /securities/{ticker}.json.

        Используется, в частности, для расчёта капитализации и вспомогательных
        метрик (issuesize, ISIN, валюта номинала и т.п.).

        Args:
            ticker: Тикер бумаги (SECID).

        Returns:
            Объект SecurityInfo с основными полями описания.

        Raises:
            InvalidTickerError: если ISS не вернул секцию description.
            IssTimeoutError | IssServerError | UnknownIssError: ошибки транспорта.
        """
        cache_key = f"security_info::{ticker}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        spec = endpoints.build_security_description_endpoint(
            ticker=ticker,
            base_url=self.settings.base_url,
        )
        payload = self._get_json(spec)
        rows = parse_iss_table(payload.get("description"))
        if not rows:
            raise InvalidTickerError(f"No ISS description rows for {ticker}", details={"ticker": ticker})

        # Преобразуем в словарь name -> value
        by_name: Dict[str, Any] = {}
        for row in rows:
            name = str(row.get("name") or row.get("NAME") or "").upper()
            if not name:
                continue
            by_name[name] = row

        def _value(name: str) -> Any:
            entry = by_name.get(name.upper())
            if not entry:
                return None
            return entry.get("value") if "value" in entry else entry.get("VALUE")

        info = SecurityInfo(
            ticker=ticker,
            isin=_value("ISIN"),
            issue_size=_maybe_float(_value("ISSUESIZE")),
            face_value=_maybe_float(_value("FACEVALUE")),
            face_unit=_value("FACEUNIT"),
            short_name=_value("SHORTNAME"),
            full_name=_value("NAME"),
        )
        if self._cache:
            self._cache.set(cache_key, info)
        return info

    def get_ohlcv_series(
        self,
        ticker: str,
        board: Optional[str],
        from_date: date,
        to_date: date,
        interval: Optional[str] = None,
        *,
        max_lookback_days: Optional[int] = None,
    ) -> List[OhlcvBar]:
        """
        Получить временной ряд OHLCV по тикеру/борду с проверкой дат.

        Args:
            ticker: Тикер бумаги.
            board: Борд MOEX.
            from_date: Начало периода (включительно).
            to_date: Конец периода (включительно).
            interval: `"1d"` → ISS interval 24, `"1h"` → 60 (по умолчанию из настроек/ENV).
            max_lookback_days: Ограничение глубины истории (по умолчанию из настроек/ENV).

        Returns:
            Список `OhlcvBar` в порядке, который вернул ISS.

        Raises:
            DateRangeTooLargeError: диапазон некорректен или превышает `max_lookback_days`.
            InvalidTickerError: ISS вернул пустые свечи для тикера/борда.
            IssTimeoutError | IssServerError | UnknownIssError: проблемы транспорта/JSON.
        """
        board_value = board or self.settings.default_board or endpoints.DEFAULT_BOARD
        interval_value = interval or self.settings.default_interval or endpoints.DEFAULT_INTERVAL
        lookback = max_lookback_days or self.settings.max_lookback_days

        from_d = coerce_date(from_date)
        to_d = coerce_date(to_date)
        validate_date_range(from_d, to_d, max_lookback_days=lookback)

        cache_key = f"ohlcv::{ticker}::{board_value}::{from_d.isoformat()}::{to_d.isoformat()}::{interval_value}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        spec = endpoints.build_ohlcv_endpoint(
            ticker=ticker,
            board=board_value,
            from_date=from_d,
            to_date=to_d,
            interval=interval_value,
            base_url=self.settings.base_url,
        )
        payload = self._get_json(spec)
        rows = parse_iss_table(payload.get("candles"))
        if not rows:
            raise InvalidTickerError(f"No ISS candles for {ticker}/{board}", details={"ticker": ticker, "board": board})

        bars: list[OhlcvBar] = []
        for row in rows:
            ts = _coerce_datetime(row.get("begin") or row.get("datetime") or row.get("time"))
            if ts is None:
                continue
            bars.append(
                OhlcvBar(
                    ts=ts,
                    open=float(_first_of(row, ["open"], default=0.0)),
                    high=float(_first_of(row, ["high"], default=0.0)),
                    low=float(_first_of(row, ["low"], default=0.0)),
                    close=float(_first_of(row, ["close"], default=0.0)),
                    volume=_maybe_float(row.get("volume")),
                    value=_maybe_float(row.get("value")),
                    board=board_value,
                    raw=row,
                )
            )

        if self._cache:
            self._cache.set(cache_key, bars)
        return bars

    def get_index_constituents(
        self,
        index_ticker: str,
        as_of_date: date,
    ) -> List[IndexConstituent]:
        """
        Получить состав индекса MOEX (например, IMOEX) через statistics API.

        Args:
            index_ticker: Код индекса (например, `"IMOEX"`).
            as_of_date: Дата, на которую запрашивается состав.

        Returns:
            Список `IndexConstituent`, включающий веса и, при наличии, цены/сектор/идентификаторы.

        Raises:
            InvalidTickerError: ISS вернул пустую таблицу analytics.
            IssTimeoutError | IssServerError | UnknownIssError: ошибки транспорта.
        """
        cache_key = f"index::{index_ticker}::{as_of_date.isoformat()}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        spec = endpoints.build_index_constituents_endpoint(
            index_ticker=index_ticker,
            as_of_date=coerce_date(as_of_date),
            base_url=self.settings.base_url,
        )
        payload = self._get_json(spec)
        rows = parse_iss_table(payload.get("analytics"))
        if not rows:
            raise InvalidTickerError(f"No ISS constituents for index {index_ticker}", details={"index_ticker": index_ticker})

        members: list[IndexConstituent] = []
        for row in rows:
            members.append(
                IndexConstituent(
                    index_ticker=index_ticker,
                    ticker=str(row.get("ticker") or row.get("secids") or row.get("SECID") or ""),
                    weight_pct=float(_first_of(row, ["weight", "weight_cc"], default=0.0)),
                    last_price=_maybe_float(_first_of(row, ["LAST", "PRICE"])),
                    price_change_pct=_maybe_float(row.get("LASTCHANGEPRC") or row.get("CHANGE_PCT")),
                    sector=row.get("SECTOR") or row.get("sector"),
                    board=row.get("BOARDID") or row.get("board"),
                    figi=row.get("FIGI"),
                    isin=row.get("ISIN"),
                    raw=row,
                )
            )
        if self._cache:
            self._cache.set(cache_key, members)
        return members

    def get_security_dividends(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> List[DividendRecord]:
        """
        Получить историю дивидендов для бумаги в указанном окне дат.

        Args:
            ticker: Тикер бумаги.
            from_date: Начало окна (включительно).
            to_date: Конец окна (включительно).

        Returns:
            Список `DividendRecord` в порядке, который вернул ISS.

        Raises:
            DateRangeTooLargeError: окно дат некорректно.
            InvalidTickerError: ISS вернул пустые строки дивидендов.
            IssTimeoutError | IssServerError | UnknownIssError: ошибки транспорта.
        """
        from_d = coerce_date(from_date)
        to_d = coerce_date(to_date)
        validate_date_range(from_d, to_d)

        cache_key = f"dividends::{ticker}::{from_d.isoformat()}::{to_d.isoformat()}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        spec = endpoints.build_dividends_endpoint(
            ticker=ticker,
            from_date=from_d,
            to_date=to_d,
            base_url=self.settings.base_url,
        )
        payload = self._get_json(spec)
        rows = parse_iss_table(payload.get("dividends"))
        if not rows:
            raise InvalidTickerError(f"No ISS dividend rows for {ticker}", details={"ticker": ticker})

        dividends: list[DividendRecord] = []
        for row in rows:
            dividends.append(
                DividendRecord(
                    ticker=ticker,
                    board=row.get("BOARDID"),
                    dividend=float(_first_of(row, ["value", "VALUE"], default=0.0)),
                    currency=row.get("currencyid") or row.get("CURRENCYID"),
                    registry_close_date=_coerce_date(row.get("registryclosedate") or row.get("registry_close_date")),
                    record_date=_coerce_date(row.get("registryclosedate") or row.get("record_date")),
                    payment_date=_coerce_date(row.get("paymentdate") or row.get("payment_date")),
                    announcement_date=_coerce_date(row.get("declaredate") or row.get("announcement_date")),
                    yield_pct=_maybe_float(row.get("yield") or row.get("YIELD")),
                    raw=row,
                )
            )

        if self._cache:
            self._cache.set(cache_key, dividends)
        return dividends

    # ------------------------------------------------------------------ #
    # Внутренние вспомогательные методы
    # ------------------------------------------------------------------ #
    def _get_json(self, spec: endpoints.EndpointSpec) -> Dict[str, Any]:
        """
        Выполнить HTTP GET к ISS, распарсить JSON и при необходимости сделать ретраи.
        """
        attempts = self.settings.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            self._rate_limiter.acquire()
            try:
                return self._perform_request(spec)
            except InvalidTickerError:
                # Некорректный тикер/борд не имеет смысла ретраить
                raise
            except (IssTimeoutError, IssServerError, UnknownIssError) as exc:
                last_error = exc
                if attempt < self.settings.max_retries:
                    self._sleep(self._retry_delay(attempt))
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("Unexpected state: _get_json exhausted retries without result")

    def _perform_request(self, spec: endpoints.EndpointSpec) -> Dict[str, Any]:
        """
        Выполнить один HTTP‑запрос к ISS и преобразовать исключения в ошибки SDK.
        """
        url = spec.url
        if spec.params:
            url = f"{url}?{urlencode(spec.params)}"
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            if 500 <= exc.code < 600:
                raise IssServerError(f"ISS responded with {exc.code}", status_code=exc.code) from exc
            if exc.code == 404:
                raise InvalidTickerError("ISS returned 404 (possibly invalid ticker/board)", status_code=exc.code) from exc
            raise UnknownIssError(f"Unexpected ISS HTTP error {exc.code}", status_code=exc.code) from exc
        except URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise IssTimeoutError("Timeout while calling ISS", details={"url": url}) from exc
            raise UnknownIssError(f"Network error contacting ISS: {exc.reason}") from exc
        except socket.timeout as exc:
            raise IssTimeoutError("Timeout while calling ISS", details={"url": url}) from exc
        except json.JSONDecodeError as exc:
            raise UnknownIssError("Failed to decode ISS response as JSON", details={"url": url}) from exc

    def _retry_delay(self, attempt_index: int) -> float:
        """
        Подсчитать задержку перед повтором запроса (линейный backoff).
        """
        return max(0.0, self.settings.retry_backoff_seconds * (attempt_index + 1))


def _first_of(mapping: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    """Вернуть первое непустое значение по списку ключей в словаре."""
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _maybe_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
