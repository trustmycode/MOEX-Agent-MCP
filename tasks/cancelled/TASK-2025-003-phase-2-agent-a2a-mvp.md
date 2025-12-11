---
id: TASK-2025-003
title: "Фаза 2. AI-агент A2A MVP"
status: cancelled
priority: low
type: feature
estimate: 24h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-12
children: [TASK-2025-020, TASK-2025-021, TASK-2025-022, TASK-2025-023, TASK-2025-024, TASK-2025-025, TASK-2025-026, TASK-2025-027, TASK-2025-046, TASK-2025-047, TASK-2025-048, TASK-2025-049, TASK-2025-050, TASK-2025-051]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: medium
benefit: "Даёт полностью рабочий агент, который через A2A использует MCP и формирует отчёты для бизнес-пользователя."
superseded_by: [TASK-2025-120, TASK-2025-121, TASK-2025-122, TASK-2025-123]
cancellation_reason: "Переход на мультиагентную архитектуру. Логика переезжает в TASK-2025-120...123 (Orchestrator + Subagents)."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-12, user: "@AI-Codex", action: "cancelled — переход на мультиагентную архитектуру"}
---

## Описание

Реализовать AI-агент `moex-market-analyst-agent` как A2A-сервис: конфигурация и клиент Foundation Models с поддержкой MAIN/FALLBACK/DEV, обработчик A2A-запросов, планировщик, оркестратор вызовов MCP, формирование ответа и базовая телеметрия, а также Agent Card и обновлённая документация.

## Критерии приемки

- Реализованы `Config` и `LlmClient` с выбором модели по `ENVIRONMENT` и fallback на `LLM_MODEL_FALLBACK` при transient-ошибках основной модели; есть тесты на dev/prod-конфигурации.
- Определены Pydantic-модели `A2AInput` и `A2AOutput` и обработчик `A2ARequestHandler.handle_request(...)`, который валидирует вход, создаёт `SessionContext` и логирует запрос/ответ.
- `SessionContext` хранит ключевые поля (`user_query`, `locale`, `user_role`, временные метки, `plan`, `tool_results`, ошибки) и корректно создаётся из A2A-входа.
- `Planner` формирует осмысленный `Plan` с шагами `mcp_call` и финальной генерацией отчёта; для примера «Сравни SBER и GAZP за год» план включает вызовы для обоих тикеров и финальное резюме.
- `McpClient` и `ToolOrchestrator` вызывают MCP `moex-iss-mcp` по `MCP_URL`, агрегируют результаты и помещают их в `SessionContext.tool_results`; есть интеграционный тест сквозного вызова MCP.
- `ResponseFormatter` строит `output.text`, `output.tables` и (опционально) `output.debug`, не выдумывая чисел и опираясь только на данные MCP (и RAG при наличии).
- Реализована базовая телеметрия агента (логирование, счётчики LLM-запросов, fallback-ов, latency A2A-запроса).
- Подготовлена и валидирована Agent Card; README/ARCHITECTURE обновлены под фактические компоненты.

## Определение готовности

- Агент развёрнут локально (или в dev-контуре) и корректно обрабатывает базовые сценарии: обзор тикера, сравнение двух тикеров, анализ индекса.
- A2A-контракт полностью соответствует описанию в документации и проходит схематическую валидацию.
- Метрики агента доступны в выбранной системе мониторинга, зарегистрирован факт использования fallback-модели.

## Заметки

Эта задача агрегирует подпункты 2.1–2.8 плана архитектора (Фаза 2).
