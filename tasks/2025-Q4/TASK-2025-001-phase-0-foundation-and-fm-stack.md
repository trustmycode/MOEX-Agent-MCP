---
id: TASK-2025-001
title: "Фаза 0. Требования и стек моделей"
status: backlog
priority: high
type: chore
estimate: 8h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
arch_refs: [ARCH-agent-moex-market-analyst, ARCH-mcp-moex-iss]
risk: low
benefit: "Синхронизация требований, архитектуры и SPEC с финальным выбором FM-стека и правил по датам."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Зафиксировать финальный выбор Foundation Models и общие правила работы с датами, глубиной истории и индексами во всех ключевых документах (`REQUIREMENTS_moex-market-analyst-agent.md`, `ARCHITECTURE.md`, `SPEC_moex-iss-mcp.md`), чтобы убрать двусмысленности между архитектурой и реализацией.

## Критерии приемки

- В требованиях и архитектуре явно перечислены модели:
  - `LLM_MODEL_MAIN = Qwen3-235B`;
  - `LLM_MODEL_FALLBACK = gpt-oss-120b`;
  - `LLM_MODEL_DEV = GigaChat3-10B`;
  - описано правило выбора модели по `ENVIRONMENT=dev/prod` и fallback‑логика.
- В SPEC/REQUIREMENTS формализовано поведение по датам:
  - значения по умолчанию (`to_date = today`, `from_date = to_date - 365 дней`);
  - лимит `MAX_LOOKBACK_DAYS = 730`;
  - ошибка `DATE_RANGE_TOO_LARGE` при превышении лимита.
- В SPEC описан маппинг `index_ticker → indexid`, кэш на 24 часа и ошибка `UNKNOWN_INDEX`.

## Определение готовности

- Обновлены и провалидированы все целевые документы без конфликтов между собой.
- В коде (по мере появления реализации) используются те же константы и правила, что и в документации.
- Команда разработки подтверждает, что по выбору моделей и правилам по датам/индексам нет открытых вопросов.

## Заметки

Исходник требований и уточнений — Q&A по хакатону и итоговый план архитектора (Фаза 0, задачи 0.1–0.3).

