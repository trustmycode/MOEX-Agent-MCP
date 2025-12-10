from datetime import date

import pytest

from risk_analytics_mcp.calculations.correlation import InsufficientDataError, compute_correlation_matrix


def test_correlation_matrix_symmetry_and_known_values():
    returns_by_ticker = {
        "AAA": [
            (date(2024, 1, 1), 0.01),
            (date(2024, 1, 2), 0.02),
            (date(2024, 1, 3), -0.01),
        ],
        "BBB": [
            (date(2024, 1, 1), 0.02),
            (date(2024, 1, 2), 0.04),
            (date(2024, 1, 3), -0.02),
        ],
        "CCC": [
            (date(2024, 1, 1), -0.01),
            (date(2024, 1, 2), -0.02),
            (date(2024, 1, 3), 0.01),
        ],
    }

    matrix, metadata = compute_correlation_matrix(["AAA", "BBB", "CCC"], returns_by_ticker)

    assert metadata["method"] == "pearson"
    assert metadata["num_observations"] == 3

    assert len(matrix) == 3 and all(len(row) == 3 for row in matrix)
    assert matrix[0][0] == pytest.approx(1.0)
    assert matrix[1][1] == pytest.approx(1.0)
    assert matrix[2][2] == pytest.approx(1.0)
    assert matrix[0][1] == pytest.approx(matrix[1][0], rel=1e-6)
    assert matrix[0][1] == pytest.approx(1.0, rel=1e-6)
    assert matrix[0][2] == pytest.approx(matrix[2][0], rel=1e-6)
    assert matrix[0][2] == pytest.approx(-1.0, rel=1e-6)


def test_correlation_matrix_insufficient_data():
    returns_by_ticker = {
        "AAA": [(date(2024, 1, 1), 0.01)],
        "BBB": [(date(2024, 1, 1), 0.02)],
    }

    with pytest.raises(InsufficientDataError):
        compute_correlation_matrix(["AAA", "BBB"], returns_by_ticker)


def test_correlation_matrix_requires_overlapping_dates():
    returns_by_ticker = {
        "AAA": [(date(2024, 1, 1), 0.01), (date(2024, 1, 2), 0.02)],
        "BBB": [(date(2024, 1, 3), 0.01), (date(2024, 1, 4), 0.02)],
    }

    with pytest.raises(InsufficientDataError):
        compute_correlation_matrix(["AAA", "BBB"], returns_by_ticker)


def test_correlation_matrix_rejects_zero_variance():
    returns_by_ticker = {
        "AAA": [(date(2024, 1, 1), 0.0), (date(2024, 1, 2), 0.0), (date(2024, 1, 3), 0.0)],
        "BBB": [(date(2024, 1, 1), 0.01), (date(2024, 1, 2), -0.01), (date(2024, 1, 3), 0.02)],
    }

    with pytest.raises(InsufficientDataError):
        compute_correlation_matrix(["AAA", "BBB"], returns_by_ticker)


def test_correlation_matrix_metadata_contains_sorted_dates():
    returns_by_ticker = {
        "AAA": [(date(2024, 1, 2), 0.01), (date(2024, 1, 1), -0.01), (date(2024, 1, 3), 0.0)],
        "BBB": [(date(2024, 1, 2), 0.02), (date(2024, 1, 1), -0.02), (date(2024, 1, 3), 0.01)],
    }

    _, metadata = compute_correlation_matrix(["AAA", "BBB"], returns_by_ticker)
    assert metadata["dates"] == ["2024-01-01", "2024-01-02", "2024-01-03"]
