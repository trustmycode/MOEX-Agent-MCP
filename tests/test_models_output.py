"""
Тесты методов success/from_error для выходных моделей.
"""

from datetime import datetime, timezone

from moex_iss_mcp.error_mapper import ToolErrorModel
from moex_iss_mcp.models import (
    GetIndexConstituentsMetricsOutput,
    GetOhlcvTimeseriesOutput,
    GetSecuritySnapshotOutput,
)


def test_security_snapshot_output_success_optional_fields():
    as_of = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    output = GetSecuritySnapshotOutput.success(
        ticker="SBER",
        board="TQBR",
        as_of=as_of,
        last_price=100.0,
        price_change_abs=1.0,
        price_change_pct=1.0,
        open_price=None,
        high_price=None,
        low_price=None,
        volume=None,
        value=None,
        intraday_volatility_estimate=None,
    )
    assert output.metadata["as_of"] == as_of.isoformat()
    assert "open_price" not in output.data
    assert output.metrics is None
    assert output.error is None


def test_security_snapshot_output_error():
    err = ToolErrorModel(error_type="INVALID_TICKER", message="bad")
    output = GetSecuritySnapshotOutput.from_error(err)
    assert output.error.error_type == "INVALID_TICKER"
    assert output.metadata == {}
    assert output.data == {}


def test_ohlcv_timeseries_output_success_and_metrics_filter():
    output = GetOhlcvTimeseriesOutput.success(
        ticker="SBER",
        board="TQBR",
        interval="1d",
        from_date=datetime(2024, 1, 1).date(),
        to_date=datetime(2024, 1, 2).date(),
        bars=[{"ts": "2024-01-01T00:00:00", "open": 1, "high": 2, "low": 1, "close": 2}],
        total_return_pct=None,
        annualized_volatility=10.0,
        avg_daily_volume=None,
    )
    assert output.metadata["from_date"] == "2024-01-01"
    assert output.metadata["to_date"] == "2024-01-02"
    assert output.metrics == {"annualized_volatility": 10.0}
    assert output.error is None


def test_ohlcv_timeseries_output_error():
    err = ToolErrorModel(error_type="DATE_RANGE_TOO_LARGE", message="too wide")
    output = GetOhlcvTimeseriesOutput.from_error(err)
    assert output.data == []
    assert output.error.error_type == "DATE_RANGE_TOO_LARGE"


def test_index_constituents_metrics_output_success_empty_list():
    output = GetIndexConstituentsMetricsOutput.success(
        index_ticker="IMOEX",
        as_of_date=datetime(2024, 1, 10).date(),
        data=[],
        top5_weight_pct=None,
        num_constituents=0,
    )
    assert output.metadata["index_ticker"] == "IMOEX"
    assert output.metrics["num_constituents"] == 0
    assert "top5_weight_pct" not in output.metrics
    assert output.error is None


def test_index_constituents_metrics_output_error():
    err = ToolErrorModel(error_type="UNKNOWN_INDEX", message="no index")
    output = GetIndexConstituentsMetricsOutput.from_error(err)
    assert output.data == []
    assert output.error.error_type == "UNKNOWN_INDEX"
