---
id: TASK-2025-020
title: "Фаза 2.1. Config и LlmClient"
status: backlog
priority: high
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-003]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Даёт централизованную конфигурацию агента и клиента LLM с поддержкой MAIN/FALLBACK/DEV."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Реализовать модуль конфигурации агента (`Config`) и клиента Foundation Models (`LlmClient`) с выбором модели по `ENVIRONMENT` и fallback-логикой при временных ошибках основной модели.

## Критерии приемки

- `Config.from_env()` загружает:
  - `ENVIRONMENT`, `LLM_API_BASE`, `LLM_MODEL_MAIN`, `LLM_MODEL_FALLBACK`, `LLM_MODEL_DEV`;
  - ключ/секрет для доступа к Foundation Models;
  - параметры генерации (`temperature`, `max_tokens` и т.п.).
- `LlmClient` умеет:
  - выбирать модель в зависимости от `ENVIRONMENT` (dev → `LLM_MODEL_DEV`, prod → `LLM_MODEL_MAIN`);
  - при transient-ошибках основной модели в prod переходить на `LLM_MODEL_FALLBACK` с логированием события.
- Есть unit-тесты, проверяющие выбор модели и корректность fallback-поведения на смоделированных ошибках.

## Определение готовности

- Остальные компоненты агента могут использовать `LlmClient` как единый интерфейс к Foundation Models.
- Поведение по выбору и резервированию моделей соответствует требованиям Фазы 0.

## Заметки

Соответствует пункту 2.1 плана архитектора (Фаза 2).

