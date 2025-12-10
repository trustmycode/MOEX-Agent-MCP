---
id: TASK-2025-056
title: "Фаза PA.1. Интерфейс PlanningStrategy и BasicPlanningStrategy"
status: backlog
priority: high
type: feature
estimate: 12h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-047]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Выделяет интерфейс стратегий планирования и переносит текущую логику Planner v1 в BasicPlanningStrategy."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Определить интерфейс `PlanningStrategy` с методами построения и перепланирования плана и реализовать `BasicPlanningStrategy`, в которую переносится текущая логика Planner v1, сохраняя поведение basic-режима.

## Критерии приемки

- В коде агента объявлен интерфейс/абстрактный класс `PlanningStrategy` с методами `build_plan(ctx)` и `replan(ctx, exec_result)`.
- Реализован класс `BasicPlanningStrategy`, содержащий всю существующую бизнес-логику построения плана (включая учёт лимитов и heuristic re-plan) вместо монолитного Planner v1.
- Класс `Planner` становится тонким фасадом, который:
  - выбирает стратегию на основе конфигурации (`PLANNER_MODE`);
  - делегирует вызовы `build_plan`/`replan` выбранной стратегии;
  - сам не содержит доменной логики построения плана.
- Все существующие тесты планировщика и e2e-сценариев проходят без изменений ожидаемого поведения в режиме `PLANNER_MODE=basic`.

## Определение готовности

- Подключение новых стратегий (advanced, external_agent) требует минимальных изменений (регистрация и выбор по конфигу), без переписывания базовой логики.
- Basic-режим остаётся предсказуемым и совпадает по поведению с реализацией до рефакторинга.

## Заметки

Эта подзадача закладывает фундамент для последующих стратегий (`AdvancedPlanningStrategy`, `ExternalAgentPlanningStrategy`) и упрощает эволюцию планировщика.
