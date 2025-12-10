---
id: TASK-2025-091
title: "Фаза 2.1.3. Телеметрия и подключение moex_iss_sdk в risk-analytics-mcp"
status: done
priority: medium
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-10
updated: 2025-12-10
parents: [TASK-2025-076]
arch_refs: [ARCH-mcp-risk-analytics, ARCH-sdk-moex-iss]
risk: medium
benefit: "Обеспечивает корректное подключение SDK и базовую телеметрию для risk-analytics-mcp ещё до появления бизнес-логики."
audit_log:
  - {date: 2025-12-10, user: "@AI-DocArchitect", action: "created with status backlog"}
  - {date: 2025-12-10, user: "@codex", action: "marked as done after IssClient wiring, telemetry metrics/tracing, and metrics endpoint implemented for risk-analytics-mcp"}
---

## Описание

Подключить `moex_iss_sdk.IssClient` к `risk-analytics-mcp` через
конфигурацию и инициализацию сервера, а также добавить базовый модуль
телеметрии (счётчики вызовов tools и latency) для будущих инструментов.

## Критерии приемки

- Конфигурация `RiskMcpConfig` создаёт экземпляр `IssClient` и делает
  его доступным tool-хендлерам (через DI/контекст сервера).
- В модуле `telemetry` реализованы базовые счётчики и/или гистограммы
  (`tool_calls_total{tool}`, `tool_errors_total{tool}`, latency),
 экспортируемые через `/metrics`.
- Запуск MCP подтверждает наличие метрик и корректную работу с SDK
  даже при заглушечных инструментах.

## Определение готовности

- Задачи по реализации инструментов (`TASK-2025-077`, `TASK-2025-078`)
  могут фокусироваться на бизнес-логике, используя уже настроенный
  `IssClient` и телеметрию.

## Заметки

- Конкретный стек телеметрии (Prometheus/OTEL) должен быть согласован
  с общими решениями по наблюдаемости в проекте.
