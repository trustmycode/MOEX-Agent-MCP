---
id: TASK-2025-012
title: "Фаза 1.1. Каркас MCP: McpConfig, McpServer, main.py"
status: done
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Создаёт базовый каркас MCP-сервера moex-iss-mcp с конфигом и точкой входа."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@codex", action: "marked as done after MCP skeleton, config, endpoints implemented and tested"}
---

## Описание

Реализовать каркас MCP-сервера: конфигурационный объект `McpConfig`, обёртку над FastMCP `McpServer` и `main.py`, поднимающий HTTP-сервер с endpoint'ами `/mcp`, `/health`, `/metrics`.

## Критерии приемки

- Реализован класс `McpConfig.from_env()` с загрузкой ключевых параметров (`PORT`, `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `MOEX_ISS_TIMEOUT_SECONDS`, флаги мониторинга).
- Реализован класс `McpServer`, инициализирующий FastMCP с транспортом `streamable-http` и базовой регистрацией инструментов (пока могут быть заглушки).
- `main.py` поднимает процесс MCP, регистрирует маршруты `/mcp`, `/health`, `/metrics`.
- Локальный запуск возвращает `{"status":"ok"}` на `/health` и не падает при отсутствии инструментов.

## Определение готовности

- MCP можно запустить локально без бизнес-логики tools, и он корректно отвечает на здравоохранительные запросы.
- Конфиг и серверный каркас используются как основа для дальнейших задач Фазы 1.

## Заметки

Декомпозиция пункта 1.1 плана архитектора (Фаза 1).
