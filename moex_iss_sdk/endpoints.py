"""
Хелперы для построения URL и query‑параметров эндпоинтов MOEX ISS.

Все функции возвращают `EndpointSpec` (URL + параметры), чтобы транспортный
код в `IssClient` оставался отделённым от построения путей.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Dict
from urllib.parse import urljoin

from dotenv import load_dotenv

# Подтягиваем значения из .env.sdk (если есть) и затем из стандартного .env
load_dotenv(dotenv_path=".env.sdk")
load_dotenv()

DEFAULT_BASE_URL = os.getenv("MOEX_ISS_BASE_URL", "https://iss.moex.com/iss/")
DEFAULT_ENGINE = os.getenv("MOEX_ISS_ENGINE", "stock")
DEFAULT_MARKET = os.getenv("MOEX_ISS_MARKET", "shares")
DEFAULT_BOARD = os.getenv("MOEX_ISS_DEFAULT_BOARD", "TQBR")
DEFAULT_INTERVAL = os.getenv("MOEX_ISS_DEFAULT_INTERVAL", "1d")

# Соответствие человекочитаемых интервалов SDK интервалам свечей ISS (в минутах).
INTERVAL_TO_ISS = {
    "1d": int(os.getenv("MOEX_ISS_INTERVAL_1D_MINUTES", "24")),
    "1h": int(os.getenv("MOEX_ISS_INTERVAL_1H_MINUTES", "60")),
}


@dataclass(frozen=True)
class EndpointSpec:
    """Пара URL и параметров запроса, готовых к HTTP GET."""

    url: str
    params: Dict[str, str]


def build_security_snapshot_endpoint(
    ticker: str,
    board: str = DEFAULT_BOARD,
    *,
    base_url: str = DEFAULT_BASE_URL,
    engine: str = DEFAULT_ENGINE,
    market: str = DEFAULT_MARKET,
) -> EndpointSpec:
    """Построить эндпоинт для снимка инструмента из таблицы marketdata ISS."""
    path = f"engines/{engine}/markets/{market}/boards/{board}/securities/{ticker}.json"
    url = urljoin(base_url, path)
    params = {"iss.meta": "off", "iss.only": "marketdata,marketdata_yields"}
    return EndpointSpec(url=url, params=params)


def build_ohlcv_endpoint(
    ticker: str,
    board: str,
    from_date: date,
    to_date: date,
    interval: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    engine: str = DEFAULT_ENGINE,
    market: str = DEFAULT_MARKET,
) -> EndpointSpec:
    """
    Построить эндпоинт для исторических свечей OHLCV.

    ISS использует числовые коды `interval`; соответствие задаёт `INTERVAL_TO_ISS`.
    """
    iss_interval = INTERVAL_TO_ISS.get(interval)
    if iss_interval is None:
        raise ValueError(f"Unsupported interval: {interval}")
    path = f"engines/{engine}/markets/{market}/securities/{ticker}/candles.json"
    url = urljoin(base_url, path)
    params = {
        "from": from_date.isoformat(),
        "till": to_date.isoformat(),
        "interval": str(iss_interval),
        "boardid": board,
        "iss.meta": "off",
    }
    return EndpointSpec(url=url, params=params)


def build_index_constituents_endpoint(
    index_ticker: str,
    as_of_date: date,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> EndpointSpec:
    """Построить эндпоинт для состава индекса (weights) через statistics API."""
    path = f"statistics/engines/{DEFAULT_ENGINE}/markets/index/analytics/{index_ticker}.json"
    url = urljoin(base_url, path)
    params = {"date": as_of_date.isoformat(), "iss.meta": "off"}
    return EndpointSpec(url=url, params=params)


def build_dividends_endpoint(
    ticker: str,
    from_date: date,
    to_date: date,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> EndpointSpec:
    """Построить эндпоинт для истории дивидендов бумаги."""
    path = f"securities/{ticker}/dividends.json"
    url = urljoin(base_url, path)
    params = {
        "from": from_date.isoformat(),
        "till": to_date.isoformat(),
        "iss.meta": "off",
    }
    return EndpointSpec(url=url, params=params)
