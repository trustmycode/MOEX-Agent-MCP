---
id: TASK-2025-060
title: "Фаза PB.2. Heuristic re-plan на базе PlanExecutionResult"
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
benefit: "Переводит heuristic re-plan basic-режима на использование структурированного результата выполнения плана."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Адаптировать `BasicPlanningStrategy.replan(...)` к использованию `PlanExecutionResult`, чтобы heuristic re-plan работал на уровне конкретных упавших шагов и их категорий ошибок, а не на базе грубых сигналов.

## Критерии приемки

- `BasicPlanningStrategy.replan(...)` принимает `PlanExecutionResult` (или эквивалентную структуру) и анализирует только те шаги, которые имеют `status="failed"` и распознанный `error_category`.
- Логика обработки ошибок `DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`, `RATE_LIMIT` и других типовых ошибок переносится на работу с `ExecutedStep.error_category`.
- В случае смешанных ошибок (часть шагов упала с обрабатываемыми категориями, часть — с неизвестными) стратегия корректирует только «известные» шаги и не делает неконтролируемых догадок.
- Тесты покрывают сценарии с несколькими упавшими шагами, в том числе когда re-plan корректирует только часть плана.

## Определение готовности

- Heuristic re-plan в basic-режиме становится более точечным и легко расширяемым за счёт добавления новых `error_category`.
- Наблюдаемость (логи/метрики) отражает, какие именно шаги были изменены в результате heuristic re-plan.

## Заметки

Это подготовительный шаг для advanced-стратегии, которая будет использовать тот же `PlanExecutionResult` в LLM-assisted re-plan.
