---
id: TASK-2025-004
title: "Фаза 3. Инфраструктура и деплой"
status: backlog
priority: high
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
children: [TASK-2025-028, TASK-2025-029, TASK-2025-030, TASK-2025-031, TASK-2025-032]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Обеспечивает стабильный запуск MCP и агента локально и в Evolution AI Agents, включая smoke-тесты."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Построить инфраструктуру сборки и запуска MCP и агента: Docker-образы, `docker-compose.yml` для локальной разработки, smoke-тест end-to-end и деплой в Cloud.ru Evolution AI Agents с корректной настройкой секретов и переменных окружения.

## Критерии приемки

- Подготовлены Dockerfile для MCP и агента (linux/amd64); образы успешно собираются локально и стартуют без ошибок.
- Описан `docker-compose.yml`, поднимающий MCP, агента и (опционально) заглушку LLM; команды `make local-up` / `make local-down` запускают и останавливают контур.
- Реализован smoke-тест, который поднимает MCP и агента, отправляет запрос «Сравни SBER и GAZP за год» и проверяет HTTP 200, ненулевой `output.text` и `output.tables`.
- MCP и агент зарегистрированы в Evolution AI Agents (dev и prod-контуры при необходимости); они видны в интерфейсе и доступны для вызова.
- Настроены секреты и переменные окружения через Secret Manager/конфиг проекта; в репозитории нет хардкода ключей.
- README содержит раздел с описанием необходимых env-переменных и шагами деплоя в Evolution AI Agents.

## Определение готовности

- Один вызов `make local-up` поднимает работающий контур MCP+агент и позволяет выполнить smoke-тест.
- В dev-контуре Evolution AI Agents агент успешно обрабатывает тестовый сценарий без ручных вмешательств.
- Конфигурация секретов и env-переменных задокументирована и воспроизводима для нового окружения.

## Заметки

Эта задача агрегирует подпункты 3.1–3.5 плана архитектора (Фаза 3).
