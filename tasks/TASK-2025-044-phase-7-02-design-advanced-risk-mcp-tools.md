---
id: TASK-2025-044
title: "Фаза 7.2. Проектирование MCP-инструментов для advanced-риска"
status: backlog
priority: low
type: spike
estimate: 12h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-008]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Определяет будущие MCP-инструменты для расширенного риск-анализа без их немедленной реализации."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Спроектировать (без реализации) MCP-инструменты для расширенного риск-анализа: `get_risk_factors`, `get_portfolio_var`, `get_stress_test_results`, описать их входы/выходы и статус `planned`.

## Критерии приемки

- В SPEC добавлен раздел «Planned tools for advanced risk analytics» с описанием:
  - назначения каждого инструмента;
  - входных параметров;
  - основных полей выходных структур.
- У всех этих инструментов статус `planned`, чётко указано, что они не входят в MVP.

## Определение готовности

- Команда понимает, какие MCP-инструменты нужно будет разработать для полноценного риск-анализа после хакатона.

## Заметки

Соответствует пункту 7.2 плана архитектора (Фаза 7).

