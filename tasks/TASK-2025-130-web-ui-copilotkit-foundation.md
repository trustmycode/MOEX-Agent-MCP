---
id: TASK-2025-130
title: "Инициализация Web UI с CopilotKit (Foundation)"
status: backlog
priority: high
type: feature
estimate: 8h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-006]
children: [TASK-2025-131, TASK-2025-132]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: low
benefit: "Создаёт каркас веб-приложения с готовым чат-интерфейсом, готовым к подключению агента."
audit_log:
  - {date: 2025-12-12, user: "@AI-Architect", action: "created"}
---

## Описание

Развернуть базовое Next.js приложение и настроить интеграцию с **CopilotKit**. Это обеспечит стандартный интерфейс чата (CopilotSidebar/CopilotPopup) и инфраструктуру для подключения к нашему `agent-service`.

## Контекст

Мы используем подход **Agentic UI**. Вместо написания кастомного чата с нуля, мы используем `CopilotKit` для управления состоянием диалога, стриминга сообщений и (в будущем) рендеринга Generative UI.

## Ссылки на документацию фреймворков

https://docs.ag-ui.com/introduction
https://docs.ag-ui.com/drafts/generative-ui
https://www.copilotkit.ai/

## Критерии приёмки

### Setup
- [ ] Инициализирован проект Next.js 14+ (App Router) + Tailwind CSS.
- [ ] Установлены зависимости `@copilotkit/react-core`, `@copilotkit/react-ui`.

### Copilot Configuration
- [ ] Настроен `<CopilotKit />` провайдер в корне приложения.
- [ ] Реализован `runtimeUrl` (или `CopilotRuntime`), который проксирует запросы к нашему `agent-service` (OrchestratorAgent).
  - *Примечание:* Так как наш агент работает по протоколу A2A, может потребоваться легкий API Route в Next.js для адаптации формата CopilotKit <-> A2A Input/Output.

### UI Skeleton
- [ ] На главной странице добавлен `<CopilotSidebar />` (или аналог), занимающий правую часть экрана.
- [ ] Левая/центральная часть экрана зарезервирована под "Canvas" (место, где будет отрисовываться Risk Dashboard).

## Определение готовности

- Приложение запускается локально (`npm run dev`).
- Виден интерфейс чата.
- Можно отправить текстовое сообщение, оно уходит на бэкенд (даже если пока возвращает mock-ответ).

## Структура файлов

```text
apps/web/
├── app/
│   ├── api/copilot/route.ts  # Proxy to Agent Service
│   ├── page.tsx              # Main layout with Canvas + Chat
│   └── layout.tsx            # CopilotKit Provider
├── components/
│   └── ...
└── package.json
```
