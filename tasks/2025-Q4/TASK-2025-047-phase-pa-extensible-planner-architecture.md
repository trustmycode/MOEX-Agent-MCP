---
id: TASK-2025-047
title: "Фаза PA. Расширяемая архитектура планировщика"
status: backlog
priority: high
type: feature
estimate: 32h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-003]
children: [TASK-2025-056, TASK-2025-057, TASK-2025-058]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Переводит планировщик на стратегию PlanningStrategy с ToolRegistry и телеметрией, готовя его к advanced-режиму и внешнему Planner Agent."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Выделить планировщик агента в расширяемую подсистему с интерфейсом `PlanningStrategy`, стратегиями `BasicPlanningStrategy`/`AdvancedPlanningStrategy`/`ExternalAgentPlanningStrategy`, единым реестром MCP-инструментов `ToolRegistry` и отдельной телеметрией планировщика.

## Критерии приемки

- Определён интерфейс `PlanningStrategy` с методами `build_plan(ctx)` и `replan(ctx, exec_result)`; текущая логика Planner v1 перенесена в реализацию `BasicPlanningStrategy` без изменения поведения basic-режима.
- Класс `Planner` становится фасадом, принимающим `PlanningStrategy` (через DI/конфиг по `PLANNER_MODE`) и делегирующим ей построение и перепланирование; при `PLANNER_MODE=basic` поведение совпадает с задачей P0.
- Реализованы каркасы `AdvancedPlanningStrategy` и `ExternalAgentPlanningStrategy` (с заглушками или минимальной логикой), которые не активны без соответствующих фиче-флагов.
- Введён компонент `ToolRegistry` с моделью `ToolSpec` (`name`, `server`, `description`, `enabled`, `experimental`, `cost_rank`, `reliability_rank`), который:
  - загружает конфигурацию из `tools.json` и ENV-флагов;
  - предоставляет методы `list_tools()` и `get_tool(name)`;
  - является единственным источником правды о доступных MCP-инструментах.
- `Planner` и `ToolOrchestrator` перестают хардкодить имена tools и серверов, получая их из `ToolRegistry`; отключение инструмента (`enabled=false`) исключает его и из построения плана, и из фактических вызовов.
- Добавлена телеметрия планировщика: счётчики и/или метрики вида `plans_built_total{strategy,scenario_type}`, `plans_replanned_total{strategy}`, `plans_failed_total{reason}`, а также метрики по размеру портфеля (например, `portfolio_risk_tickers_total{bucket="<=10","11-30",">30"}`).
- В логах планировщика фиксируются `scenario_type`, количество тикеров в запросе и факт применения деградации (ограничения портфеля) для сценариев портфельного риска.

## Определение готовности

- В режиме `PLANNER_MODE=basic` все существующие тесты планировщика проходят через `BasicPlanningStrategy`, без регрессий по поведению basic-режима.
- Отключение любого MCP-инструмента через конфигурацию немедленно отражается в планах и фактических вызовах (инструмент не используется), что видно по логам и метрикам.
- В наблюдаемости доступны агрегаты по стратегиям и сценариям планировщика, в том числе распределение запросов `portfolio_risk` по размеру портфеля.

## Заметки

Дальнейшие фазы (PB–PE) будут наращивать поверх этой архитектуры LLM-assistant re-plan, сценарные шаблоны и внешнего Planner Agent; задача PA задаёт каркас, в который эти возможности встраиваются без ломки существующего кода.
