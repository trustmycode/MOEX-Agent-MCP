---
id: TASK-2025-079
title: "Фаза 2.4. SPEC и tools.json для risk-analytics-mcp"
status: done
priority: high
type: chore
estimate: 8h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-007]
children: [TASK-2025-098, TASK-2025-099, TASK-2025-100]
arch_refs: [ARCH-mcp-risk-analytics]
risk: low
benefit: "Формализует контракт risk-analytics-mcp (JSON Schema и tools.json) для интеграции в Evolution AI Agents и агента."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Подготовить SPEC-документацию и `tools.json` для MCP-сервера
`risk-analytics-mcp`, описав инструменты `compute_portfolio_risk_basic`
и `compute_correlation_matrix` в формате, совместимом с Evolution
AI Agents.

Задача соответствует пункту 2.4 плана архитектора.

## Критерии приемки

- В SPEC-файле (отдельный раздел или отдельный документ) описаны:
  - назначение MCP `risk-analytics-mcp`;
  - JSON Schema входа/выхода для `compute_portfolio_risk_basic`;
  - JSON Schema входа/выхода для `compute_correlation_matrix`;
  - формат ошибок и поддерживаемые значения `error_type`.
- Подготовлен `tools.json` (или эквивалент) с описанием обоих
  инструментов: `name`, `description` (EN), ссылки на схемы
  `input_schema` и `output_schema`.
- Выполнена пробная валидация `tools.json` средствами платформы
  Evolution AI Agents (либо утилитой проверки схем, если доступна).

## Определение готовности

- MCP `risk-analytics-mcp` можно зарегистрировать в Evolution AI Agents
  без ручных правок схем и описаний инструментов.
- Агент `moex-market-analyst-agent` может использовать описания
  инструментов risk-analytics-mcp из `tools.json`/SPEC для
  конфигурации `ToolRegistry` и планировщика.

## Заметки

- При обновлении моделей/полей инструментов в будущем необходимо
  поддерживать синхронизацию SPEC, `tools.json` и Pydantic-моделей
  в коде.

