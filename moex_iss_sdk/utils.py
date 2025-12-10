"""
Вспомогательные функции SDK: работа с датами, кэш, rate limiting.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from datetime import date, datetime, timezone
import os
from typing import Any, Callable, Iterable, Optional

from .exceptions import DateRangeTooLargeError

MAX_LOOKBACK_DAYS = int(os.getenv("MOEX_ISS_MAX_LOOKBACK_DAYS", "730"))


def utc_now() -> datetime:
    """Вернуть текущее время в UTC (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def coerce_date(value: date | datetime | str) -> date:
    """
    Привести поддерживаемые типы к `date`. Строки парсятся как ISO‑даты.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")


def validate_date_range(
    from_date: date,
    to_date: date,
    max_lookback_days: int = MAX_LOOKBACK_DAYS,
) -> None:
    """
    Проверить, что `from_date` не позже `to_date` и глубина не превышает лимит.
    """
    if from_date > to_date:
        raise DateRangeTooLargeError(
            "from_date is after to_date",
            details={"from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
        )
    delta_days = (to_date - from_date).days
    if delta_days > max_lookback_days:
        raise DateRangeTooLargeError(
            f"Requested range {delta_days} days exceeds limit {max_lookback_days}",
            details={"from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
        )


def parse_iss_table(section: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Преобразовать секцию ISS ({'columns': [...], 'data': [...]}) в список словарей.
    Вернуть пустой список, если секции нет или она некорректна.
    """
    if not section or "columns" not in section or "data" not in section:
        return []
    columns: list[str] = section.get("columns", [])
    rows: list[list[Any]] = section.get("data", [])
    result: list[dict[str, Any]] = []
    for row in rows:
        mapped = {col: row[idx] if idx < len(row) else None for idx, col in enumerate(columns)}
        result.append(mapped)
    return result


def build_cache_key(namespace: str, *parts: Iterable[Any]) -> str:
    """Сформировать стабильный ключ кэша из произвольных частей."""
    flattened: list[str] = [namespace]
    for part in parts:
        if isinstance(part, (list, tuple, set)):
            flattened.append(",".join(map(str, part)))
        else:
            flattened.append(str(part))
    return "::".join(flattened)


class TTLCache:
    """Потокобезопасный TTL‑кэш с ограничением размера."""

    def __init__(self, max_size: int = 256, ttl_seconds: int = 30, *, time_func: Callable[[], float] | None = None) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._now = time_func or time.monotonic
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            self._evict_expired()
            if key not in self._data:
                return None
            expires_at, value = self._data.pop(key)
            if expires_at < self._now():
                return None
            # переустанавливаем, чтобы сохранить порядок LRU
            self._data[key] = (expires_at, value)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._evict_expired()
            expires_at = self._now() + self.ttl_seconds
            if key in self._data:
                self._data.pop(key)
            self._data[key] = (expires_at, value)
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def _evict_expired(self) -> None:
        now = self._now()
        keys_to_delete = [key for key, (expires_at, _) in self._data.items() if expires_at < now]
        for key in keys_to_delete:
            self._data.pop(key, None)


class SimpleRateLimiter:
    """Блокирующий rate limiter, удерживающий запросы ISS в пределах RPS."""

    def __init__(self, rate_limit_rps: float) -> None:
        self.rate_limit_rps = rate_limit_rps
        self._lock = threading.Lock()
        self._min_interval = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 0
        self._last_acquired = 0.0

    def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_acquired
            sleep_for = self._min_interval - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_acquired = time.monotonic()


class RateLimiter(SimpleRateLimiter):
    """
    Псевдоним для совместимости с архитектурным описанием.

    При необходимости можно расширить кастомной логикой, не ломая вызовы
    `SimpleRateLimiter`.
    """

    pass
