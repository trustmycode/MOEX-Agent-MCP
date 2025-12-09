---
id: TASK-2025-028
title: "Фаза 3.1. Docker-образы MCP и агента"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-004]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Подготавливает контейнерные образы MCP и агента для локального запуска и деплоя в Evolution AI Agents."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Создать Dockerfile для MCP и агента (linux/amd64), обеспечить корректную установку зависимостей и старт сервисов без привязки к локальной файловой системе.

## Критерии приемки

- Существуют два Dockerfile: для `moex-iss-mcp` и `moex-market-analyst-agent`.
- Образы собираются командой `docker build` без дополнительных ручных шагов.
- При запуске контейнеров MCP и агент стартуют без ошибок и открывают соответствующие порт/endpoint.
- В образах отсутствуют секреты и dev-зависимости, не нужные в рантайме.

## Определение готовности

- Образы готовы к загрузке в Registry и дальнейшему использованию в AI Agents.

## Заметки

Соответствует пункту 3.1 плана архитектора (Фаза 3).

