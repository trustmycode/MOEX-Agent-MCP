---
id: ARCH-mcp-moex-iss
title: "MCP-сервер moex-iss-mcp"
type: service
layer: infrastructure
owner: @team-moex-agent
version: v1
status: current
created: 2025-12-09
updated: 2025-12-10
tags: [mcp, moex, iss, data-api]
depends_on: [ARCH-sdk-moex-iss]
referenced_by: []
---

## Контекст

`moex-iss-mcp` — кастомный MCP‑сервер поверх публичного MOEX ISS API. Он является
единственной точкой доступа агента и других внутренних сервисов (включая
`risk-analytics-mcp`) к рыночным данным:

- котировки и «снимки» инструментов;
- исторические ряды OHLCV;
- состав индексов и базовые агрегаты.

Сервер разворачивается как отдельный сервис в Cloud.ru (Docker, linux/amd64)
и взаимодействует с агентом по протоколу FastMCP (`streamable-http`) через
endpoint `/mcp`. Вся низкоуровневая работа с MOEX ISS (HTTP, rate limiting,
кэширование, обработка ошибок) делегирована общей библиотеке `moex_iss_sdk`
(см. `ARCH-sdk-moex-iss-v1.md`).

## Структура

Целевая структура пакета MCP (с учётом использования SDK):

```text
moex_iss_mcp/
  __init__.py
  main.py                 # Точка входа MCP-процесса
  config.py               # McpConfig: загрузка env и базовых настроек MCP
  server.py               # McpServer: инициализация FastMCP, регистрация tools

  models/
    __init__.py
    inputs.py             # Pydantic-модели входа для tools
    outputs.py            # Pydantic-модели выхода для tools
    errors.py             # Pydantic-модель ToolErrorModel

  tools/
    __init__.py
    security_snapshot.py  # get_security_snapshot
    ohlcv_timeseries.py   # get_ohlcv_timeseries
    index_constituents.py # get_index_constituents_metrics

  telemetry/
    __init__.py
    metrics.py            # Prometheus-метрики
    tracing.py            # OTEL-трейсинг (по возможности)
```

Ключевое отличие от ранней версии дизайна: **нет собственного HTTP‑клиента ISS
внутри MCP**. Вместо пакета `iss/*` используется единый SDK:

- `moex_iss_sdk.IssClient` — выполняет HTTP‑запросы к MOEX ISS с учётом
  `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `MOEX_ISS_TIMEOUT_SECONDS`,
  включает кэш и нормализованные исключения.
- Pydantic‑модели SDK (`SecuritySnapshot`, `OhlcvBar`, `IndexConstituent`,
  `DividendRecord` и др.) используются внутри tools как основной формат
  данных.

Переменные окружения MCP:

- `PORT=8000`;
- `MOEX_ISS_BASE_URL=https://iss.moex.com/iss/`;
- `MOEX_ISS_RATE_LIMIT_RPS`;
- `MOEX_ISS_TIMEOUT_SECONDS`;
- флаги и параметры наблюдаемости (`ENABLE_MONITORING`, `OTEL_ENDPOINT`,
  `OTEL_SERVICE_NAME`).

## Поведение

Основные инструменты MCP (см. `docs/SPEC_moex-iss-mcp.md`):

- **`get_security_snapshot`**
  - Назначение: краткий снимок инструмента (последняя цена, изменение,
    ликвидность).
  - Вход: `ticker`, опционально `board`.
  - Выход: объект `{metadata, data, metrics, error}` согласно JSON Schema
    `GetSecuritySnapshotInput/Output`.

- **`get_ohlcv_timeseries`**
  - Назначение: исторические OHLCV‑данные за период и базовые метрики
    (`total_return_pct`, `annualized_volatility`, `avg_daily_volume`).
  - Вход: `ticker`, `board`, `from_date`, `to_date`, `interval`.
  - Выход: `{metadata, data[], metrics, error}` по JSON Schema
    `GetOhlcvTimeseriesInput/Output`.

- **`get_index_constituents_metrics`**
  - Назначение: состав индекса и агрегированные показатели по бумагам.
  - Вход: `index_ticker`, `as_of_date`.
  - Выход: `{metadata, data[], metrics, error}` по JSON Schema
    `GetIndexConstituentsMetricsInput/Output`.

### Общий паттерн обработки запроса tool

1. Входной JSON валидируется Pydantic‑моделью (`inputs.py`) и при ошибках
   формируется нормализованный `error`.
2. Обработчик вызывает `moex_iss_sdk.IssClient` для получения данных ISS.
3. При необходимости, поверх данных ISS вычисляются бизнес‑метрики
   (доходность, волатильность, агрегаты по индексу) — либо с помощью утилит
   SDK, либо внутренних функций MCP.
4. Результат сериализуется в структуры `{metadata, data, metrics, error}` по
   схемам из `docs/SPEC_moex-iss-mcp.md`.
5. Любые исключения SDK (`InvalidTickerError`, `DateRangeTooLargeError`,
   `TooManyTickersError`, `IssTimeoutError`, `IssServerError`, `UnknownIssError`)
   маппятся в `error_type` (`INVALID_TICKER`, `DATE_RANGE_TOO_LARGE`,
   `TOO_MANY_TICKERS`, `ISS_TIMEOUT`, `ISS_5XX`, `UNKNOWN`).

### Наблюдаемость

- Счётчики `tool_calls_total{tool}`, `tool_errors_total{tool,error_type}`.
- Гистограммы `mcp_http_latency_seconds{tool}`.
- Endpoint `/metrics` для Prometheus и `/health` для health‑check.

## Связь со сценариями 5/7/9

`moex-iss-mcp` не реализует бизнес‑логику сценариев 5/7/9, но является
обязательным **data-provider** для `risk-analytics-mcp` и агента:

- сценарий 5 `issuer_peers_compare` — загрузка рыночных цен, индексов и,
  при необходимости, составов индексов и дивидендов для эмитента и пиров;
- сценарий 7 `portfolio_risk` — исторические ряды цен и, опционально,
  справочная информация по бумагам и индексам;
- сценарий 9 `cfo_liquidity_report` — рыночные параметры для расчёта
  стресс‑сценариев и Var_light.

Все численные расчёты (портфельный риск, ликвидность, ребалансировка) живут в
`risk-analytics-mcp`; `moex-iss-mcp` отвечает только за корректную и
устойчивую поставку данных MOEX ISS в нормализованном виде.
