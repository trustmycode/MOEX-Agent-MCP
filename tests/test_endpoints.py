from datetime import date

from moex_iss_sdk import endpoints


def test_build_security_snapshot_endpoint():
    spec = endpoints.build_security_snapshot_endpoint("SBER", "TQBR", base_url="https://example/")
    assert spec.url.endswith("/engines/stock/markets/shares/boards/TQBR/securities/SBER.json")
    assert spec.params["iss.only"] == "marketdata,marketdata_yields"


def test_build_ohlcv_endpoint_daily_interval():
    spec = endpoints.build_ohlcv_endpoint(
        "SBER",
        "TQBR",
        date(2025, 1, 1),
        date(2025, 1, 2),
        "1d",
        base_url="https://example/",
    )
    assert spec.url.endswith("/engines/stock/markets/shares/securities/SBER/candles.json")
    assert spec.params["interval"] == "24"
    assert spec.params["from"] == "2025-01-01" and spec.params["till"] == "2025-01-02"


def test_build_index_constituents_endpoint_statistics_api():
    spec = endpoints.build_index_constituents_endpoint("IMOEX", date(2025, 1, 1), base_url="https://example/")
    assert "/statistics/engines/stock/markets/index/analytics/IMOEX.json" in spec.url
    assert spec.params["date"] == "2025-01-01"


def test_build_dividends_endpoint():
    spec = endpoints.build_dividends_endpoint("SBER", date(2025, 1, 1), date(2025, 2, 1), base_url="https://example/")
    assert spec.url.endswith("/securities/SBER/dividends.json")
    assert spec.params["from"] == "2025-01-01"
