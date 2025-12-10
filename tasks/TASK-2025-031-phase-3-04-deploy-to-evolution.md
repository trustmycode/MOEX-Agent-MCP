---
id: TASK-2025-031
title: "Фаза 3.4. Деплой в Evolution AI Agents"
status: backlog
priority: high
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-004]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Переводит решение из локального статуса в работающий сервис в Cloud.ru Evolution AI Agents."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Зарегистрировать MCP и агента в Evolution AI Agents (dev → prod), настроить все необходимые переменные окружения и убедиться, что базовые сценарии выполняются через интерфейс платформы.

## Критерии приемки

- Образы MCP и агента загружены в Registry и доступны в проекте Cloud.ru.
- Созданы сущности MCP и Agent в Evolution AI Agents, настроены связи с образами и Agent Card.
- ENV/секреты настроены через Secret Manager/конфиг, без хардкода ключей.
- Через A2A UI/Inspector можно выполнить сценарий «Сравни SBER и GAZP за год» с успешным ответом.

## Определение готовности

- Решение доступно для демонстрации и тестирования непосредственно в Cloud.ru без локальных зависимостей.

## Заметки

Соответствует пункту 3.4 плана архитектора (Фаза 3).

