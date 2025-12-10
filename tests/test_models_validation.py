"""
Тесты валидации входных Pydantic-моделей.
"""

import pytest
from pydantic import ValidationError

from moex_iss_mcp.models import (
    GetIndexConstituentsMetricsInput,
    GetOhlcvTimeseriesInput,
    GetSecuritySnapshotInput,
)


class TestGetSecuritySnapshotInputValidation:
    def test_ticker_trim_and_upper(self):
        model = GetSecuritySnapshotInput(ticker="  sber ", board="tqbr")
        assert model.ticker == "SBER"
        assert model.board == "TQBR"

    def test_ticker_invalid_chars(self):
        with pytest.raises(Exception):
            GetSecuritySnapshotInput(ticker="SBER!", board="TQBR")

    def test_ticker_length_limits(self):
        valid = "A" * 16
        model = GetSecuritySnapshotInput(ticker=valid, board="TQBR")
        assert model.ticker == valid
        with pytest.raises(Exception):
            GetSecuritySnapshotInput(ticker="B" * 17, board="TQBR")

    def test_empty_ticker_after_trim(self):
        with pytest.raises(Exception):
            GetSecuritySnapshotInput(ticker="   ", board="TQBR")

    def test_board_trim_and_upper(self):
        model = GetSecuritySnapshotInput(ticker="SBER", board="  tqbr ")
        assert model.board == "TQBR"

    def test_empty_board_raises(self):
        with pytest.raises(Exception):
            GetSecuritySnapshotInput(ticker="SBER", board="   ")


class TestGetOhlcvTimeseriesInputValidation:
    def test_interval_valid(self):
        model = GetOhlcvTimeseriesInput(
            ticker="SBER",
            board="TQBR",
            from_date="2024-01-01",
            to_date="2024-01-02",
            interval="1h",
        )
        assert model.interval == "1h"
        model_daily = GetOhlcvTimeseriesInput(
            ticker="SBER",
            board="TQBR",
            from_date="2024-01-01",
            to_date="2024-01-02",
            interval="1d",
        )
        assert model_daily.interval == "1d"

    def test_invalid_interval(self):
        with pytest.raises(ValidationError):
            GetOhlcvTimeseriesInput(
                ticker="SBER",
                board="TQBR",
                from_date="2024-01-01",
                to_date="2024-01-02",
                interval="5m",
            )

    def test_from_after_to(self):
        with pytest.raises(ValidationError):
            GetOhlcvTimeseriesInput(
                ticker="SBER",
                board="TQBR",
                from_date="2024-02-01",
                to_date="2024-01-01",
            )

    def test_same_dates_valid(self):
        model = GetOhlcvTimeseriesInput(
            ticker="SBER",
            board="TQBR",
            from_date="2024-01-01",
            to_date="2024-01-01",
        )
        assert str(model.from_date) == "2024-01-01"
        assert str(model.to_date) == "2024-01-01"


class TestGetIndexConstituentsMetricsInputValidation:
    def test_index_ticker_trim_upper(self):
        model = GetIndexConstituentsMetricsInput(index_ticker="  imoex ", as_of_date="2024-01-10")
        assert model.index_ticker == "IMOEX"

    def test_empty_index_ticker(self):
        with pytest.raises(Exception):
            GetIndexConstituentsMetricsInput(index_ticker=" ", as_of_date="2024-01-10")

    def test_invalid_date_format(self):
        with pytest.raises(Exception):
            GetIndexConstituentsMetricsInput(index_ticker="IMOEX", as_of_date="10-01-2024")
