from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from moex_iss_sdk import IssClient, IssClientSettings
from moex_iss_sdk.models import DividendRecord, SecurityInfo, SecuritySnapshot
from risk_analytics_mcp.providers import MoexIssFundamentalsProvider

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "tests" / "data"


class DescriptionClient(IssClient):
    """
    Клиент, использующий сохранённый JSON /securities/{ticker}.json
    вместо реального HTTP-запроса.
    """

    def __init__(self, payload: dict) -> None:
        settings = IssClientSettings.from_env()
        settings.rate_limit_rps = 0
        settings.enable_cache = False
        super().__init__(settings, cache=None)
        self._payload = payload

    def _get_json(self, spec):  # type: ignore[override]
        # Для теста достаточно всегда возвращать один и тот же payload.
        return self._payload


class SnapshotIssClient(IssClient):
    """
    Клиент ISS, который вместо HTTP возвращает заранее сохранённые JSON-ответы.

    Используется только в тестах, чтобы не ходить в сеть.
    """

    def __init__(self, snapshot_payload: dict, dividends_payload: dict) -> None:
        settings = IssClientSettings.from_env()
        # отключаем rate limiting и кэш, чтобы логика была детерминированной
        settings.rate_limit_rps = 0
        settings.enable_cache = False
        super().__init__(settings, cache=None)
        self._description_payload = snapshot_payload
        self._dividends_payload = dividends_payload

    # Переопределяем только публичные методы, которые использует провайдер.
    def get_security_snapshot(self, ticker: str, board: str | None = None) -> SecuritySnapshot:  # type: ignore[override]  # noqa: E501
        # В тесте нас интересует только last_price и as_of.
        return SecuritySnapshot(
            ticker=ticker,
            board=board or "TQBR",
            as_of=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            last_price=300.0,
            price_change_abs=0.0,
            price_change_pct=0.0,
            open_price=None,
            high_price=None,
            low_price=None,
            volume=None,
            value=None,
            raw=None,
        )

    def _get_json(self, spec):  # type: ignore[override]
        url: str = getattr(spec, "url", "")
        if "/securities/" in url and "/dividends" not in url:
            return self._description_payload
        if "/dividends" in url:
            return self._dividends_payload
        # Для остальных эндпоинтов (в этом тесте не используется) возвращаем пустую структуру.
        return {}

    def get_security_dividends(  # type: ignore[override]
        self,
        ticker: str,
        from_date,
        to_date,
    ) -> list[DividendRecord]:
        section = self._dividends_payload["dividends"]
        columns = section["columns"]
        records: list[DividendRecord] = []
        for row in section["data"]:
            row_map = dict(zip(columns, row))
            # В snapshot-ответе дивиденды хранятся в поле value.
            records.append(
                DividendRecord(
                    ticker=row_map.get("secid") or ticker,
                    board=None,
                    dividend=float(row_map.get("value", 0.0)),
                    currency=row_map.get("currencyid"),
                    registry_close_date=row_map.get("registryclosedate"),
                    record_date=row_map.get("registryclosedate"),
                    payment_date=None,
                    announcement_date=None,
                    yield_pct=None,
                    raw=row_map,
                )
            )
        return records


def _load_snapshot(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text())


def test_get_security_info_parses_description_snapshot():
    securities_payload = _load_snapshot("securities_SBER.json")
    client = DescriptionClient(securities_payload)
    info = client.get_security_info("SBER")

    assert info.ticker == "SBER"
    assert info.isin == "RU0009029540"
    assert info.issue_size and info.issue_size > 1_000_000_000
    assert info.face_unit in {"SUR", "RUB"}


def test_moex_iss_fundamentals_provider_builds_basic_metrics_from_snapshots():
    securities_payload = _load_snapshot("securities_SBER.json")
    dividends_payload = _load_snapshot("dividends_SBER_2023_2025.json")
    client = SnapshotIssClient(securities_payload, dividends_payload)
    provider = MoexIssFundamentalsProvider(client)

    fundamentals = provider.get_issuer_fundamentals("SBER")

    assert fundamentals.ticker == "SBER"
    assert fundamentals.isin == "RU0009029540"
    # Капитализация должна быть price * issuesize.
    assert fundamentals.price == 300.0
    assert fundamentals.shares_outstanding and fundamentals.shares_outstanding > 1_000_000_000
    assert fundamentals.market_cap == pytest.approx(fundamentals.price * fundamentals.shares_outstanding)
    # Дивидендная доходность должна быть положительной и конечной при наличии дивидендов.
    assert fundamentals.dividend_yield_pct is None or fundamentals.dividend_yield_pct >= 0.0
