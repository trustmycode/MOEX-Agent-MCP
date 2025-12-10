---
id: TASK-2025-018
title: "Фаза 1.7. Телеметрия MCP и /metrics"
status: done
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-02-11
parents: [TASK-2025-002]
arch_refs: [ARCH-mcp-moex-iss]
risk: medium
benefit: "Добавляет наблюдаемость по MCP-инструментам: счётчики вызовов, ошибок и латентности."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-02-11, user: "@AI-Codex", action: "status changed to done"}
---

## Описание

Реализовать телеметрию MCP: счётчики вызовов и ошибок по инструментам, гистограмму латентности и HTTP-endpoint `/metrics` в формате Prometheus, а также интеграцию с OTEL при необходимости.

## Критерии приемки

- В коде MCP есть модуль метрик с:
  - `tool_calls_total{tool}`;
  - `tool_errors_total{tool,error_type}`;
  - `mcp_http_latency_seconds{tool}`.
- Endpoint `/metrics` отдаёт актуальные значения счётчиков и гистограмм, совместимые с Prometheus.
- Ошибки инструментов увеличивают соответствующие метрики `tool_errors_total`.
- При включённой OTEL-интеграции формируются трейсы для входящих MCP-вызовов (по возможности).

## Определение готовности

- В среде разработки можно подключить Prometheus/Grafana и наблюдать нагрузку и ошибки MCP.
- Телеметрия используется в smoke- и нагрузочных тестах для контроля качества.

## Заметки

Соответствует пункту 1.7 плана архитектора (Фаза 1).
