---
id: ARCH-mcp-moex-iss
title: "MCP-сервер moex-iss-mcp"
type: service
layer: infrastructure
owner: @team-moex-agent
version: v1
status: current
created: 2025-12-09
updated: 2025-12-09
tags: [mcp, moex, iss, data-api]
depends_on: []
referenced_by: []
---

## Контекст

`moex-iss-mcp` — кастомный MCP‑сервер поверх публичного MOEX ISS API. Он является единственной точкой доступа агента к рыночным данным: котировкам, историческим OHLCV‑рядам и составу индексов.

Сервер разворачивается как отдельный сервис в Cloud.ru (Docker, linux/amd64) и взаимодействует с агентом по протоколу FastMCP (`streamable-http`) через endpoint `/mcp`.

## Структура

Основные элементы пакета (см. C4 L4):

- `main.py` — точка входа MCP‑процесса.
- `config.py` (`McpConfig`) — загрузка конфигурации из переменных окружения (`PORT`, `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `MOEX_ISS_TIMEOUT_SECONDS`, `ENABLE_MONITORING`, `OTEL_ENDPOINT` и др.).
- `server.py` (`McpServer`) — инициализация FastMCP, регистрация инструментов, интеграция с телеметрией.
- Пакет `models` — Pydantic‑модели входа/выхода и `ToolErrorModel`.
- Пакет `tools` — обработчики бизнес‑инструментов:
  - `get_security_snapshot`;
  - `get_ohlcv_timeseries`;
  - `get_index_constituents_metrics`.
- Пакет `iss` — HTTP‑клиент `IssClient` с ретраями, тайм‑аутами и rate limiting.
- Пакет `domain` (`DomainCalculations`) — вычисление доходности, волатильности, средних объёмов и агрегатов по индексу.
- Пакет `telemetry` — экспорт метрик и трейсов (Prometheus / OTEL).

Переменные окружения:

- `PORT=8000`;
- `MOEX_ISS_BASE_URL=https://iss.moex.com/iss/`;
- `MOEX_ISS_RATE_LIMIT_RPS`;
- `MOEX_ISS_TIMEOUT_SECONDS`;
- флаги и параметры наблюдаемости (`ENABLE_MONITORING`, `OTEL_ENDPOINT`, `OTEL_SERVICE_NAME`).

## Поведение

Основные инструменты MCP:

- `get_security_snapshot` — краткий снимок инструмента (последняя цена, изменение, ликвидность).
- `get_ohlcv_timeseries` — исторические OHLCV‑данные за период и базовые метрики (`total_return_pct`, `annualized_volatility`, `avg_daily_volume`).
- `get_index_constituents_metrics` — состав индекса и агрегированные показатели (`top5_weight_pct`, `num_constituents` и др.).

Общий паттерн обработки запроса tool:

1. Pydantic‑модель входа валидирует аргументы (тикер, борд, даты, интервал).
2. `IssClient` выполняет один или несколько HTTP‑запросов к MOEX ISS с учётом лимита RPS и тайм‑аутов.
3. `DomainCalculations` считает бизнес‑метрики поверх сырых данных ISS.
4. Формируется ответ `{metadata, data, metrics, error}` согласно JSON Schema в `docs/SPEC_moex-iss-mcp.md`.
5. При ошибках (валидация, ISS, сети) `ErrorMapper` формирует нормализованный `error` с полями `error_type`, `message`, `details`.

Наблюдаемость:

- счётчики `tool_calls_total{tool}`, `tool_errors_total{tool,error_type}`;
- гистограммы `mcp_http_latency_seconds{tool}`;
- endpoint `/metrics` для Prometheus и `/health` для health‑check.

## Эволюция

### Планируемые изменения

- Расширение набора инструментов:
  - `get_multi_ohlcv_timeseries` для агрегированного сравнения нескольких тикеров за один вызов;
  - `get_portfolio_metrics` для портфельного анализа v1 (доходность, волатильность, концентрация, «красные флаги», опционально beta к индексу).
- Вынесение logic индексных маппингов и кэширования:
  - кэш `index_ticker → indexid` с временем жизни ~24 часа;
  - явные ошибки `UNKNOWN_INDEX` и `DATE_RANGE_TOO_LARGE`.
- Подготовка и поддержка JSON Schema/`tools.json` для регистрации MCP в Evolution AI Agents.

### История

- v1 (2025‑12‑09): зафиксирован целевой дизайн MCP и контракт инструментов по текущему SPEC.

