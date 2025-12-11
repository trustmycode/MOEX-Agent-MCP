```mermaid
C4Context
    title C4 Level 1 — System Context: moex-market-analyst-agent (Multi-Agent System)

    Person(user, "Бизнес-пользователь", "CFO, риск-менеджер, инвестиционный аналитик")

    System_Boundary(sys, "moex-market-analyst-agent (в Cloud.ru Evolution AI Agents)") {
        System(agent_system, "moex-market-analyst-agent (Multi-Agent)", "Мультиагентная система (Orchestrator + Subagents), развёрнутая в Evolution AI Agents. Анализирует рынок Мосбиржи и выдаёт отчёты.")
    }

    System_Ext(fm, "Evolution Foundation Models", "Cloud.ru Foundation Models API", "LLM, используемая агентами через https://foundation-models.api.cloud.ru/v1.")
    System_Ext(moex, "MOEX ISS API", "Публичный HTTP JSON API", "Источник рыночных данных (котировки, история, индексы).")
    System_Ext(rag, "Дополнительные MCP (RAG/KB)", "MCP-серверы из каталога", "Опциональные источники текстовых знаний (методички, регламенты).")

    Rel(user, agent_system, "Задает вопросы на естественном языке и получает отчёты", "HTTP + JSON (A2A UI / интеграции)")
    Rel(agent_system, fm, "Запросы /chat/completions от Orchestrator и Subagents", "HTTPS, LLM_API_BASE=https://foundation-models.api.cloud.ru/v1")
    Rel(agent_system, moex, "Получает данные рынка через MCP (MarketDataSubagent → moex-iss-mcp)", "MCP → HTTP JSON")
    Rel(agent_system, rag, "Запросы к базе знаний (KnowledgeSubagent → kb-rag-mcp)", "MCP")
```

---

## Пояснение к мультиагентной архитектуре

С точки зрения внешнего мира (A2A-протокол, Agent Card) существует **один агент** `moex-market-analyst-agent`.  
Внутри он реализован по паттерну **Orchestrator + Subagents**, где:

- **OrchestratorAgent** — координирует выполнение сценария, делегирует задачи сабагентам.
- **Subagents** — специализированные агенты с изолированными промптами и ответственностью:
  - `ResearchPlannerSubagent` — определяет тип сценария и строит план.
  - `MarketDataSubagent` — работает с `moex-iss-mcp`.
  - `RiskAnalyticsSubagent` — работает с `risk-analytics-mcp`.
  - `DashboardSubagent` — формирует `RiskDashboardSpec`.
  - `ExplainerSubagent` — генерирует текстовый отчёт.
  - `KnowledgeSubagent` — работает с `kb-rag-mcp`.

Такая архитектура обеспечивает:
- изоляцию промптов и контекста между задачами;
- лучшую управляемость и тестируемость отдельных ролей;
- возможность независимого масштабирования и развития сабагентов.