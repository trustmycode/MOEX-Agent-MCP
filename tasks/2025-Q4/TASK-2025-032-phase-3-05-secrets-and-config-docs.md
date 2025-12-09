---
id: TASK-2025-032
title: "Фаза 3.5. Secret Manager и конфигурация"
status: backlog
priority: high
type: chore
estimate: 8h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-004]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: low
benefit: "Гарантирует безопасное хранение секретов и понятную документацию по конфигурации."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Вынести чувствительные данные (ключи FM, ISS, OTEL/Prometheus endpoints) в Secret Manager/переменные окружения и задокументировать необходимые ENV-переменные в README.

## Критерии приемки

- Все секреты передаются в MCP и агент только через переменные окружения/Secret Manager, не присутствуют в репозитории.
- В README есть таблица ENV-переменных с описанием и указанием обязательности (для MCP и агента).
- Для dev/prod окружений описаны отличия в конфигурации (например, `ENVIRONMENT`, разные ключи и endpoints).

## Определение готовности

- Новому человеку в команде достаточно README и доступа к Secret Manager, чтобы поднять окружение.

## Заметки

Соответствует пункту 3.5 плана архитектора (Фаза 3).

