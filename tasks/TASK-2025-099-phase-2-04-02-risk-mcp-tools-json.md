---
id: TASK-2025-099
title: "Фаза 2.4.2. Формирование tools.json для risk-analytics-mcp"
status: backlog
priority: high
type: chore
estimate: 4h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-079]
arch_refs: [ARCH-mcp-risk-analytics]
risk: low
benefit: "Готовит корректный tools.json для регистрации risk-analytics-mcp в Evolution AI Agents."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Сформировать файл `tools.json` (или эквивалентный артефакт) для
`risk-analytics-mcp`, описывающий инструменты
`compute_portfolio_risk_basic` и `compute_correlation_matrix` в формате,
совместимом с Evolution AI Agents.

## Критерии приемки

- `tools.json` содержит два инструмента с полями:
  - `name`;
  - `description` (EN, предназначенное для LLM);
  - `input_schema`/`output_schema` (ссылки на схемы из
    `TASK-2025-098`);
  - при необходимости дополнительные поля, требуемые платформой
    (версия, serverId и т.п.).
- Структура `tools.json` согласована с актуальной документацией
  Evolution AI Agents и проходит базовую валидацию (ручную или
  автоматизированную).

## Определение готовности

- `risk-analytics-mcp` можно зарегистрировать на платформе без ручного
  редактирования описаний инструментов.

## Заметки

- При добавлении новых инструментов MCP файл `tools.json` должен
  обновляться по понятной процедуре (зафиксированной в документации).

