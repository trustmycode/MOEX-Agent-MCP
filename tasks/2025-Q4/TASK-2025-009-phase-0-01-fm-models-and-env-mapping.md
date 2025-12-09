---
id: TASK-2025-009
title: "Фаза 0.1. FM-модели и ENV mapping"
status: backlog
priority: high
type: chore
estimate: 4h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-001]
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: low
benefit: "Убирает двусмысленности по выбору моделей и fallback-логике между REQUIREMENTS и ARCHITECTURE."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Обновить `REQUIREMENTS_moex-market-analyst-agent.md` и `ARCHITECTURE.md`, зафиксировав финальный выбор Foundation Models (`LLM_MODEL_MAIN`, `LLM_MODEL_FALLBACK`, `LLM_MODEL_DEV`) и правила выбора модели по `ENVIRONMENT` (`dev`/`prod`) с явной fallback-логикой.

## Критерии приемки

- В REQUIREMENTS есть отдельный раздел «Выбор моделей FM и fallback-логика» с перечислением:
  - `LLM_MODEL_MAIN = Qwen3-235B`;
  - `LLM_MODEL_FALLBACK = gpt-oss-120b`;
  - `LLM_MODEL_DEV = GigaChat3-10B`;
  - правил:
    - `ENVIRONMENT=dev` → GigaChat3-10B;
    - `ENVIRONMENT=prod` → Qwen3-235B, при ошибках — fallback на gpt-oss-120b.
- В ARCHITECTURE нет формулировок вида «выбираем модель позже» или противоречий с REQUIREMENTS.
- Везде, где упоминаются LLM в документации, используется согласованный FM-стек.

## Определение готовности

- Из документации однозначно понятно, какие модели используются в dev/prod и как работает fallback.
- Команда разработки и эксперты по платформе подтверждают отсутствие открытых вопросов по конфигурации моделей.

## Заметки

Исходные формулировки берутся из плана архитектора (Фаза 0, задача 0.1) и Q&A по хакатону.

