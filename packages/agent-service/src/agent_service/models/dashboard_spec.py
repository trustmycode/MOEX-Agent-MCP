"""
RiskDashboardSpec — модель структурированного JSON-дашборда для UI.

Определяет формат `output.dashboard`, который агент возвращает в A2A-ответе
и который используется фронтендом / AGI UI как payload backend-события
`type="risk_dashboard"`.

Соответствует спецификации из `docs/SPEC_risk_dashboard_agi_ui.md`.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MetricSeverity(str, Enum):
    """Уровень важности/риска для метрики."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertSeverity(str, Enum):
    """Уровень критичности алерта."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ChartType(str, Enum):
    """Тип графика."""

    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    HEATMAP = "heatmap"


class MetricCard(BaseModel):
    """
    Карточка ключевой метрики для отображения на дашборде.

    Attributes:
        id: Машинно-читаемый идентификатор метрики.
        title: Человекочитаемое название на русском.
        value: Отформатированное значение метрики (строка).
        change: Опциональное изменение за период (например, "+5.2%").
        status: Уровень важности/риска (normal, warning, critical).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "portfolio_total_return_pct",
                "title": "Доходность портфеля",
                "value": "11.63%",
                "change": "+2.1%",
                "status": "normal",
            }
        }
    )

    id: str = Field(..., description="Машинно-читаемый идентификатор метрики")
    title: str = Field(..., description="Человекочитаемое название на русском")
    value: str = Field(..., description="Отформатированное значение метрики")
    change: Optional[str] = Field(
        default=None, description="Изменение за период (например, '+5.2%')"
    )
    status: MetricSeverity = Field(
        default=MetricSeverity.INFO,
        description="Уровень важности/риска",
    )


class Metric(BaseModel):
    """
    Числовая метрика для layout-визуализации (v1 контракт).

    Используется фронтендом для рендеринга KPI-гридов без дополнительных
    преобразований строк.
    """

    id: str = Field(..., description="Машинно-читаемый идентификатор метрики")
    label: str = Field(..., description="Название метрики")
    value: float = Field(..., description="Числовое значение метрики")
    unit: Optional[str] = Field(default=None, description="Единица измерения")
    change: Optional[float] = Field(default=None, description="Изменение за период, %")
    severity: MetricSeverity = Field(
        default=MetricSeverity.INFO,
        description="Уровень важности/риска",
    )


class TableColumn(BaseModel):
    """
    Определение колонки таблицы.

    Attributes:
        id: Идентификатор колонки (соответствует ключу в данных).
        label: Отображаемое название колонки.
    """

    id: str = Field(..., description="Идентификатор колонки")
    label: str = Field(..., description="Отображаемое название колонки")


class TableSpec(BaseModel):
    """
    Спецификация таблицы для отображения на дашборде.

    Attributes:
        id: Идентификатор таблицы.
        title: Заголовок таблицы.
        columns: Список определений колонок.
        rows: Данные таблицы — список строк, каждая строка — список значений.
        data_ref: Ссылка на источник данных (для фронтенда).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "positions",
                "title": "Позиции портфеля",
                "columns": [
                    {"id": "ticker", "label": "Тикер"},
                    {"id": "weight_pct", "label": "Вес, %"},
                    {"id": "total_return_pct", "label": "Доходность, %"},
                ],
                "rows": [
                    ["SBER", "25.0", "15.2"],
                    ["GAZP", "20.0", "8.5"],
                ],
                "data_ref": "data.per_instrument",
            }
        }
    )

    id: str = Field(..., description="Идентификатор таблицы")
    title: str = Field(..., description="Заголовок таблицы")
    columns: list[TableColumn] = Field(
        default_factory=list, description="Список определений колонок"
    )
    rows: list[list[str]] = Field(
        default_factory=list, description="Данные таблицы — список строк"
    )
    data_ref: Optional[str] = Field(
        default=None, description="Ссылка на источник данных"
    )


class WidgetType(str, Enum):
    """Тип UI-виджета дашборда."""

    KPI_GRID = "kpi_grid"
    TABLE = "table"
    CHART = "chart"
    ALERT_LIST = "alert_list"
    TEXT = "text"


class LayoutItem(BaseModel):
    """
    Элемент layout-декларации для детерминированного рендера JSON → UI.
    """

    id: str = Field(..., description="Идентификатор элемента layout")
    type: WidgetType = Field(..., description="Тип виджета")
    title: Optional[str] = Field(default=None, description="Заголовок блока")
    description: Optional[str] = Field(default=None, description="Описание блока")
    metric_ids: list[str] = Field(
        default_factory=list,
        description="Список идентификаторов метрик для KPI-грида",
    )
    chart_id: Optional[str] = Field(default=None, description="ID графика для рендера")
    table_id: Optional[str] = Field(default=None, description="ID таблицы для рендера")
    alert_ids: list[str] = Field(
        default_factory=list,
        description="Список алертов для блока alert_list",
    )
    columns: Optional[int] = Field(
        default=None,
        description="Желаемое количество колонок в гриде",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Дополнительные опции для виджета",
    )


class ChartAxis(BaseModel):
    """
    Определение оси графика.

    Attributes:
        field: Имя поля данных для этой оси.
        label: Отображаемая подпись оси.
    """

    field: str = Field(..., description="Имя поля данных")
    label: str = Field(..., description="Отображаемая подпись оси")


class ChartSeries(BaseModel):
    """
    Серия данных для графика.

    Attributes:
        id: Идентификатор серии.
        label: Отображаемое название серии.
        data_ref: Ссылка на источник данных.
    """

    id: str = Field(..., description="Идентификатор серии")
    label: str = Field(..., description="Отображаемое название серии")
    data_ref: str = Field(..., description="Ссылка на источник данных")


class ChartSpec(BaseModel):
    """
    Спецификация графика для отображения на дашборде.

    Attributes:
        id: Идентификатор графика.
        type: Тип графика (line, bar, pie, heatmap).
        title: Заголовок графика.
        x_axis: Определение оси X.
        y_axis: Определение оси Y.
        series: Список серий данных.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "equity_curve",
                "type": "line",
                "title": "Динамика стоимости портфеля",
                "x_axis": {"field": "date", "label": "Дата"},
                "y_axis": {"field": "value", "label": "Стоимость, млн ₽"},
                "series": [
                    {
                        "id": "portfolio",
                        "label": "Портфель",
                        "data_ref": "time_series.portfolio_value",
                    }
                ],
            }
        }
    )

    id: str = Field(..., description="Идентификатор графика")
    type: ChartType = Field(..., description="Тип графика")
    title: str = Field(..., description="Заголовок графика")
    x_axis: Optional[ChartAxis] = Field(default=None, description="Определение оси X")
    y_axis: Optional[ChartAxis] = Field(default=None, description="Определение оси Y")
    series: list[ChartSeries] = Field(
        default_factory=list, description="Список серий данных"
    )


class Alert(BaseModel):
    """
    Алерт/предупреждение для отображения на дашборде.

    Alerts отображают ключевые «красные флаги» портфеля:
    - превышение лимитов концентрации
    - VaR близок к лимиту
    - сильные стресс-потери

    Attributes:
        id: Идентификатор алерта.
        severity: Уровень критичности (info, warning, critical).
        message: Текст сообщения на русском.
        related_ids: Список связанных идентификаторов (метрики, тикеры).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "issuer_concentration",
                "severity": "warning",
                "message": "Концентрация по эмитенту SBER превышает лимит 15%.",
                "related_ids": ["ticker:SBER", "metric:top1_weight_pct"],
            }
        }
    )

    id: str = Field(..., description="Идентификатор алерта")
    severity: AlertSeverity = Field(..., description="Уровень критичности")
    message: str = Field(..., description="Текст сообщения на русском")
    related_ids: list[str] = Field(
        default_factory=list, description="Список связанных идентификаторов"
    )


class DashboardMetadata(BaseModel):
    """
    Метаданные дашборда.

    Attributes:
        as_of: Момент времени, на который актуальны метрики.
        scenario_type: Тип сценария (portfolio_risk_basic, index_risk_scan и т.п.).
        base_currency: Базовая валюта портфеля.
        portfolio_id: Опциональный идентификатор портфеля.
    """

    as_of: datetime = Field(
        default_factory=datetime.utcnow,
        description="Момент времени актуальности метрик",
    )
    scenario_type: str = Field(
        default="portfolio_risk_basic",
        description="Тип сценария",
    )
    base_currency: str = Field(default="RUB", description="Базовая валюта")
    portfolio_id: Optional[str] = Field(
        default=None, description="Идентификатор портфеля"
    )


class RiskDashboardSpec(BaseModel):
    """
    Полная спецификация Risk Dashboard для UI/AGI UI.

    Это доменно-ориентированный профиль, оптимизированный под сценарии
    портфельного риска (7) и связанные сценарии (5/9).

    Используется как `output.dashboard` в A2A-ответе агента и как
    payload backend-события `type="risk_dashboard"` для AGI UI.

    Attributes:
        metadata: Метаданные дашборда (время, сценарий, валюта).
        metric_cards: Список карточек ключевых метрик.
        tables: Список таблиц (позиции, стресс-сценарии и т.п.).
        charts: Список графиков (equity curve, веса и т.п.).
        alerts: Список алертов/предупреждений.
        raw_data: Опциональные сырые данные для графиков (time_series и т.п.).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metadata": {
                    "as_of": "2025-12-11T10:00:00Z",
                    "scenario_type": "portfolio_risk_basic",
                    "base_currency": "RUB",
                    "portfolio_id": "demo-portfolio-001",
                },
                "metric_cards": [
                    {
                        "id": "portfolio_total_return_pct",
                        "title": "Доходность портфеля за период",
                        "value": "11.63%",
                        "status": "info",
                    }
                ],
                "tables": [],
                "charts": [],
                "alerts": [],
            }
        }
    )

    version: str = Field(
        default="1.0",
        description="Версия контракта RiskDashboardSpec (layout v1.0).",
    )
    metadata: DashboardMetadata = Field(
        default_factory=DashboardMetadata,
        description="Метаданные дашборда",
    )
    # Новые поля v1: декларативные метрики и layout
    metrics: list[Metric] = Field(
        default_factory=list,
        description="Структурированные метрики (KPI) для AG-UI layout",
    )
    layout: list[LayoutItem] = Field(
        default_factory=list,
        description="Декларация расположения виджетов для рендера",
    )
    metric_cards: list[MetricCard] = Field(
        default_factory=list,
        description="Список карточек ключевых метрик",
    )
    tables: list[TableSpec] = Field(
        default_factory=list,
        description="Список таблиц",
    )
    charts: list[ChartSpec] = Field(
        default_factory=list,
        description="Список графиков",
    )
    alerts: list[Alert] = Field(
        default_factory=list,
        description="Список алертов/предупреждений",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Сырые данные (tables/charts) для data_ref ссылок",
    )
    time_series: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict,
        description="Временные ряды для графиков",
    )
    raw_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Сырые данные для графиков (time_series и т.п.)",
    )

    def add_metric_card(
        self,
        id: str,
        title: str,
        value: float | str,
        unit: str = "",
        status: MetricSeverity = MetricSeverity.INFO,
        change: Optional[str] = None,
    ) -> MetricCard:
        """
        Добавить карточку метрики на дашборд.

        Args:
            id: Идентификатор метрики.
            title: Название метрики.
            value: Значение (число или строка).
            unit: Единица измерения (%, RUB и т.п.).
            status: Уровень важности.
            change: Изменение за период.

        Returns:
            Созданная MetricCard.
        """
        numeric_value: Optional[float] = None
        if isinstance(value, (int, float)):
            numeric_value = float(value)
            formatted_value = f"{numeric_value:.2f}{unit}"
        else:
            formatted_value = f"{value}{unit}"

        card = MetricCard(
            id=id,
            title=title,
            value=formatted_value,
            change=change,
            status=status,
        )
        self.metric_cards.append(card)

        # Дублируем в metrics (v1 контракт) при наличии числового значения
        if numeric_value is not None:
            try:
                numeric_change = float(change) if change is not None else None
            except (TypeError, ValueError):
                numeric_change = None

            self.metrics.append(
                Metric(
                    id=id,
                    label=title,
                    value=numeric_value,
                    unit=unit or None,
                    change=numeric_change,
                    severity=status,
                )
            )

        return card

    def add_alert(
        self,
        id: str,
        severity: AlertSeverity,
        message: str,
        related_ids: Optional[list[str]] = None,
    ) -> Alert:
        """
        Добавить алерт на дашборд.

        Args:
            id: Идентификатор алерта.
            severity: Уровень критичности.
            message: Текст сообщения.
            related_ids: Связанные идентификаторы.

        Returns:
            Созданный Alert.
        """
        alert = Alert(
            id=id,
            severity=severity,
            message=message,
            related_ids=related_ids or [],
        )
        self.alerts.append(alert)
        return alert

    def add_table(
        self,
        id: str,
        title: str,
        columns: list[tuple[str, str]],
        rows: list[list[str]],
        data_ref: Optional[str] = None,
    ) -> TableSpec:
        """
        Добавить таблицу на дашборд.

        Args:
            id: Идентификатор таблицы.
            title: Заголовок таблицы.
            columns: Список кортежей (id, label) для колонок.
            rows: Данные таблицы.
            data_ref: Ссылка на источник данных.

        Returns:
            Созданная TableSpec.
        """
        table = TableSpec(
            id=id,
            title=title,
            columns=[TableColumn(id=col_id, label=label) for col_id, label in columns],
            rows=rows,
            data_ref=data_ref,
        )
        self.tables.append(table)
        return table

