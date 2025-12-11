---
id: TASK-2025-048
title: "Фаза PB. Re-planning v2 и AdvancedPlanningStrategy"
status: cancelled
priority: low
cancellation_reason: "Сложный перепланировщик не нужен в новой архитектуре. Если сабагент ошибся, Оркестратор просто скажет пользователю 'Не смог'."
type: feature
estimate: 32h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-003]
children: [TASK-2025-059, TASK-2025-060, TASK-2025-061]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Добавляет структурированное исполнение плана, более точный heuristic re-plan и LLM-assisted re-plan в advanced-режиме с fallback в basic."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Развить подсистему планировщика до re-planning v2: ввести модели `ExecutedStep` и `PlanExecutionResult` в `ToolOrchestrator`, обновить heuristic re-plan basic-режима на основе этих структур и реализовать `AdvancedPlanningStrategy` с LLM-assisted re-plan под фиче-флагом и fallback в basic.

## Критерии приемки

- `ToolOrchestrator.execute_plan(...)` возвращает объект `PlanExecutionResult`, содержащий:
  - список `ExecutedStep` с полями `step_id`, `status`, `error_category`, `duration_ms`;
  - флаг `has_fatal_error`, отражающий необходимость остановки плана.
- Basic-режим планировщика обновлён на работу с `PlanExecutionResult`:
  - heuristic re-plan корректирует только шаги с известными `error_category` (например, `DATE_RANGE_TOO_LARGE`, `TOO_MANY_TICKERS`, `RATE_LIMIT`);
  - логика ограничена `MAX_REPLAN_ATTEMPTS_BASIC` и не создаёт циклов перепланирования.
- Реализована стратегия `AdvancedPlanningStrategy` (за фиче-флагом/режимом `PLANNER_MODE=advanced`), которая:
  - в `build_plan` может использовать дополнительные подсказки/метаданные сценария (scenario hints);
  - в `replan` формирует компактный контекст для LLM: сокращённый исходный план, `PlanExecutionResult`, актуальные лимиты `planner.limits` и сведения о размере портфеля/лимите top-N для `portfolio_risk`;
  - вызывает Qwen3-235B (через `LlmClient`) для построения нового плана, валидирует его и соблюдает лимит `MAX_REPLAN_ATTEMPTS_ADVANCED`;
  - при недоступности/ошибке LLM или нарушении лимитов аккуратно откатывается к heuristic re-plan basic-режима.
- Для одного специально подобранного сценария (например, `portfolio_risk` с 30+ тикерами) есть интеграционный тест, демонстрирующий корректную работу LLM-assisted re-plan (перестроенный план, сужение портфеля/периода, отсутствие бесконечных циклов).
- В логах/метриках фиксируется доля запросов, в которых был задействован advanced re-plan, и частота fallback-ов в basic.

## Определение готовности

- Planner в режиме `basic` продолжает работать предсказуемо, а heuristic re-plan, основанный на `PlanExecutionResult`, стал более точным и расширяемым без регрессий.
- В режиме `advanced` как минимум один демонстрационный сценарий проходит путь: базовый план → частичный фейл → LLM-assisted re-plan → успешное завершение с учётом лимитов.
- При отключении advanced-режима (фиче-флаг) вся логика re-plan корректно работает на heuristic-уровне и не зависит от LLM.

## Заметки

Эта задача опирается на архитектурный каркас из фазы PA и подготавливает базу для сценарных шаблонов и валидатора плана (фаза PE).
