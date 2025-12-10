---
id: TASK-2025-089
title: "Фаза 2.1.1. Структура проекта и конфиг risk-analytics-mcp"
status: backlog
priority: high
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-076]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Создаёт минимально необходимую структуру пакета risk_analytics_mcp и конфигурацию окружения."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Создать пакет `risk_analytics_mcp` с базовой структурой директорий
(`main.py`, `config.py`, `server.py`, подмодули `models`, `tools`,
`calculations`, `telemetry`) и реализовать конфигурационный класс
(`RiskMcpConfig` или аналог), загружающий параметры из ENV.

## Критерии приемки

- В репозитории присутствует пакет `risk_analytics_mcp` со структурой,
  соответствующей `ARCH-mcp-risk-analytics-v1.md`.
- Реализован класс конфигурации, читающий как минимум:
  - порт сервера;
  - лимиты по тикерам/дням;
  - параметры доступа к MOEX ISS/SDK;
  - настройки телеметрии (включение/выключение, endpoints).
- Конфиг проходит unit-тесты на корректную загрузку/валидацию ENV.

## Определение готовности

- Другие задачи по risk-analytics-mcp могут опираться на готовый каркас
  пакета и конфигурации, не создавая свою структуру.

## Заметки

- На этом этапе бизнес-логика tools может быть заглушена.

