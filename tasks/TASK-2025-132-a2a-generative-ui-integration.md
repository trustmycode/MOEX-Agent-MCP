---
id: TASK-2025-132
title: "Интеграция A2A с Generative UI (Render Loop)"
status: backlog
priority: critical
type: feature
estimate: 12h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-131, TASK-2025-122]
children: []
arch_refs: [ARCH-agent-moex-market-analyst]
risk: high
benefit: "Связывает 'мозги' (Агент) и 'лицо' (UI). Агент сам вызывает отрисовку дашборда в интерфейсе."
audit_log:
  - {date: 2025-12-12, user: "@AI-Architect", action: "created"}
---

## Описание

Настроить механизм **Generative UI** в CopilotKit. Когда `OrchestratorAgent` возвращает ответ с полем `output.dashboard`, фронтенд должен автоматически отрисовать компонент `RiskCockpit` в основной области экрана (Canvas) или внутри чата.

## Контекст

В терминах CopilotKit/Generative UI, агент "вызывает инструмент" (tool calling) или возвращает структурированный ответ, который фронтенд интерпретирует как команду "render UI".

## Ссылки на документацию фреймворков

https://docs.ag-ui.com/introduction
https://docs.ag-ui.com/drafts/generative-ui
https://www.copilotkit.ai/

## Критерии приёмки

### Backend Adapter (Next.js API Route)
- [ ] Адаптер преобразует ответ `OrchestratorAgent` (`A2AOutput`):
  - `output.text` -> отправляется как сообщение чата.
  - `output.dashboard` -> передается как пропсы для Generative UI компонента.

### Client-side Integration (`useCopilotChat` / `useCopilotAction`)
- [ ] Настроен `useCopilotReadable` (опционально) для передачи контекста страницы агенту.
- [ ] Реализован рендеринг:
  - **Вариант А (Custom Message):** Если в ответе есть дашборд, рендерим кастомный message component в чате.
  - **Вариант Б (Canvas/Sidebar - Рекомендуемый):** Если в ответе есть дашборд, обновляем состояние `dashboardData` в React Context, и компонент `RiskCockpit` в центре экрана перерисовывается.

### End-to-End Flow
- [ ] Пользователь пишет: "Оцени риск портфеля SBER 100%".
- [ ] Агент думает...
- [ ] В чате появляется текст: "Вот анализ вашего портфеля. Обнаружена высокая концентрация...".
- [ ] **Одновременно** в центре экрана появляется красивый дашборд с графиками и алертами.

## Определение готовности

- Работает полный цикл: Запрос -> Агент -> JSON -> UI Component.
- Нет "мигания" или ошибок при парсинге JSON.
- Если агент вернул ошибку, UI показывает тост/сообщение об ошибке, а не ломает верстку.

## Заметки

Использовать возможности CopilotKit для стриминга (если агент поддерживает стриминг JSON), чтобы графики появлялись по мере генерации данных (nice-to-have).
