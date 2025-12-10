---
id: TASK-2025-013
title: "Фаза 1.2. IssClient и RateLimiter"
status: done
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Инкапсулирует доступ к MOEX ISS с учётом RPS-лимита, тайм-аутов и ретраев."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@codex", action: "marked as done after IssClient rate limiting/retries and tests delivered"}
---

## Описание

Реализовать HTTP-клиент `IssClient` к MOEX ISS и `RateLimiter`, обеспечивающий ограничение RPS и контролируемые ретраи/тайм-ауты для всех инструментов MCP.

## Критерии приемки

- `IssClient` поддерживает методы:
  - `get_security_snapshot`;
  - `get_ohlcv_series`;
  - `get_index_list` / `get_index_analytics_for_date` / `get_index_tickers_for_date` (в соответствии со SPEC).
- Реализован `RateLimiter`, обеспечивающий соблюдение `MOEX_ISS_RATE_LIMIT_RPS` для всех исходящих запросов.
- В `IssClient` настроены тайм-ауты и базовая retry-логика (c backoff или фиксированными интервалами).
- Есть unit-тесты, проверяющие формирование URL/параметров и корректную работу rate limiting (без реальных запросов).

## Определение готовности

- Все будущие tools MCP могут использовать `IssClient`/`RateLimiter` без необходимости дублировать сетевую логику.
- При нагрузочных тестах RPS по запросам к ISS не превышает заданный лимит.

## Заметки

Задача конкретизирует пункт 1.2 плана архитектора (Фаза 1).
