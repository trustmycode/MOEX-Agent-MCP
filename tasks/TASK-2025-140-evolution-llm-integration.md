---
id: TASK-2025-140
title: "Интеграция с Evolution Foundation Models (Real LLM)"
status: backlog
priority: critical
type: feature
estimate: 6h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-123]
children: []
arch_refs: [ARCH-agent-moex-market-analyst]
risk: high
benefit: "Заменяет Mock-генерацию текста на реальный интеллект, позволяя агенту давать осмысленные объяснения и рекомендации."
audit_log:
  - {date: 2025-12-12, user: "@AI-Architect", action: "created"}
---

## Описание

Реализовать `EvolutionLLMClient` в `agent-service`, который заменяет текущий `MockLLMClient`. Клиент должен использовать API Cloud.ru Foundation Models (OpenAI-compatible) для генерации текста в `ExplainerSubagent` и классификации интентов в `IntentClassifier` (опционально).

## Контекст

Сейчас `ExplainerSubagent` возвращает шаблонный текст. Для сдачи проекта необходимо подключение к реальной LLM. Согласно документации Cloud.ru, используется endpoint `https://foundation-models.api.cloud.ru/v1`.

## Ссылки на документацию
https://cloud.ru/docs/foundation-models/ug/topics/guides?source-platform=Evolution
https://cloud.ru/docs/ai-agents/ug/topics/concepts__variables-mcp-server?source-platform=Evolution

## Критерии приёмки

### Реализация клиента
- [ ] Создан класс `EvolutionLLMClient`, реализующий протокол `LLMClient`.
- [ ] Используется библиотека `openai` (python) для запросов.
- [ ] Конфигурация через ENV:
  - `LLM_API_BASE`: `https://foundation-models.api.cloud.ru/v1`
  - `LLM_API_KEY`: (Secret)
  - `LLM_MODEL`: (по требованиям в ARCHITECTURE.md).

### Логика работы
- [ ] Реализован метод `generate(system_prompt, user_prompt)`.
- [ ] Добавлена обработка ошибок (Rate Limit, 5xx) с простым ретраем (backoff).
- [ ] Поддержка переключения моделей (Dev/Prod) через переменные окружения.

### Интеграция
- [ ] В `AgentRegistry` (или `config.py`) логика инициализации заменена с `MockLLMClient` на `EvolutionLLMClient` при наличии API ключа.

## Определение готовности

- При запуске агента с валидным `LLM_API_KEY`, запрос "Объясни риск портфеля" возвращает уникальный текст, сгенерированный моделью, а не хардкод.

## Ссылки

- [Документация Foundation Models](https://cloud.ru/docs/foundation-models/ug/topics/guides?source-platform=Evolution)
