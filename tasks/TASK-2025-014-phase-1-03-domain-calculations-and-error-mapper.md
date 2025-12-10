---
id: TASK-2025-014
title: "Фаза 1.3. DomainCalculations и ErrorMapper"
status: done
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-10
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Выделяет чистые доменные расчёты и единый слой нормализации ошибок MCP."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@assistant", action: "marked as done"}
---

## Описание

Реализовать модуль доменных расчётов `DomainCalculations` для базовых метрик и модуль `ErrorMapper`, преобразующий исключения в унифицированную модель `ToolErrorModel`.

## Критерии приемки

- `DomainCalculations` предоставляет функции:
  - `calc_total_return_pct`;
  - `calc_annualized_volatility`;
  - `calc_avg_daily_volume`;
  - `calc_top5_weight_pct` и другие агрегирующие хелперы по индексам/портфелям.
- Реализован `ToolErrorModel` (Pydantic) и `ErrorMapper`, мапящий сетевые/валидационные/ISS-ошибки на `error_type`, `message`, `details`.
- Есть unit-тесты на формулы и корректное формирование ошибок для нескольких типовых сценариев (timeout, 4xx, неверный тикер).

## Определение готовности

- Все инструменты MCP могут использовать единый набор доменных расчётов и формат ошибок без дублирования кода.
- Тесты формул проходят и дают разумные значения на примерных данных.

## Заметки

Соответствует пункту 1.3 плана архитектора (Фаза 1).

