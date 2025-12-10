---
id: TASK-2025-098
title: "Фаза 2.4.1. JSON Schema для инструментов risk-analytics-mcp"
status: backlog
priority: high
type: chore
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-079]
arch_refs: [ARCH-mcp-risk-analytics]
risk: low
benefit: "Формализует входы/выходы compute_portfolio_risk_basic и compute_correlation_matrix в виде JSON Schema."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Подготовить JSON Schema для входных и выходных моделей инструментов
`compute_portfolio_risk_basic` и `compute_correlation_matrix` и
зафиксировать их в SPEC risk-analytics-mcp.

## Критерии приемки

- Для каждого инструмента подготовлены:
  - `<tool>_input.json` — схема входных данных;
  - `<tool>_output.json` — схема выходных данных.
- Схемы согласованы с Pydantic-моделями, реализованными в
  `risk_analytics_mcp.models` (`TASK-2025-092`, `TASK-2025-078`),
  и не противоречат JSON-подходу SPEC `moex-iss-mcp`.
- В SPEC-документе risk-analytics-mcp добавлены разделы с этими
  схемами и описанием полей.

## Определение готовности

- Схемы могут быть использованы как при генерации `tools.json`,
  так и при валидации вызовов MCP на стороне платформы.

## Заметки

- При изменении моделей инструментов в будущем необходимо
  синхронно обновлять и JSON Schema.

