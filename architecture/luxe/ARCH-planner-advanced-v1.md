---
id: ARCH-planner-advanced
title: "Продвинутый планировщик агента (PlanningStrategy, External Planner)"
type: component
layer: application
owner: @team-moex-agent
version: v1
status: draft
created: 2025-12-10
updated: 2025-12-10
tags: [planner, strategy, luxe]
depends_on: [ARCH-agent-moex-market-analyst]
referenced_by: []
---

## Контекст

В P0‑версии агент использует простой deterministic‑планировщик, основанный на
`ScenarioTemplate` и жёстких лимитах. Для production‑эксплуатации и сложных
кейсов планируется развитие подсистемы планирования в отдельный слой с
поддержкой нескольких стратегий и, при необходимости, вынесенного Planner
Agent.

Этот документ описывает **люксовый** (расширенный) дизайн планировщика,
который не обязателен для хакатона, но задаёт целевую архитектуру.

## Основные сущности

- **`Plan`** — список шагов (`PlannedStep`) с дополнительной мета‑информацией:
  - `scenario_type` (5/7/9 и базовые сценарии);
  - ожидаемая стоимость (кол-во LLM и MCP‑вызовов, грубая оценка токенов);
  - ссылки на `ScenarioTemplate`.

- **`PlannedStep`** — отдельный шаг плана:
  - тип шага (`mcp_call`, `explanation`, `rag_search`, и т.п.);
  - целевой MCP‑инструмент и его аргументы;
  - ссылки на данные/результаты предыдущих шагов.

- **`ExecutedStep`** и `PlanExecutionResult` — факт выполнения плана:
  - статус шага (успех/ошибка);
  - `error_category` (DATE_RANGE_TOO_LARGE, TOO_MANY_TICKERS, RATE_LIMIT,
    MCP_4XX, MCP_5XX и др.);
  - длительность и использованные ресурсы.

- **`PlanningStrategy`** — интерфейс стратегий планирования:

  ```python
  class PlanningStrategy(Protocol):
      def build_plan(self, ctx: SessionContext) -> Plan: ...
      def replan(self, ctx: SessionContext, exec_result: PlanExecutionResult) -> Plan | None: ...
  ```

- **Стратегии**:
  - `BasicPlanningStrategy` — текущий P0‑режим с жёсткими лимитами.
  - `AdvancedPlanningStrategy` — LLM‑assisted re-plan (см. TASK-2025-048).
  - `ExternalAgentPlanningStrategy` — делегирование в вынесенный Planner Agent
    (см. TASK-2025-050).

- **`ToolRegistry`** — единый реестр MCP‑инструментов с метаданными
  (`cost_rank`, `reliability_rank`, `enabled`, `experimental`).

## Высокоуровневое поведение

1. **Выбор стратегии**
   - По `PLANNER_MODE` (`basic` / `advanced` / `external_agent`) агент выбирает
     соответствующую `PlanningStrategy`.

2. **Построение плана**
   - Стратегия строит первоначальный `Plan` на основе `ScenarioTemplate`,
     `ToolRegistry`, `planner.limits` и контекста запроса.

3. **Исполнение плана**
   - `ToolOrchestrator` исполняет `Plan` и возвращает `PlanExecutionResult`.

4. **Re-plan**
   - При наличии фатальных ошибок или нарушении лимитов `PlanningStrategy`
     может вызвать `replan(...)`:
     - heuristic re-plan (basic);
     - LLM‑assisted re-plan (advanced);
     - запрос к внешнему Planner Agent (external), с fallback в basic при
       ошибках/тайм‑аутах.

5. **Валидация и cost-aware**
   - Встроенный `PlanValidator` проверяет:
     - отсутствие циклов;
     - соблюдение лимитов (`MAX_PLAN_STEPS`, `MAX_TICKERS_PER_REQUEST`,
       бюджет токенов);
     - разумную стоимость плана (по `cost_rank` инструментов и оценке
       токенов LLM‑вызовов).

## Интеграция с сценариями 5/7/9

- Для 5/7/9 advanced‑планировщик позволяет:
  - аккуратно деградировать при больших портфелях (автоматически
    документировать `limit_portfolio`, предлагать drill-down);
  - адаптировать набор шагов в зависимости от роли (risk‑менеджер vs CFO);
  - экспериментировать с разными уровнями детализации (`mode=fast/balanced/detailed`).

## Наблюдаемость

- Метрики планировщика:
  - `plans_built_total{strategy,scenario_type}`;
  - `plans_replanned_total{strategy,reason}`;
  - `plans_failed_total{reason}`;
  - распределение по длине планов и размеру портфелей (`portfolio_risk`).
- Логи содержат:
  - `scenario_type`, размер портфеля и факт применения `limit_portfolio`;
  - использование advanced‑режима и fallback‑ов в basic.

## Эволюция

- Внедрение YAML‑DSL для описания `ScenarioTemplate` вне кода (см.
  TASK-2025-051): храним сценарии как версионируемые YAML‑файлы, а
  `PlanningStrategy` и `PlanValidator` работают поверх них.
- Постепенный перенос наиболее сложных сценариев (например,
  `portfolio_stress_test`) в external Planner Agent для независимого
  масштабирования и обновления.

