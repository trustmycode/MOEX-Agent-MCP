---
id: TASK-2025-090
title: "Фаза 2.1.2. Каркас FastMCP-сервера и endpoint'ы risk-analytics-mcp"
status: done
priority: high
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-076]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Поднимает рабочий FastMCP-сервер risk-analytics-mcp с базовыми endpoint'ами /mcp, /health, /metrics."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@codex", action: "marked as done after FastMCP server entrypoint, /mcp health/metrics routes, and stub tools registered for risk-analytics-mcp"}
---

## Описание

Реализовать `main.py` и `server.py` для `risk_analytics_mcp`, инициализирующие
FastMCP с transport="streamable-http", настраивающие маршруты `/mcp`,
`/health`, `/metrics` и регистрирующие заглушки инструментов
`compute_portfolio_risk_basic` и `compute_correlation_matrix`.

## Критерии приемки

- `main.py` поднимает процесс MCP, используя `RiskMcpConfig` и `McpServer`
  (или аналог), и экспортирует endpoint'ы `/mcp`, `/health`, `/metrics`.
- `/health` возвращает `{"status": "ok"}`, `/metrics` отдаёт либо пустой,
  либо минимальный набор метрик в формате Prometheus.
- Для обоих инструментов зарегистрированы заглушки tool-хендлеров,
  возвращающие фиксированные/пустые данные без реальных расчётов.

## Определение готовности

- `risk-analytics-mcp` можно запустить локально и через docker, а также
  зарегистрировать в Evolution AI Agents в виде "пустого" MCP.

## Заметки

- Реализацию бизнес-логики и телеметрии для tools следует выполнять в
  задачах `TASK-2025-077`–`TASK-2025-079` и `TASK-2025-091`.
