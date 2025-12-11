---
id: TASK-2025-075
title: "Фаза 0.6. Кэш и расширенные исключения в moex_iss_sdk"
status: done
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-002]
children: [TASK-2025-086, TASK-2025-087, TASK-2025-088]
arch_refs: [ARCH-sdk-moex-iss, ARCH-mcp-moex-iss]
risk: medium
benefit: "Добавляет LRU-кэш и нормализованные исключения в moex_iss_sdk, упрощая обработку ошибок и снижая нагрузку на MOEX ISS."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать в `moex_iss_sdk` опциональный LRU-кэш с TTL для типовых
запросов и набор специализированных исключений (`InvalidTickerError`,
`DateRangeTooLargeError`, `TooManyTickersError`, `IssTimeoutError`,
`IssServerError`, `UnknownIssError`), которые будут использоваться
MCP-серверами при маппинге ошибок в `error_type`.

Задача соответствует пункту 0.3 плана архитектора («Добавить LRU-кэш и
расширенные исключения»).

## Критерии приемки

- В SDK добавлен LRU-кэш с параметрами `ENABLE_CACHE` и
  `CACHE_TTL_SECONDS`, управляемыми через конфигурацию/ENV; кэш
  прозрачно оборачивает вызовы `IssClient` для идемпотентных
  запросов (snapshot, индексные маппинги, короткие интервалы истории).
- Определены и задокументированы классы исключений:
  `InvalidTickerError`, `DateRangeTooLargeError`,
  `TooManyTickersError`, `IssTimeoutError`, `IssServerError`,
  `UnknownIssError`.
- `moex-iss-mcp` и `risk-analytics-mcp` используют эти исключения и
  маппят их на нормализованные `error_type` (`INVALID_TICKER`,
  `DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`, `ISS_TIMEOUT`,
  `ISS_5XX`, `UNKNOWN`).
- Написаны unit-тесты на поведение кэша (TTL, инвалидация, hit/miss)
  и корректное пробрасывание/маппинг исключений.

## Определение готовности

- Нагрузочные/повторные запросы snapshot/индексных данных демонстрируют
  снижение числа реальных HTTP-вызовов к ISS за счёт кэширования.
- В SPEC MCP задокументирован набор поддерживаемых `error_type`,
  согласованный с реализацией SDK.

## Заметки

- Конкретные значения TTL и объёма кэша могут быть уточнены по итогам
  первых нагрузочных тестов и ограничений по памяти.

