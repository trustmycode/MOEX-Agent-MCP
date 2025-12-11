"""
Pydantic-модели для входных и выходных данных MCP-инструментов.

Модели соответствуют JSON Schema в SPEC_moex-iss-mcp.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from moex_iss_sdk.error_mapper import ToolErrorModel


class GetSecuritySnapshotInput(BaseModel):
    """
    Входная модель для инструмента get_security_snapshot.

    Соответствует JSON Schema GetSecuritySnapshotInput из SPEC.
    """

    ticker: str = Field(
        min_length=1,
        max_length=16,
        description="Security ticker, e.g. 'SBER'.",
    )
    board: Optional[str] = Field(
        default="TQBR",
        min_length=1,
        max_length=16,
        description="MOEX board, e.g. 'TQBR'.",
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        """Валидация тикера: должен быть непустой и содержать только допустимые символы."""
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        # Убираем пробелы
        v = v.strip().upper()
        # Проверяем, что тикер содержит только буквы, цифры и некоторые спецсимволы
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(f"Ticker contains invalid characters: {v}")
        return v

    @field_validator("board")
    @classmethod
    def validate_board(cls, v: Optional[str]) -> Optional[str]:
        """Валидация борда: должен быть непустым, если передан."""
        if v is not None:
            v = v.strip().upper()
            if not v:
                raise ValueError("Board cannot be empty if provided")
        return v


class GetOhlcvTimeseriesInput(BaseModel):
    """
    Входная модель для инструмента get_ohlcv_timeseries.

    Соответствует JSON Schema GetOhlcvTimeseriesInput из SPEC.
    """

    ticker: str = Field(
        min_length=1,
        max_length=16,
        description="Security ticker, e.g. 'SBER'.",
    )
    board: Optional[str] = Field(
        default="TQBR",
        min_length=1,
        max_length=16,
        description="MOEX board, e.g. 'TQBR'.",
    )
    from_date: date = Field(description="Start date, inclusive, in ISO format (YYYY-MM-DD).")
    to_date: date = Field(description="End date, inclusive, in ISO format (YYYY-MM-DD).")
    interval: Literal["1d", "1h"] = Field(
        default="1d",
        description="Aggregation interval: 1d (daily) or 1h (hourly).",
    )

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Ticker cannot be empty")
        v = v.strip().upper()
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(f"Ticker contains invalid characters: {v}")
        return v

    @field_validator("board")
    @classmethod
    def validate_board(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip().upper()
            if not v:
                raise ValueError("Board cannot be empty if provided")
        return v

    @field_validator("to_date")
    @classmethod
    def validate_date_range(cls, to_date_value: date, info) -> date:
        from_date_value = info.data.get("from_date")
        if from_date_value and to_date_value < from_date_value:
            raise ValueError("to_date must be greater than or equal to from_date")
        return to_date_value


class GetSecuritySnapshotOutput(BaseModel):
    """
    Выходная модель для инструмента get_security_snapshot.

    Соответствует JSON Schema GetSecuritySnapshotOutput из SPEC.
    """

    metadata: dict = Field(
        description="Метаданные запроса: source, ticker, board, as_of"
    )
    data: dict = Field(
        description="Данные снимка: last_price, price_change_abs, price_change_pct, и т.д."
    )
    metrics: Optional[dict] = Field(
        default=None,
        description="Вычисленные метрики (например, intraday_volatility_estimate)",
    )
    error: Optional[ToolErrorModel] = Field(
        default=None,
        description="Информация об ошибке, если запрос завершился с ошибкой",
    )

    @classmethod
    def success(
        cls,
        ticker: str,
        board: str,
        as_of: datetime,
        last_price: float,
        price_change_abs: float,
        price_change_pct: float,
        open_price: Optional[float] = None,
        high_price: Optional[float] = None,
        low_price: Optional[float] = None,
        volume: Optional[float] = None,
        value: Optional[float] = None,
        intraday_volatility_estimate: Optional[float] = None,
    ) -> "GetSecuritySnapshotOutput":
        """
        Создать успешный ответ get_security_snapshot.

        Args:
            ticker: Тикер инструмента.
            board: Борд MOEX.
            as_of: Время получения снимка (UTC).
            last_price: Последняя цена.
            price_change_abs: Абсолютное изменение цены.
            price_change_pct: Процентное изменение цены.
            open_price: Цена открытия (опционально).
            high_price: Максимальная цена (опционально).
            low_price: Минимальная цена (опционально).
            volume: Объём торгов (опционально).
            value: Оборот (опционально).
            intraday_volatility_estimate: Оценка внутридневной волатильности (опционально).

        Returns:
            GetSecuritySnapshotOutput с заполненными полями.
        """
        metadata = {
            "source": "moex-iss",
            "ticker": ticker,
            "board": board,
            "as_of": as_of.isoformat(),
        }

        data = {
            "last_price": last_price,
            "price_change_abs": price_change_abs,
            "price_change_pct": price_change_pct,
        }

        # Добавляем опциональные поля, если они есть
        if open_price is not None:
            data["open_price"] = open_price
        if high_price is not None:
            data["high_price"] = high_price
        if low_price is not None:
            data["low_price"] = low_price
        if volume is not None:
            data["volume"] = volume
        if value is not None:
            data["value"] = value

        metrics = None
        if intraday_volatility_estimate is not None:
            metrics = {"intraday_volatility_estimate": intraday_volatility_estimate}

        return cls(
            metadata=metadata,
            data=data,
            metrics=metrics,
            error=None,
        )

    @classmethod
    def from_error(cls, error: ToolErrorModel) -> "GetSecuritySnapshotOutput":
        """
        Создать ответ с ошибкой для get_security_snapshot.

        Args:
            error: Модель ошибки.

        Returns:
            GetSecuritySnapshotOutput с заполненным полем error.
        """
        return cls(
            metadata={},
            data={},
            metrics=None,
            error=error,
        )


class GetOhlcvTimeseriesOutput(BaseModel):
    """
    Выходная модель для инструмента get_ohlcv_timeseries.

    Соответствует JSON Schema GetOhlcvTimeseriesOutput из SPEC.
    """

    metadata: dict = Field(description="Метаданные запроса: source, ticker, board, interval, from_date, to_date.")
    data: list[dict] = Field(description="Список баров OHLCV.")
    metrics: Optional[dict] = Field(default=None, description="Вычисленные метрики (доходность, волатильность).")
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке, если запрос завершился с ошибкой.")

    @classmethod
    def success(
        cls,
        *,
        ticker: str,
        board: str,
        interval: str,
        from_date: date,
        to_date: date,
        bars: list[dict],
        total_return_pct: Optional[float],
        annualized_volatility: Optional[float],
        avg_daily_volume: Optional[float],
    ) -> "GetOhlcvTimeseriesOutput":
        metadata = {
            "source": "moex-iss",
            "ticker": ticker,
            "board": board,
            "interval": interval,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        }

        metrics = {}
        if total_return_pct is not None:
            metrics["total_return_pct"] = total_return_pct
        if annualized_volatility is not None:
            metrics["annualized_volatility"] = annualized_volatility
        if avg_daily_volume is not None:
            metrics["avg_daily_volume"] = avg_daily_volume
        if not metrics:
            metrics = None

        return cls(
            metadata=metadata,
            data=bars,
            metrics=metrics,
            error=None,
        )

    @classmethod
    def from_error(cls, error: ToolErrorModel) -> "GetOhlcvTimeseriesOutput":
        return cls(metadata={}, data=[], metrics=None, error=error)


class GetIndexConstituentsMetricsInput(BaseModel):
    """
    Входная модель для инструмента get_index_constituents_metrics.

    Соответствует JSON Schema GetIndexConstituentsMetricsInput из SPEC.
    """

    index_ticker: str = Field(description="Index ticker.", min_length=1, max_length=16)
    as_of_date: date = Field(description="Date for which index composition is requested.")

    @field_validator("index_ticker")
    @classmethod
    def validate_index_ticker(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("index_ticker cannot be empty")
        return v.strip().upper()


class GetIndexConstituentsMetricsOutput(BaseModel):
    """
    Выходная модель для инструмента get_index_constituents_metrics.

    Соответствует JSON Schema GetIndexConstituentsMetricsOutput из SPEC.
    """

    metadata: dict = Field(description="Метаданные запроса: source, index_ticker, as_of_date.")
    data: list[dict] = Field(description="Состав индекса и показатели по бумагам.")
    metrics: Optional[dict] = Field(default=None, description="Агрегированные показатели по индексу.")
    error: Optional[ToolErrorModel] = Field(default=None, description="Информация об ошибке, если запрос завершился с ошибкой.")

    @classmethod
    def success(
        cls,
        *,
        index_ticker: str,
        as_of_date: date,
        data: list[dict],
        top5_weight_pct: Optional[float],
        num_constituents: int,
    ) -> "GetIndexConstituentsMetricsOutput":
        metadata = {
            "source": "moex-iss",
            "index_ticker": index_ticker,
            "as_of_date": as_of_date.isoformat(),
        }
        metrics = {}
        if top5_weight_pct is not None:
            metrics["top5_weight_pct"] = top5_weight_pct
        if num_constituents is not None:
            metrics["num_constituents"] = num_constituents
        if not metrics:
            metrics = None

        return cls(metadata=metadata, data=data, metrics=metrics, error=None)

    @classmethod
    def from_error(cls, error: ToolErrorModel) -> "GetIndexConstituentsMetricsOutput":
        return cls(metadata={}, data=[], metrics=None, error=error)


# Пересборка моделей для корректной работы с from __future__ import annotations
GetSecuritySnapshotInput.model_rebuild()
GetSecuritySnapshotOutput.model_rebuild()
GetOhlcvTimeseriesInput.model_rebuild()
GetOhlcvTimeseriesOutput.model_rebuild()
GetIndexConstituentsMetricsInput.model_rebuild()
GetIndexConstituentsMetricsOutput.model_rebuild()

