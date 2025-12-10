import pytest

from risk_analytics_mcp.models import CorrelationMatrixInput


def test_correlation_input_normalizes_tickers_and_dates():
    model = CorrelationMatrixInput(
        tickers=[" sber ", "gazp"],
        from_date="2024-01-01",
        to_date="2024-01-05",
    )
    assert model.tickers == ["SBER", "GAZP"]


def test_correlation_input_rejects_duplicates():
    with pytest.raises(ValueError):
        CorrelationMatrixInput(tickers=["SBER", "sber"], from_date="2024-01-01", to_date="2024-01-02")


def test_correlation_input_requires_two_or_more_tickers():
    with pytest.raises(ValueError):
        CorrelationMatrixInput(tickers=["SBER"], from_date="2024-01-01", to_date="2024-01-02")


def test_correlation_input_rejects_empty_ticker():
    with pytest.raises(ValueError):
        CorrelationMatrixInput(tickers=["SBER", "  "], from_date="2024-01-01", to_date="2024-01-02")


def test_correlation_input_validates_date_order():
    with pytest.raises(ValueError):
        CorrelationMatrixInput(tickers=["SBER", "GAZP"], from_date="2024-01-05", to_date="2024-01-01")
