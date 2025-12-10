---
id: TASK-2025-059
title: "Фаза PB.1. PlanExecutionResult и ExecutedStep"
status: backlog
priority: medium
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-048]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Структурирует результаты выполнения плана для последующего re-plan в basic и advanced стратегиях."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Ввести модели `ExecutedStep` и `PlanExecutionResult` и изменить `ToolOrchestrator.execute_plan(...)` так, чтобы он возвращал структурированный результат выполнения плана вместо неформальных структур/словарей.

## Критерии приемки

- Определены модели:
  - `ExecutedStep` с полями `step_id`, `status` (success/failed), `error_category`, `duration_ms` и, при необходимости, дополнительными метаданными;
  - `PlanExecutionResult` с коллекциями `successful_steps`, `failed_steps` и флагом `has_fatal_error`.
- `ToolOrchestrator.execute_plan(plan, ctx)` возвращает `PlanExecutionResult`, заполняя его на основе реального исполнения шагов плана.
- Существующие потребители результатов выполнения плана адаптированы к новому интерфейсу без потери информации (например, debug-вывод, телеметрия).

## Определение готовности

- Тесты демонстрируют, что для сценариев с успехом и с ошибками структура `PlanExecutionResult` корректно отражает статус выполнения каждого шага и общее состояние плана.
- Basic- и advanced-стратегии могут использовать `PlanExecutionResult` как источник правды для принятия решений о re-plan.

## Заметки

Эта подзадача является техническим фундаментом для heuristic и LLM-assisted re-plan, реализуемых в последующих подзадачах фазы PB.
