"""
Публичная точка входа пакета `moex_iss_sdk`.

SDK предоставляет типизированный `IssClient` с набором доменных моделей и
нормализованными исключениями для работы с MOEX ISS API. Вся тяжёлая логика
сети/кэша/обработки ошибок скрыта за этим фасадом, чтобы MCP-сервисы
использовали одну реализацию.
"""

from .client import IssClient, IssClientSettings
from .exceptions import (
    DateRangeTooLargeError,
    InvalidTickerError,
    IssSdkError,
    IssServerError,
    IssTimeoutError,
    TooManyTickersError,
    UnknownIssError,
)
from .models import DividendRecord, IndexConstituent, OhlcvBar, SecuritySnapshot
from .utils import MAX_LOOKBACK_DAYS, RateLimiter

__all__ = [
    "IssClient",
    "IssClientSettings",
    "SecuritySnapshot",
    "OhlcvBar",
    "IndexConstituent",
    "DividendRecord",
    "IssSdkError",
    "InvalidTickerError",
    "DateRangeTooLargeError",
    "TooManyTickersError",
    "IssTimeoutError",
    "IssServerError",
    "UnknownIssError",
    "RateLimiter",
    "MAX_LOOKBACK_DAYS",
]
