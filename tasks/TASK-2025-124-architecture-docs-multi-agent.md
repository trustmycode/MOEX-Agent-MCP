---
id: TASK-2025-124
title: "Полное обновление архитектурной документации (Multi-Agent)"
status: done
priority: medium
type: chore
estimate: 6h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-122]
children: []
arch_refs: [ARCH-agent-moex-market-analyst]
risk: low
benefit: "Устраняет технический долг в документации, синхронизируя C4-диаграммы всех уровней и требования с реализованной мультиагентной архитектурой."
audit_log:
  - {date: 2025-12-12, user: "@AI-Architect", action: "created"}
  - {date: 2025-12-11, user: "@AI-Agent", action: "completed — all architecture docs updated for multi-agent pattern"}
---

## Описание

Текущая документация описывает монолитную архитектуру агента (`Planner` + `ToolOrchestrator`). Реализация перешла на паттерн **Orchestrator + Subagents**. Необходимо обновить все архитектурные артефакты, чтобы они отражали реальное устройство системы.

## Объём работ

### 1. Обновление C4 Диаграмм

- **`docs/c4_level_1_system_context.md`**:
  - Обновить описание System: "Multi-Agent System" вместо "AI Agent".
- **`docs/ARCHITECTURE.md` (C4 Level 2)**:
  - Обновить контейнерную диаграмму. Контейнер "AI Agent" теперь логически состоит из набора сабагентов.
  - Обновить текстовое описание архитектуры: явно прописать паттерн Orchestrator-Workers.
- **`docs/c4_level_3_component_ai_agent.md` (Components)**:
  - **Удалить:** `Planner`, `Tool Orchestrator`, `Response Formatter` (как отдельные компоненты).
  - **Добавить:** `Orchestrator Agent`, `MarketData Subagent`, `RiskAnalytics Subagent`, `Dashboard Subagent`, `Explainer Subagent`.
  - Показать связи: Сабагенты <--> MCP Клиенты.
- **`docs/c4_level_4_code_ai_agent.md` (Code/Classes)**:
  - **Полная переработка.**
  - Описать новые классы: `BaseSubagent`, `OrchestratorAgent`, `AgentContext`, `AgentRegistry`.
  - Удалить описание классов старого планировщика.

### 2. Обновление Требований и Сценариев

- **`docs/REQUIREMENTS_moex-market-analyst-agent.md`**:
  - Обновить раздел "Архитектура": указать требование на мультиагентность.
  - Уточнить NFR (Non-Functional Requirements): управление контекстом, изоляция промптов.
- **`docs/SCENARIOS_PORTFOLIO_RISK.md`**:
  - Обновить Sequence Diagrams. Вместо `Agent -> MCP` показать цепочку `User -> Orchestrator -> RiskSubagent -> MCP`.

### 3. Проверка MCP документации

- Проверить `docs/c4_level_3_component_mcp_moex.md` и `docs/c4_level_4_code_mcp_moex.md`.
  - *Примечание:* Внутренняя структура MCP скорее всего не изменилась, но нужно убедиться, что описание потребителей (Consumers) соответствует новым сабагентам (например, "Используется MarketData Subagent").

## Критерии приемки

- [x] Диаграмма C4 L3 показывает 5 отдельных компонентов-агентов вместо одного монолита.
- [x] Диаграмма C4 L4 описывает иерархию классов `BaseSubagent`.
- [x] Sequence Diagram в сценариях отражает передачу управления между Оркестратором и Сабагентами.
- [x] В `REQUIREMENTS` зафиксирован отказ от монолитного планировщика в пользу специализированных ролей.
