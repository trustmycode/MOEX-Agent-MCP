---
id: TASK-2025-023
title: "Фаза 2.4. Planner (минимальное LLM-планирование)"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-003]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Обеспечивает построение плана действий агента на базе LLM c минимальным числом вызовов."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать компонент `Planner`, который использует `LlmClient` и промпты для построения `Plan` из шагов `mcp_call` и финальной генерации отчёта.

## Критерии приемки

- Определены модели `Plan` и `PlannedStep` (тип шага, tool, аргументы, описание).
- `Planner.build_plan(ctx: SessionContext)` строит план на основе последнего user-сообщения и контекста (без лишних LLM-вызовов).
- Для запроса «Сравни SBER и GAZP за год» план содержит:
  - шаги вызова MCP-инструментов для обоих тикеров (`get_ohlcv_timeseries` или `get_multi_ohlcv_timeseries`);
  - финальный шаг генерации отчёта.
- Есть тесты/фикстуры, проверяющие структуру плана для нескольких типовых запросов.

## Определение готовности

- Агент может объяснимо вывести, какие MCP-вызовы он собирается делать, прежде чем собирать отчёт.

## Заметки

Соответствует пункту 2.4 плана архитектора (Фаза 2).

