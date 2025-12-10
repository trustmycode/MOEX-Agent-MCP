---
id: ARCH-mcp-risk-analytics
title: "MCP-сервер risk-analytics-mcp"
type: service
layer: domain
owner: @team-moex-agent
version: v1
status: current
created: 2025-12-10
updated: 2025-12-10
tags: [mcp, risk, portfolio, analytics, moex]
depends_on: [ARCH-sdk-moex-iss]
referenced_by: []
---

## Контекст

`risk-analytics-mcp` — специализированный MCP-сервер для расчёта
портфельных метрик и матриц корреляций поверх данных MOEX ISS,
предоставляемых `moex_iss_sdk`.

Он разгружает агента и базовый `moex-iss-mcp`, беря на себя тяжёлую
числовую обработку: расчёт доходностей, волатильностей, вкладов в риск,
концентрационных показателей и корреляций между инструментами.

Сервер используется сценариями агента:

- `portfolio_risk` — базовый портфельный риск-анализ;
- `portfolio_risk_drill_down` — drill-down по вкладчикам риска
  (top-N бумаг).

## Структура

Целевая структура пакета:

```text
risk_analytics_mcp/
  __init__.py
  main.py                 # Точка входа FastMCP (transport="streamable-http")
  config.py               # Загрузка конфигурации и env
  server.py               # Инициализация FastMCP, регистрация tools

  models/
    __init__.py
    inputs.py             # Pydantic-модели входа для tools
    outputs.py            # Pydantic-модели выхода для tools

  tools/
    __init__.py
    compute_portfolio_risk_basic.py
    compute_correlation_matrix.py

  calculations/
    __init__.py
    returns.py            # Расчёт рядов доходностей
    portfolio_metrics.py  # Метрики портфеля и концентрации
    correlation.py        # Построение матрицы корреляций

  telemetry/
    __init__.py
    metrics.py            # Prometheus-метрики
    tracing.py            # OTEL-трейсинг (по возможности)
```

Основные зависимости:

- `moex_iss_sdk.IssClient` — источник цен и временных рядов;
- общая конфигурация окружения (лимиты по тикерам/дням, тайм-ауты,
  включение/отключение кэша);
- стек телеметрии агента/инфраструктуры (Prometheus/OTEL/Phoenix).

## Поведение

Сервер реализует как минимум два инструмента MCP.

### compute_portfolio_risk_basic

**Назначение:** базовый портфельный риск-анализ для ограниченного числа
тикеров (5–10) без тяжёлых моделей VaR/stress-test.

**Вход:**

```json
{
  "positions": [
    { "ticker": "SBER", "weight": 0.3 },
    { "ticker": "GAZP", "weight": 0.2 }
  ],
  "from_date": "YYYY-MM-DD",
  "to_date": "YYYY-MM-DD",
  "rebalance": "buy_and_hold"
}
```

**Выход (упрощённо):**

- массив `per_instrument[]` с доходностью, волатильностью и вкладом
  каждой бумаги в риск;
- объект `portfolio_metrics` с общей доходностью, упрощённой
  волатильностью и max drawdown;
- объект `concentration_metrics` (доля top-N бумаг, HHI и др.).

Под капотом инструмент:

- по каждому тикеру запрашивает временные ряды через
  `IssClient.get_ohlcv_series(...)`;
- строит ряды доходностей;
- агрегирует портфельные доходности по весам;
- считает простые статистики (волатильность, drawdown, концентрацию).

### compute_correlation_matrix

**Назначение:** оценка корреляций между инструментами для дальнейшего
портфельного анализа и drill-down сценариев.

**Вход:**

```json
{
  "tickers": ["SBER", "GAZP", "LKOH"],
  "from_date": "YYYY-MM-DD",
  "to_date": "YYYY-MM-DD"
}
```

**Выход (упрощённо):**

```json
{
  "tickers": ["SBER", "GAZP", "LKOH"],
  "matrix": [
    [1.0, 0.8, 0.6],
    [0.8, 1.0, 0.5],
    [0.6, 0.5, 1.0]
  ],
  "metadata": { ... }
}
```

Инструмент накладывает лимит `MAX_TICKERS_FOR_CORRELATION` (например,
15–20). При его превышении возвращается контролируемая ошибка с
`error_type = "TOO_MANY_TICKERS"` и подсказкой по снижению числа
тикеров.

Оба инструмента используют общий набор ошибок, маппящий исключения SDK
на стандартные коды MCP: `INVALID_TICKER`, `DATE_RANGE_TOO_LARGE`,
`TOO_MANY_TICKERS`, `ISS_TIMEOUT`, `ISS_5XX`, `UNKNOWN`.

## Эволюция

### Планируемые изменения

- Добавление advanced-метрик риска (поддержка beta к индексу,
  однодневный/многодневный VaR, сценарные stress-тесты).
- Выделение дополнительных инструментов для stress-тестов портфеля
  и факторного анализа (см. задачи `TASK-2025-043`, `TASK-2025-044`,
  `TASK-2025-072`).
- Возможная интеграция с `alerts-mcp` для формирования уведомлений при
  выходе метрик риска за пороговые значения.

### История

- v1 (2025-12-10): зафиксирован целевой дизайн MCP `risk-analytics-mcp`
  для базового портфельного анализа и корреляций; реализация планируется
  в задачах `TASK-2025-076`–`TASK-2025-079`.

