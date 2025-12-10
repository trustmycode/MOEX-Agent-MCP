from datetime import date

import pytest

from moex_iss_sdk import IssClient, IssClientSettings
from moex_iss_sdk.exceptions import DateRangeTooLargeError, InvalidTickerError
from moex_iss_sdk.models import DividendRecord, IndexConstituent, OhlcvBar, SecuritySnapshot
from moex_iss_sdk.utils import TTLCache


class FakeClient(IssClient):
    """Клиент, который возвращает заранее подготовленные payload вместо ISS."""

    def __init__(self, payloads, *, cache=None):
        settings = IssClientSettings.from_env()
        settings.rate_limit_rps = 0
        settings.enable_cache = bool(cache)
        settings.cache_ttl_seconds = 60
        settings.cache_max_size = 16
        super().__init__(settings, cache=cache)
        self._payloads = iter(payloads)

    def _get_json(self, spec):
        return next(self._payloads)


def test_get_security_snapshot_parses_and_caches():
    payload = {
        "marketdata": {
            "columns": [
                "SECID",
                "BOARDID",
                "TIME",
                "LAST",
                "LASTCHANGE",
                "LASTCHANGEPRC",
                "OPEN",
                "HIGH",
                "LOW",
                "VOLUME",
                "VALTODAY",
            ],
            "data": [
                [
                    "SBER",
                    "TQBR",
                    "2025-01-01T10:00:00",
                    300.1,
                    1.5,
                    0.5,
                    299.0,
                    301.0,
                    298.0,
                    1000,
                    2_000_000,
                ]
            ],
        }
    }
    cache = TTLCache(max_size=4, ttl_seconds=60)
    client = FakeClient([payload], cache=cache)
    snap1 = client.get_security_snapshot("SBER", "TQBR")
    assert isinstance(snap1, SecuritySnapshot)
    assert snap1.last_price == 300.1
    snap2 = client.get_security_snapshot("SBER", "TQBR")
    assert snap1 is snap2  # вернулось из кэша (второго payload нет)


def test_get_ohlcv_series_parses_rows():
    payload = {
        "candles": {
            "columns": ["begin", "open", "high", "low", "close", "volume", "value"],
            "data": [["2025-01-01T10:00:00", 1.0, 2.0, 0.5, 1.5, 123, 456]],
        }
    }
    client = FakeClient([payload])
    bars = client.get_ohlcv_series("SBER", "TQBR", date(2025, 1, 1), date(2025, 1, 2), "1d")
    assert len(bars) == 1
    bar = bars[0]
    assert isinstance(bar, OhlcvBar)
    assert bar.open == 1.0 and bar.close == 1.5


def test_get_ohlcv_series_rejects_invalid_interval():
    client = FakeClient([])
    with pytest.raises(ValueError):
        client.get_ohlcv_series("SBER", "TQBR", date(2025, 1, 1), date(2025, 1, 2), "5m")


def test_get_ohlcv_series_rejects_too_long_range():
    client = FakeClient([])
    with pytest.raises(DateRangeTooLargeError):
        client.get_ohlcv_series("SBER", "TQBR", date(2000, 1, 1), date(2025, 1, 1), "1d")


def test_get_index_constituents_parses_analytics():
    payload = {
        "analytics": {
            "columns": ["indexid", "tradedate", "ticker", "secids", "weight"],
            "data": [["IMOEX", "2025-01-01", "SBER", "SBER", 32.1]],
        }
    }
    client = FakeClient([payload])
    members = client.get_index_constituents("IMOEX", date(2025, 1, 1))
    assert len(members) == 1
    m = members[0]
    assert isinstance(m, IndexConstituent)
    assert m.ticker == "SBER"
    assert m.weight_pct == 32.1


def test_get_index_constituents_raises_on_empty():
    payload = {"analytics": {"columns": ["indexid"], "data": []}}
    client = FakeClient([payload])
    with pytest.raises(InvalidTickerError):
        client.get_index_constituents("NO_INDEX", date(2025, 1, 1))


def test_get_security_dividends_parses_rows():
    payload = {
        "dividends": {
            "columns": ["BOARDID", "value", "currencyid", "registryclosedate", "paymentdate", "declaredate"],
            "data": [["TQBR", 12.34, "RUB", "2025-01-05", "2025-02-01", "2025-01-01"]],
        }
    }
    client = FakeClient([payload])
    divs = client.get_security_dividends("SBER", date(2025, 1, 1), date(2025, 12, 31))
    assert len(divs) == 1
    div = divs[0]
    assert isinstance(div, DividendRecord)
    assert div.dividend == 12.34
    assert div.registry_close_date.isoformat() == "2025-01-05"


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("MOEX_ISS_BASE_URL", "http://example/")
    monkeypatch.setenv("MOEX_ISS_RATE_LIMIT_RPS", "9")
    monkeypatch.setenv("MOEX_ISS_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("ENABLE_CACHE", "true")
    monkeypatch.setenv("CACHE_TTL_SECONDS", "42")
    monkeypatch.setenv("CACHE_MAX_SIZE", "99")
    monkeypatch.setenv("MOEX_ISS_DEFAULT_BOARD", "TESTB")
    monkeypatch.setenv("MOEX_ISS_DEFAULT_INTERVAL", "1h")
    monkeypatch.setenv("MOEX_ISS_MAX_LOOKBACK_DAYS", "365")
    monkeypatch.setenv("MOEX_ISS_MAX_RETRIES", "4")
    monkeypatch.setenv("MOEX_ISS_RETRY_BACKOFF_SECONDS", "0.1")
    settings = IssClientSettings.from_env()
    assert settings.base_url == "http://example/"
    assert settings.rate_limit_rps == 9.0
    assert settings.timeout_seconds == 5.0
    assert settings.enable_cache is True
    assert settings.cache_ttl_seconds == 42
    assert settings.cache_max_size == 99
    assert settings.default_board == "TESTB"
    assert settings.default_interval == "1h"
    assert settings.max_lookback_days == 365
    assert settings.max_retries == 4
    assert settings.retry_backoff_seconds == 0.1


def test_snapshot_no_cache_hits_second_payload():
    payload1 = {
        "marketdata": {
            "columns": ["SECID", "BOARDID", "TIME", "LAST"],
            "data": [["SBER", "TQBR", "2025-01-01T10:00:00", 100.0]],
        }
    }
    payload2 = {
        "marketdata": {
            "columns": ["SECID", "BOARDID", "TIME", "LAST"],
            "data": [["SBER", "TQBR", "2025-01-01T10:05:00", 200.0]],
        }
    }
    client = FakeClient([payload1, payload2])  # кэш отключён
    snap1 = client.get_security_snapshot("SBER", "TQBR")
    snap2 = client.get_security_snapshot("SBER", "TQBR")
    assert snap1.last_price == 100.0
    assert snap2.last_price == 200.0


def test_defaults_fall_back_to_settings(monkeypatch):
    monkeypatch.setenv("MOEX_ISS_DEFAULT_BOARD", "ZZZ")
    monkeypatch.setenv("MOEX_ISS_DEFAULT_INTERVAL", "1h")
    client = FakeClient(
        [
            {
                "candles": {
                    "columns": ["begin", "open", "high", "low", "close", "volume", "value", "boardid"],
                    "data": [["2025-01-01T10:00:00", 1, 2, 0.5, 1.5, 10, 20, "ZZZ"]],
                }
            }
        ]
    )
    bars = client.get_ohlcv_series("SBER", None, date(2025, 1, 1), date(2025, 1, 2), None)
    assert bars[0].board == "ZZZ"
