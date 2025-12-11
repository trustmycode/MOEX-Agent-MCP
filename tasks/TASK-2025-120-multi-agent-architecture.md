---
id: TASK-2025-120
title: "Архитектура мультиагентности (BaseSubagent, Context, Registry)"
status: planned
priority: critical
type: feature
estimate: 16h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: []
children: [TASK-2025-121, TASK-2025-122, TASK-2025-123]
arch_refs: [ARCH-agent-moex-market-analyst]
risk: medium
benefit: "Создаёт фундамент мультиагентной системы — базовые абстракции для всех сабагентов и оркестратора."
supersedes: [TASK-2025-003, TASK-2025-046, TASK-2025-104]
audit_log:
  - {date: 2025-12-12, user: "@AI-Codex", action: "created as critical P0 task for multi-agent MVP"}
---

## Описание

Создать базовую архитектуру мультиагентной системы для `agent-service`:

- **BaseSubagent** — абстрактный базовый класс для всех сабагентов с единым интерфейсом `execute(context) -> SubagentResult`.
- **AgentContext** — структура данных, передаваемая между агентами (user_query, session_id, intermediate_results, errors, metadata).
- **SubagentRegistry** — реестр всех доступных сабагентов с методами `register()`, `get(name)`, `list_available()`.
- **SubagentResult** — стандартизированный ответ сабагента (status, data, error, next_agent_hint).

## Контекст

Переход от монолитного агента с `Planner` + `ToolOrchestrator` к распределённой системе, где:
- Оркестратор (TASK-122) маршрутизирует запросы
- Рабочие сабагенты (TASK-121) вызывают MCP-tools
- Репортёры (TASK-123) формируют ответ пользователю

## Критерии приёмки

- [ ] Реализован абстрактный класс `BaseSubagent` с методами:
  - `async def execute(self, context: AgentContext) -> SubagentResult`
  - `@property def name(self) -> str`
  - `@property def capabilities(self) -> list[str]`
- [ ] Реализована Pydantic-модель `AgentContext`:
  - `user_query: str`
  - `session_id: str`
  - `user_role: Optional[str]` (CFO, риск-менеджер, аналитик)
  - `scenario_type: Optional[str]` (portfolio_risk, issuer_peers, cfo_liquidity)
  - `intermediate_results: dict[str, Any]`
  - `errors: list[str]`
  - `metadata: dict`
- [ ] Реализована модель `SubagentResult`:
  - `status: Literal["success", "error", "partial"]`
  - `data: Optional[Any]`
  - `error: Optional[str]`
  - `next_agent_hint: Optional[str]`
- [ ] Реализован `SubagentRegistry` (singleton или инжектируемый):
  - `register(subagent: BaseSubagent)`
  - `get(name: str) -> Optional[BaseSubagent]`
  - `list_available() -> list[str]`
- [ ] Написаны unit-тесты для `AgentContext`, `SubagentResult`, `SubagentRegistry`
- [ ] Модули размещены в `packages/agent-service/src/agent_service/core/`

## Определение готовности

- Все сабагенты из TASK-121/122/123 наследуются от `BaseSubagent` и используют `AgentContext`.
- Registry позволяет динамически добавлять/удалять сабагентов без изменения кода оркестратора.
- Тесты проходят, линтеры не ругаются.

## Структура файлов (предлагаемая)

```
packages/agent-service/src/agent_service/
├── core/
│   ├── __init__.py
│   ├── base_subagent.py      # BaseSubagent
│   ├── context.py            # AgentContext
│   ├── result.py             # SubagentResult
│   └── registry.py           # SubagentRegistry
├── subagents/                 # TASK-121, 123
│   ├── __init__.py
│   ├── market_data.py
│   ├── risk_analytics.py
│   ├── explainer.py
│   └── dashboard.py
└── orchestrator/              # TASK-122
    ├── __init__.py
    └── orchestrator_agent.py
```

## Заметки

Это фундамент для TASK-121, 122, 123. Начинать работу над ними можно параллельно, но базовые классы из этой задачи должны быть готовы первыми.
