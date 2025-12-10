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
referenced_by: []
---

## Контекст

`moex_iss_sdk` — это общий Python-пакет для работы с публичным MOEX ISS API,
который используется всеми внутренними MCP-серверами проекта (в первую
очередь `moex-iss-mcp` и `risk-analytics-mcp`).

Основные цели SDK:

- устранить дублирование HTTP‑клиентов ISS в разных MCP;
- зафиксировать единый, типизированный интерфейс `IssClient`;
- инкапсулировать детали rate limiting, ретраев, тайм‑аутов и кэширования;
- дать общие Pydantic‑модели для рыночных сущностей (OHLCV, дивиденды,
  компоненты индекса и т.п.), чтобы бизнес‑логика и MCP‑слой работали с
  одними и теми же структурами данных.

## Структура

Пакет имеет следующую целевую структуру:

```text
moex_iss_sdk/
  __init__.py
  client.py          # IssClient: HTTP, rate limiting, retries, кэш
  models.py          # Pydantic-модели (SecuritySnapshot, OhlcvBar, IndexConstituent, DividendRecord и др.)
  endpoints.py       # Константы и хелперы по ISS-эндпоинтам
  exceptions.py      # Специализированные исключения (InvalidTickerError, DateRangeTooLargeError, IssTimeoutError, IssServerError и др.)
  utils.py           # Вспомогательные функции (нормализация параметров, проверка диапазонов дат, парсинг ответов)
```

Ключевые элементы:

- **`IssClient` (client.py)**: единая точка входа для всех запросов к MOEX ISS;
  конфигурируется через объект настроек или переменные окружения
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
  мапятся в `error_type` на уровне MCP.
- **Утилиты (utils.py)** — функции для нормализации параметров, проверки
  диапазонов дат, разбора ответов ISS и построения удобных DTO.

## Поведение

Основной публичный класс SDK — `IssClient`. Он предоставляет методы:

- `get_security_snapshot(ticker, board) -> SecuritySnapshot`;
- `get_ohlcv_series(ticker, board, from_date, to_date, interval) -> list[OhlcvBar]`;
- `get_index_constituents(index_ticker, as_of_date) -> list[IndexConstituent]`;
- `get_security_dividends(ticker, from_date, to_date) -> list[DividendRecord]`;
- (опционально) батч‑методы и хелперы для построения мульти‑рядов
  (`get_multi_ohlcv_series(...)`) и скрининга ликвидных бумаг.

Все вызовы проходят через общий HTTP‑слой с:

- ограничением RPS по `MOEX_ISS_RATE_LIMIT_RPS`;
- тайм‑аутами запросов `MOEX_ISS_TIMEOUT_SECONDS`;
- ретраями по сетевым/5xx‑ошибкам с backoff;
- опциональным LRU‑кэшем с TTL для типовых запросов (snapshot, индексные
  маппинги, короткие диапазоны истории).

Исключения SDK являются частью контракта: MCP‑серверы (`moex-iss-mcp`,
`risk-analytics-mcp`) не разбирают HTTP‑детали, а обрабатывают уже
нормализованные ошибки, конвертируя их в свои `error_type`:
`INVALID_TICKER`, `DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`,
`ISS_TIMEOUT`, `ISS_5XX`, `UNKNOWN`.

## Эволюция

### Планируемые изменения

- Первая версия SDK используется `moex-iss-mcp` для всех обращений к ISS
  (инструменты snapshot/OHLCV/индекс), замещая внутренний пакет `iss/*`.
- После реализации `risk-analytics-mcp` SDK становится единственным
  источником рыночных данных для портфельных расчётов и корреляций.
- В дальнейшем SDK может быть расширен дополнительными методами
  (скрининг по ликвидности, агрегаты по секторам, производные показатели)
  без изменения уже опубликованного интерфейса `IssClient`.

### История

- v1 (2025-12-10): зафиксирован целевой дизайн `moex_iss_sdk` и интерфейса
  `IssClient` в документации; реализация планируется в задачах
  `TASK-2025-073`–`TASK-2025-075` и последующих задачах по MCP.

