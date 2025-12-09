---
id: TASK-2025-016
title: "Фаза 1.5. Tool get_ohlcv_timeseries"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Обеспечивает исторические OHLCV-данные и базовые метрики для сценариев обзора и сравнения тикеров."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать MCP-инструмент `get_ohlcv_timeseries`, принимающий тикер, борд, период и интервал, с валидацией дат и ограничением `MAX_LOOKBACK_DAYS`, возвращающий OHLCV-ряд и агрегированные метрики.

## Критерии приемки

- Определены Pydantic-модели входа/выхода согласно SPEC (ticker, board, from_date, to_date, interval).
- Валидация гарантирует:
  - `to_date >= from_date`;
  - длительность периода не превышает `MAX_LOOKBACK_DAYS`, иначе формируется ошибка `DATE_RANGE_TOO_LARGE`.
- Инструмент вызывает соответствующий метод `IssClient`, преобразует данные в нормализованный массив баров и считает:
  - `total_return_pct`;
  - `annualized_volatility`;
  - `avg_daily_volume`.
- Интеграционный тест:
  - 90-дневный период → непустые данные и разумные метрики;
  - 5-летний период → ошибка `DATE_RANGE_TOO_LARGE` в `error`.

## Определение готовности

- Агент может использовать `get_ohlcv_timeseries` для построения сравнений и отчётов по отдельным тикерам.
- Поведение по датам и ошибкам соответствует документации Фазы 0.

## Заметки

Соответствует пункту 1.5 плана архитектора (Фаза 1).

