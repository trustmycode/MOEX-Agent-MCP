---
id: TASK-2025-027
title: "Фаза 2.8. Agent Card и документация"
status: backlog
priority: high
type: chore
estimate: 8h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-003]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: low
benefit: "Готовит Agent Card и синхронизирует документацию под фактическую реализацию агента."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Оформить Agent Card для `moex-market-analyst-agent` и обновить архитектурную/пользовательскую документацию (ARCHITECTURE, README) в соответствии с реализованными компонентами агента и подключёнными MCP.

## Критерии приемки

- Agent Card содержит:
  - имя и версию агента;
  - описание домена и сценариев использования;
  - список поддерживаемых протоколов (HTTP + JSON, A2A);
  - информацию об аутентификации (сервисный аккаунт Evolution);
  - список задействованных MCP-серверов (URI из `MCP_URL`);
  - ограничения и особенности использования.
- Agent Card успешно проходит валидацию в Evolution AI Agents.
- ARCHITECTURE и README обновлены и отражают фактическую структуру агента, A2A-контракт и интеграцию с MCP.

## Определение готовности

- Агент может быть включён в каталог Evolution AI Agents с корректным описанием.

## Заметки

Декомпозиция пункта 2.8 плана архитектора (Фаза 2).

