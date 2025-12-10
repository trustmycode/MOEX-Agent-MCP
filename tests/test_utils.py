import time
from datetime import date, timedelta

import pytest

from moex_iss_sdk.exceptions import DateRangeTooLargeError
from moex_iss_sdk.utils import (
    MAX_LOOKBACK_DAYS,
    TTLCache,
    RateLimiter,
    SimpleRateLimiter,
    build_cache_key,
    coerce_date,
    parse_iss_table,
    validate_date_range,
)


def test_validate_date_range_too_wide():
    to_d = date.today()
    from_d = to_d - timedelta(days=MAX_LOOKBACK_DAYS + 1)
    with pytest.raises(DateRangeTooLargeError):
        validate_date_range(from_d, to_d, max_lookback_days=MAX_LOOKBACK_DAYS)


def test_validate_date_range_from_after_to():
    to_d = date.today()
    from_d = to_d + timedelta(days=1)
    with pytest.raises(DateRangeTooLargeError):
        validate_date_range(from_d, to_d)


def test_ttlcache_hit_and_expiry():
    class _FakeClock:
        def __init__(self) -> None:
            self.value = 0.0

        def __call__(self) -> float:
            return self.value

        def advance(self, delta: float) -> None:
            self.value += delta

    clock = _FakeClock()
    cache = TTLCache(max_size=2, ttl_seconds=1, time_func=clock)
    cache.set("a", 1)
    assert cache.get("a") == 1
    clock.advance(1.01)
    assert cache.get("a") is None


def test_ttlcache_eviction_respects_lru():
    cache = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    # Доступ к "a", чтобы сделать его самым свежим
    assert cache.get("a") == 1
    cache.set("c", 3)  # должен вытеснить "b"
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_parse_iss_table_to_list_of_dicts():
    section = {"columns": ["A", "B"], "data": [[1, 2], [3, 4]]}
    rows = parse_iss_table(section)
    assert rows == [{"A": 1, "B": 2}, {"A": 3, "B": 4}]


def test_build_cache_key_flattens_iterables():
    key = build_cache_key("ns", ["a", "b"], "x")
    assert key == "ns::a,b::x"


def test_coerce_date_accepts_str_and_datetime():
    today = date.today()
    assert coerce_date(today) == today
    assert coerce_date(today.isoformat()) == today


def test_simple_rate_limiter_enforces_min_interval():
    limiter = SimpleRateLimiter(rate_limit_rps=2)  # минимальный интервал 0.5s
    start = time.monotonic()
    for _ in range(3):
        limiter.acquire()
    elapsed = time.monotonic() - start
    # Два интервала по ~0.5s -> ожидаем >= 1.0s с небольшой погрешностью
    assert elapsed >= 0.95


def test_rate_limiter_alias_is_non_blocking_with_zero_rate():
    limiter = RateLimiter(rate_limit_rps=0)
    start = time.monotonic()
    limiter.acquire()
    assert (time.monotonic() - start) < 0.05
