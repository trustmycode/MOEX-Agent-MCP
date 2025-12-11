---
id: TASK-2025-002
title: "Фаза 1. Базовый MCP moex-iss-mcp"
status: done
priority: high
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-12
children: [TASK-2025-012, TASK-2025-013, TASK-2025-014, TASK-2025-015, TASK-2025-016, TASK-2025-017, TASK-2025-018, TASK-2025-019, TASK-2025-141]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Даёт стабильный MCP-сервер с основными бизнес-инструментами и наблюдаемостью."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-12, user: "@AI-Architect", action: "added child task TASK-2025-141 for Evolution deployment preparation"}
---

## Описание

Реализовать минимально жизнеспособный MCP-сервер `moex-iss-mcp` на базе FastMCP с тремя основными инструментами (`get_security_snapshot`, `get_ohlcv_timeseries`, `get_index_constituents_metrics`), нормализованной обработкой ошибок и телеметрией, готовый к регистрации в Evolution AI Agents.

## Критерии приемки

- Реализованы `McpConfig.from_env()`, `McpServer` и `main.py`; MCP поднимается локально и возвращает `{"status": "ok"}` на `/health`.
- `IssClient` и `RateLimiter` ограничивают RPS, поддерживают тайм-ауты и ретраи; существуют unit-тесты для URL и логики rate limiting.
- `DomainCalculations` предоставляет функции для расчёта доходности, волатильности, среднего дневного объёма и базовых агрегатов.
- Инструменты `get_security_snapshot`, `get_ohlcv_timeseries`, `get_index_constituents_metrics` реализованы через Pydantic-модели и используют `IssClient`, `DomainCalculations`, `ErrorMapper`.
- Для типовых позитивных сценариев существуют интеграционные тесты (валидный тикер, разумный период, рабочий индекс).
- Endpoint `/metrics` экспортирует метрики `tool_calls_total`, `tool_errors_total`, `mcp_http_latency_seconds`.
- `tools.json` синхронизирован с фактическими моделями и готов к использованию в AI Agents.

## Определение готовности

- MCP-сервер собирается и стартует в контейнере без ошибок.
- Все unit- и интеграционные тесты по MCP проходят.
- Временная нагрузка (запросы от агента по базовым сценариям) не приводит к превышению лимита RPS и деградации ISS.

## Заметки

Эта задача агрегирует подпункты 1.1–1.8 плана архитектора (Фаза 1).
