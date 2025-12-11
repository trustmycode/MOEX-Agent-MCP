"""
Типизированные Pydantic‑модели для сущностей ISS.

Модели отражают поля, которые нужны MCP‑инструментам и расчётам риска, чтобы
потребителям не приходилось разбирать сырой JSON ISS вручную. Неизвестные или
дополнительные колонки ISS игнорируются для устойчивости; исходная строка может
быть сохранена в `raw` для трассировки.
"""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class IssBaseModel(BaseModel):
    """Базовая модель, игнорирующая лишние колонки ISS."""

    model_config = ConfigDict(extra="ignore")


class SecuritySnapshot(IssBaseModel):
    """Агрегированный внутридневной снимок по инструменту."""

    ticker: str = Field(description="Код бумаги, например 'SBER'.")
    board: str = Field(default="TQBR", description="Код борда, например 'TQBR'.")
    as_of: datetime = Field(description="Момент времени (UTC), когда получен снимок.")
    last_price: float = Field(description="Последняя цена сделки.")
    price_change_abs: float = Field(description="Абсолютное изменение к предыдущему закрытию.")
    price_change_pct: float = Field(description="Процентное изменение к предыдущему закрытию.")
    open_price: Optional[float] = Field(default=None, description="Цена открытия сессии.")
    high_price: Optional[float] = Field(default=None, description="Максимальная цена за сессию.")
    low_price: Optional[float] = Field(default=None, description="Минимальная цена за сессию.")
    volume: Optional[float] = Field(default=None, description="Объём торгов за сессию.")
    value: Optional[float] = Field(default=None, description="Оборот за сессию.")
    raw: Optional[dict[str, Any]] = Field(
        default=None, description="Сырая строка ISS для трассировки (опционально)."
    )


class OhlcvBar(IssBaseModel):
    """Отдельный бар OHLCV во временном ряду."""

    ts: datetime = Field(description="Метка времени бара (UTC).")
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = Field(default=None)
    value: Optional[float] = Field(default=None, description="Оборот по бару.")
    board: Optional[str] = Field(default=None, description="Борд, использованный в запросе (если известен).")
    currency: Optional[str] = Field(default=None, description="Валюта цен (опционально).")
    raw: Optional[dict[str, Any]] = Field(
        default=None, description="Сырая строка ISS для трассировки (опционально)."
    )


class IndexConstituent(IssBaseModel):
    """Элемент индекса MOEX с весом и атрибутами."""

    index_ticker: Optional[str] = Field(default=None, description="Код индекса, например 'IMOEX'.")
    ticker: str = Field(description="Код бумаги в составе индекса.")
    weight_pct: float = Field(description="Вес бумаги в индексе, проценты.")
    last_price: Optional[float] = Field(default=None)
    price_change_pct: Optional[float] = Field(default=None)
    sector: Optional[str] = Field(default=None, description="Сектор по ISS или пользовательская группировка.")
    board: Optional[str] = Field(default=None, description="Борд для бумаги, если релевантно.")
    figi: Optional[str] = Field(default=None)
    isin: Optional[str] = Field(default=None)
    raw: Optional[dict[str, Any]] = Field(
        default=None, description="Сырая строка ISS для трассировки (опционально)."
    )


class DividendRecord(IssBaseModel):
    """Запись о дивидендной (или купонной) выплате по бумаге."""

    ticker: str = Field(description="Код бумаги.")
    board: Optional[str] = Field(default=None, description="Борд, использованный в запросе, если применимо.")
    dividend: float = Field(description="Размер выплаты на акцию/паевую единицу в указанной валюте.")
    currency: Optional[str] = Field(default=None, description="Код валюты (например, RUB).")
    registry_close_date: Optional[date] = Field(
        default=None, description="Дата закрытия реестра (record date), когда фиксируются держатели."
    )
    record_date: Optional[date] = Field(default=None, description="Record date, если предоставлена ISS.")
    payment_date: Optional[date] = Field(default=None, description="Ожидаемая дата выплаты.")
    announcement_date: Optional[date] = Field(default=None, description="Дата объявления/решения.")
    yield_pct: Optional[float] = Field(default=None, description="Дивидендная доходность, %.")
    raw: Optional[dict[str, Any]] = Field(
        default=None, description="Сырая строка ISS для трассировки (опционально)."
    )


class SecurityInfo(IssBaseModel):
    """
    Статическое описание бумаги из /securities/{ticker}.json.

    Используется для расчёта капитализации и вспомогательных метрик
    (issuesize, ISIN, валюта номинала и т.п.).
    """

    ticker: str = Field(description="Код бумаги (SECID).")
    isin: Optional[str] = Field(default=None, description="ISIN код бумаги, если доступен.")
    issue_size: Optional[float] = Field(
        default=None,
        description="Объём выпуска (количество акций/паев в обращении).",
    )
    face_value: Optional[float] = Field(default=None, description="Номинальная стоимость.")
    face_unit: Optional[str] = Field(default=None, description="Валюта номинала (FACEUNIT).")
    short_name: Optional[str] = Field(default=None, description="Краткое наименование бумаги.")
    full_name: Optional[str] = Field(default=None, description="Полное наименование бумаги.")
