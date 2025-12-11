---
id: TASK-2025-076
title: "Фаза 2.1. Каркас MCP risk-analytics-mcp"
status: done
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-12
parents: [TASK-2025-007]
children: [TASK-2025-089, TASK-2025-090, TASK-2025-091, TASK-2025-141]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Создаёт отдельный MCP-сервис для портфельного и корреляционного анализа поверх moex_iss_sdk."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-12, user: "@AI-Architect", action: "added child task TASK-2025-141 for Evolution deployment preparation"}
---

## Описание

Реализовать каркас MCP-сервера `risk-analytics-mcp`: структуру пакета,
конфигурацию, инициализацию FastMCP и базовые endpoint'ы `/mcp`,
`/health`, `/metrics`, подключив `moex_iss_sdk.IssClient` как источник
данных о ценах и временных рядах.

Задача соответствует пункту 2.1 плана архитектора («Создать каркас
risk-analytics-mcp»).

## Критерии приемки

- В репозитории создан пакет `risk_analytics_mcp` со структурой,
  близкой к `moex_iss_mcp` (main.py, config.py, server.py,
  подмодули `models`, `tools`, `calculations`, `telemetry`).
- Реализован класс конфигурации (`RiskMcpConfig` или аналог),
  загружающий ключевые параметры из ENV (порт, лимиты по тикерам/дням,
  настройки доступа к ISS/SDK, параметры телеметрии).
- `main.py` поднимает FastMCP-сервер с transport="streamable-http" и
  регистрирует хотя бы заглушки tools `compute_portfolio_risk_basic` и
  `compute_correlation_matrix`.
- Endpoint `/health` возвращает `{"status": "ok"}`, endpoint
  `/metrics` отдаёт базовые метрики (можно временно пустые).

## Определение готовности

- `risk-analytics-mcp` успешно стартует локально и в docker-контейнере
  без подключённой бизнес-логики tools.
- Агента или отдельный тестовый клиент можно настроить на вызов MCP по
  `MCP_URL` и получить успешный ответ `/health`.

## Заметки

- Подробная бизнес-логика и модели для tools реализуются в задачах
  `TASK-2025-077`–`TASK-2025-079`.

