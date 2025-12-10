---
id: TASK-2025-057
title: "Фаза PA.2. Реализация ToolRegistry и ToolSpec"
status: backlog
priority: high
type: feature
estimate: 12h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-047]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Вводит единый реестр MCP-инструментов для планировщика и оркестратора."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать компонент `ToolRegistry` и модель `ToolSpec`, которые становятся единым источником правды по MCP-инструментам для `Planner` и `ToolOrchestrator`, с поддержкой отключения/пометки experimental-инструментов и указанием их относительной стоимости/надёжности.

## Критерии приемки

- Определена модель `ToolSpec` с полями как минимум: `name`, `server`, `description`, `enabled`, `experimental`, `cost_rank`, `reliability_rank`.
- Реализован `ToolRegistry`, который:
  - загружает список инструментов из `tools.json` и/или конфигурации;
  - учитывает ENV-флаги для отключения отдельных инструментов (`enabled=false`) или пометки их как experimental;
  - предоставляет методы `list_tools()` и `get_tool(name)` для использования в планировщике и оркестраторе.
- `Planner` и `ToolOrchestrator` перестают хардкодить имена MCP-инструментов и их серверов, получая данные из `ToolRegistry`.
- Отключение инструмента через конфигурацию приводит к тому, что:
  - он не попадает в строящиеся планы;
  - не вызывается `ToolOrchestrator`-ом;
  - факт отключения видно в логах/метриках.

## Определение готовности

- В тестах можно программно отключить инструмент (например, `get_index_constituents_metrics`) и убедиться, что соответствующие сценарии либо деградируют предсказуемым образом, либо помечаются как недоступные.
- Планировщик использует данные о `cost_rank` и `reliability_rank` для последующих задач по cost-aware планированию (фаза PE).

## Заметки

Интеграция `ToolRegistry` в сценарии (`ScenarioTemplate`) и портфельные сценарии `portfolio_risk` будет доработана в фазе PC.
