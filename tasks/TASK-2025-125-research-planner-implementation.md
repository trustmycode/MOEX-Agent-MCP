---
id: TASK-2025-125
title: "Реализация ResearchPlannerSubagent (LLM-based planning)"
status: todo
priority: high
type: feature
estimate: 12h
assignee: @unassigned
created: 2025-12-13
updated: 2025-12-13
parents: [TASK-2025-120]
children: [TASK-2025-126]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Позволяет агенту обрабатывать нестандартные запросы, динамически составляя план выполнения из доступных инструментов."
audit_log:
  - {date: 2025-12-13, user: "@AI-Architect", action: "created"}
---

## Описание

Реализовать `ResearchPlannerSubagent` — сабагент, который принимает запрос пользователя и с помощью LLM генерирует план выполнения (`ExecutionPlan`), состоящий из последовательности вызовов других сабагентов (`MarketData`, `RiskAnalytics` и т.д.).

В отличие от `IntentClassifier` (который просто выбирает шаблон), этот агент должен *генерировать* цепочку шагов и параметры для них.

## Объем работ

1. **Создание класса `ResearchPlannerSubagent`**:
   - Наследование от `BaseSubagent`.
   - Инициализация `EvolutionLLMClient`.
2. **Промпт-инжиниринг**:
   - Разработка системного промпта, описывающего возможности (capabilities) всех остальных сабагентов (`market_data`, `risk_analytics`, `dashboard`, `explainer`, `knowledge`).
   - Определение формата вывода (строгий JSON).
3. **Логика выполнения (`execute`)**:
   - Отправка запроса в LLM.
   - Парсинг JSON-ответа в структуру `ExecutionPlan` (или список `PipelineStep`).
   - Валидация плана (проверка, что предложенные сабагенты существуют).

## Критерии приемки

- [ ] Реализован класс `ResearchPlannerSubagent` в `packages/agent-service/src/agent_service/subagents/research_planner.py`.
- [ ] Системный промпт содержит актуальное описание инструментов (например, "MarketData умеет получать цены и OHLCV", "RiskAnalytics считает VaR").
- [ ] Метод `execute` возвращает `SubagentResult` с данными в формате:

  ```json
  {
    "plan": {
      "steps": [
        {"subagent": "market_data", "reason": "Need historical prices"},
        {"subagent": "risk_analytics", "reason": "Calculate volatility"}
      ]
    }
  }
  ```

- [ ] Написаны unit-тесты с моком LLM, проверяющие корректность парсинга JSON в план.
- [ ] Сабагент зарегистрирован в `server.py` (но пока не используется оркестратором).

## Технические детали

- **Модель ответа LLM:**

  ```python
  class PlannedStep(BaseModel):
      subagent_name: str
      description: str
      required: bool = True

  class PlannerOutput(BaseModel):
      reasoning: str
      steps: list[PlannedStep]
  ```
