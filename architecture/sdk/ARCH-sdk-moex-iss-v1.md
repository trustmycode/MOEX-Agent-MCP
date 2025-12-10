---
id: ARCH-sdk-moex-iss
title: "Пакет moex_iss_sdk — единый клиент MOEX ISS"
type: library
layer: infrastructure
owner: @team-moex-agent
version: v1
status: current
created: 2025-12-10
updated: 2025-12-10
tags: [moex, iss, sdk, python]
depends_on: []
referenced_by: [ARCH-mcp-moex-iss, ARCH-mcp-risk-analytics]
---

## Контекст

`moex_iss_sdk` — общий Python‑пакет для работы с публичным MOEX ISS API,
который используется всеми внутренними MCP‑серверами проекта (в первую
очередь `moex-iss-mcp` и `risk-analytics-mcp`).

Основные цели SDK (см. задачи `TASK-2025-073`–`TASK-2025-075` и
`architecture/mcp/*`):

- устранить дублирование HTTP‑клиентов ISS в разных MCP;
- зафиксировать единый, типизированный интерфейс `IssClient`;
- инкапсулировать детали rate limiting, ретраев, тайм‑аутов и кэширования;
- дать общие Pydantic‑модели для рыночных сущностей (OHLCV, дивиденды,
  компоненты индексов и т.п.), чтобы бизнес‑логика и MCP‑слой работали с
  одними и теми же структурами данных;
- нормализовать ошибки ISS на уровне SDK, чтобы MCP‑слой мог маппить их в
  `error_type` без знания HTTP‑деталей.

## Структура

Пакет имеет следующую целевую структуру:

```text
moex_iss_sdk/
  __init__.py
  client.py          # IssClient: HTTP, rate limiting, retries, кэш
  models.py          # Pydantic-модели (SecuritySnapshot, OhlcvBar, IndexConstituent, DividendRecord и др.)
  endpoints.py       # Константы и хелперы по ISS-эндпоинтам
  exceptions.py      # Специализированные исключения (InvalidTickerError, DateRangeTooLargeError, TooManyTickersError, IssTimeoutError, IssServerError, UnknownIssError)
  utils.py           # Вспомогательные функции (нормализация параметров, проверка диапазонов дат, парсинг ответов)
```

Ключевые элементы:

- **`IssClient` (client.py)** — единая точка входа для всех запросов к
  MOEX ISS; конфигурируется через объект настроек или переменные окружения
  (`MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `MOEX_ISS_TIMEOUT_SECONDS`,
  `ENABLE_CACHE`, `CACHE_TTL_SECONDS`).
- **Модели (models.py)**:
  - `SecuritySnapshot` — агрегированный снимок инструмента;
  - `OhlcvBar` — бар OHLCV для временного ряда;
  - `IndexConstituent` — элемент индекса с весом и атрибутами;
  - `DividendRecord` — запись о дивидендной выплате.
- **Исключения (exceptions.py)** — нормализованные ошибки уровня SDK
  (`InvalidTickerError`, `DateRangeTooLargeError`, `TooManyTickersError`,
  `IssTimeoutError`, `IssServerError`, `UnknownIssError`), которые далее
  мапятся в `error_type` на уровне MCP (`INVALID_TICKER`,
  `DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`, `ISS_TIMEOUT`, `ISS_5XX`,
  `UNKNOWN`).
- **Утилиты (utils.py)** — функции для нормализации параметров, проверки
  диапазонов дат, разбора ответов ISS и построения удобных DTO.

## Поведение

Основной публичный класс SDK — `IssClient`. Он предоставляет, как минимум,
следующие методы (см. `TASK-2025-073`):

- `get_security_snapshot(ticker, board) -> SecuritySnapshot`;
- `get_ohlcv_series(ticker, board, from_date, to_date, interval) -> list[OhlcvBar]`;
- `get_index_constituents(index_ticker, as_of_date) -> list[IndexConstituent]`;
- `get_security_dividends(ticker, from_date, to_date) -> list[DividendRecord]`.

Все вызовы проходят через общий HTTP‑слой с:

- ограничением RPS по `MOEX_ISS_RATE_LIMIT_RPS`;
- тайм‑аутами `MOEX_ISS_TIMEOUT_SECONDS`;
- ретраями по сетевым/5xx‑ошибкам с backoff;
- опциональным LRU‑кэшем с TTL для типовых запросов (`ENABLE_CACHE`,
  `CACHE_TTL_SECONDS`), реализуемым в рамках `TASK-2025-075`.

SDK является **единственным** источником правды о низкоуровневом поведении
MOEX ISS для внутренних сервисов:

- `moex-iss-mcp` использует `IssClient` и модели SDK для реализации
  инструментов `get_security_snapshot`, `get_ohlcv_timeseries`,
  `get_index_constituents_metrics` (см. `docs/SPEC_moex-iss-mcp.md`).
- `risk-analytics-mcp` использует `IssClient` для загрузки OHLCV‑рядов и
  справочных данных в расчётах `analyze_portfolio_risk`,
  `suggest_rebalance`, `build_cfo_liquidity_report` и вспомогательных
  инструментов (`compute_correlation_matrix` и др.).

## Связь с SPEC и REQUIREMENTS

- SPEC MCP `moex-iss-mcp` (`docs/SPEC_moex-iss-mcp.md`) определяет форматы
  входа/выхода для high‑level инструментов MCP и опирается на Pydantic‑модели
  и исключения SDK как на реализационный уровень.
- Требования `docs/REQUIREMENTS_moex-market-analyst-agent.md` фиксируют
  необходимость централизованной обработки ошибок и rate limiting, что
  реализуется именно в `moex_iss_sdk`.

## Эволюция

### Краткосрочная перспектива

- Перенос всех существующих HTTP‑вызовов ISS из `moex-iss-mcp` в SDK
  (`TASK-2025-074`), чтобы MCP не содержал собственного клиента.
- Добавление LRU‑кэша и специализированных исключений (`TASK-2025-075`).

### Среднесрочная перспектива

- Расширение API SDK дополнительными методами (скрининг по ликвидности,
  агрегаты по секторам, производные показатели), не ломая существующие
  сигнатуры `IssClient`.
- Возможное использование SDK другими внутренними сервисами и утилитами, не
  связанными напрямую с MCP (например, офлайн‑скриптами подготовки данных для
  демо/тестов).
