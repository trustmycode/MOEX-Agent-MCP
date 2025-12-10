---
id: TASK-2025-024
title: "Фаза 2.5. McpClient и ToolOrchestrator"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-003]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Реализует связку агента с MCP-серверами и исполнение плана вызовов инструментов."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать `McpClient` для вызова MCP-инструментов по `MCP_URL` и `ToolOrchestrator`, который исполняет `Plan`, агрегируя результаты `ToolCallResult` в `SessionContext`.

## Критерии приемки

- `McpClient` умеет:
  - парсить `MCP_URL` и регистрировать несколько MCP-серверов;
  - вызывать `call_tool(server_name, tool_name, args)` с учётом тайм-аутов и ретраев;
  - логировать вызовы и ошибки через телеметрию.
- `ToolOrchestrator.execute_plan(ctx, plan)`:
  - последовательно (или по мере необходимости) исполняет шаги `mcp_call`;
  - сохраняет `ToolCallResult` в `ctx.tool_results`;
  - формирует краткий `ToolExecutionSummary`.
- Есть интеграционный тест: при запросе «Сравни SBER и GAZP за год» агент реально вызывает MCP и получает данные.

## Определение готовности

- Планировщик и формирователь ответа могут опираться на `ToolOrchestrator` как на чёрный ящик исполнения инструментов MCP.

## Заметки

Декомпозиция пункта 2.5 плана архитектора (Фаза 2).

