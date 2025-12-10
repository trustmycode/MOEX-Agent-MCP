import os
from datetime import date, timedelta

import pytest

from moex_iss_sdk import IssClient, IssClientSettings

pytestmark = pytest.mark.iss_live

run_live = pytest.mark.skipif(os.getenv("RUN_ISS_LIVE") != "1", reason="RUN_ISS_LIVE!=1")


@run_live
def test_live_snapshot_sber():
    client = IssClient(IssClientSettings())
    snap = client.get_security_snapshot("SBER", "TQBR")
    assert snap.ticker == "SBER"
    assert snap.last_price > 0


@run_live
def test_live_ohlcv_sber_daily():
    client = IssClient(IssClientSettings())
    to_d = date.today() - timedelta(days=1)
    from_d = to_d - timedelta(days=10)
    bars = client.get_ohlcv_series("SBER", "TQBR", from_d, to_d, "1d")
    assert len(bars) > 0


@run_live
def test_live_index_constituents_imoex():
    client = IssClient(IssClientSettings())
    as_of = date.today() - timedelta(days=3)
    members = client.get_index_constituents("IMOEX", as_of)
    assert len(members) > 0
    assert any(m.weight_pct > 0 for m in members)


@run_live
def test_live_dividends_sber():
    client = IssClient(IssClientSettings())
    to_d = date.today()
    from_d = to_d - timedelta(days=730)
    divs = client.get_security_dividends("SBER", from_d, to_d)
    assert len(divs) >= 0  # допускаем 0 записей, главное — отсутствие ошибок
