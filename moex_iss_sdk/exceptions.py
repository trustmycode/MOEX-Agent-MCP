"""
Нормализованная иерархия исключений для `moex_iss_sdk`.

SDK переводит ошибки HTTP/валидации MOEX ISS в эти исключения, чтобы слой MCP
мог маппить их в `error_type` без разбора транспортных деталей.
"""

from typing import Any, Optional


class IssSdkError(Exception):
    """Базовый класс для всех ошибок SDK."""

    error_type: str = "UNKNOWN"

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Any] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.status_code = status_code

    def __repr__(self) -> str:  # pragma: no cover - мелкий хелпер
        return f"{self.__class__.__name__}(message={self.message!r}, status_code={self.status_code!r})"


class InvalidTickerError(IssSdkError):
    """Выбрасывается, когда ISS сообщает об неизвестном/делистинговом тикере или борде."""

    error_type = "INVALID_TICKER"


class DateRangeTooLargeError(IssSdkError):
    """Выбрасывается, когда запрошенная история превышает лимит глубины."""

    error_type = "DATE_RANGE_TOO_LARGE"


class TooManyTickersError(IssSdkError):
    """Выбрасывается, если запрос с несколькими тикерами превышает поддерживаемый лимит."""

    error_type = "TOO_MANY_TICKERS"


class IssTimeoutError(IssSdkError):
    """Выбрасывается, если ISS не ответил в пределах тайм-аута."""

    error_type = "ISS_TIMEOUT"


class IssServerError(IssSdkError):
    """Выбрасывается при ответах ISS 5xx или повторяемых сбоях."""

    error_type = "ISS_5XX"


class UnknownIssError(IssSdkError):
    """Выбрасывается при неожиданных ситуациях, не попавших в другие категории."""

    error_type = "UNKNOWN"
