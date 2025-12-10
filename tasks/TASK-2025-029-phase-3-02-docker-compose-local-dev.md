---
id: TASK-2025-029
title: "Фаза 3.2. docker-compose для локальной разработки"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-004]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: low
benefit: "Упрощает локальный запуск полного контура MCP+агент одной командой."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Подготовить `docker-compose.yml` для совместного запуска MCP, агента и (опционально) заглушки LLM, а также команды `make local-up/local-down` для удобного старта/остановки.

## Критерии приемки

- Файл `docker-compose.yml` описывает:
  - сервис MCP;
  - сервис агента;
  - (опционально) заглушку LLM или настройки доступа к Foundation Models.
- Команда `make local-up` поднимает все сервисы, `make local-down` их останавливает и очищает ресурсы.
- После запуска по `local-up` smoke-тест (из отдельной задачи) может быть выполнен без ручной донастройки.

## Определение готовности

- Разработчики могут локально поднять контур MCP+агент в одном окружении и использовать его для тестов/демо.

## Заметки

Соответствует пункту 3.2 плана архитектора (Фаза 3).

