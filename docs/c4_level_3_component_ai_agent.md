# C4 Level 3 — Components: AI Agent (Multi-Agent Architecture)

## 1. Обзор архитектуры

Агент реализован по паттерну **Orchestrator + Subagents**. Каждый сабагент — изолированный компонент с собственным промптом, ответственностью и набором доступных MCP-клиентов.

```mermaid
C4Component
    title C4 Level 3 — Components: AI Agent (Multi-Agent)

    Container_Boundary(agent, "AI Agent (A2A, Python + ADK)") {

        Component(api_adapter, "A2A Adapter", "FastAPI / HTTP handler", "Принимает HTTP/A2A-запросы, валидирует JSON по A2A-схеме, создаёт AgentContext.")

        Component(orchestrator, "OrchestratorAgent", "Python module", "Центральный координатор. Принимает запрос, определяет сценарий через ResearchPlannerSubagent, делегирует задачи сабагентам, агрегирует результаты.")

        Component(agent_registry, "AgentRegistry", "Python module", "Реестр сабагентов. Регистрирует, инициализирует и предоставляет доступ к сабагентам по имени/роли.")

        Component(agent_context, "AgentContext", "Python dataclass", "Разделяемый контекст выполнения: user_query, scenario_type, intermediate_results, errors, telemetry_span.")

        Component(planner_sub, "ResearchPlannerSubagent", "BaseSubagent", "Определяет scenario_type по запросу пользователя, строит план действий.")
        Component(market_sub, "MarketDataSubagent", "BaseSubagent", "Инкапсулирует работу с moex-iss-mcp: котировки, OHLCV, индексы.")
        Component(risk_sub, "RiskAnalyticsSubagent", "BaseSubagent", "Обёртка над risk-analytics-mcp: риск, корреляции, стресс-тесты.")
        Component(dashboard_sub, "DashboardSubagent", "BaseSubagent", "Формирует RiskDashboardSpec для UI/AGI UI.")
        Component(explainer_sub, "ExplainerSubagent", "BaseSubagent", "Генерирует текстовый отчёт для CFO/риск-менеджера.")
        Component(knowledge_sub, "KnowledgeSubagent", "BaseSubagent", "Работает с kb-rag-mcp: методики, регламенты, новости.")

        Component(mcp_client_moex, "MCP Client (moex-iss)", "FastMCP client", "Инкапсулирует протокол MCP для moex-iss-mcp.")
        Component(mcp_client_risk, "MCP Client (risk-analytics)", "FastMCP client", "Инкапсулирует протокол MCP для risk-analytics-mcp.")
        Component(mcp_client_rag, "MCP Client (kb-rag)", "FastMCP client", "Инкапсулирует протокол MCP для kb-rag-mcp.")

        Component(llm_client, "LLM Client", "HTTP client to FM", "Обёртка над Foundation Models API: /chat/completions.")

        Component(telemetry, "Telemetry Adapter", "Phoenix / OTEL client", "Отправляет трейсы, метрики и логи.")
    }

    Rel(api_adapter, orchestrator, "Передаёт AgentContext")
    Rel(api_adapter, agent_context, "Создаёт AgentContext")
    Rel(api_adapter, telemetry, "Логирует запрос/ответ")

    Rel(orchestrator, agent_registry, "Получает сабагентов")
    Rel(orchestrator, planner_sub, "Определение сценария")
    Rel(orchestrator, market_sub, "Запрос данных")
    Rel(orchestrator, risk_sub, "Запрос риск-аналитики")
    Rel(orchestrator, dashboard_sub, "Формирование дашборда")
    Rel(orchestrator, explainer_sub, "Генерация отчёта")
    Rel(orchestrator, knowledge_sub, "Запрос к RAG")

    Rel(market_sub, mcp_client_moex, "MCP calls")
    Rel(risk_sub, mcp_client_risk, "MCP calls")
    Rel(knowledge_sub, mcp_client_rag, "MCP calls")

    Rel(planner_sub, llm_client, "LLM для плана")
    Rel(explainer_sub, llm_client, "LLM для текста")

    Rel(orchestrator, telemetry, "Span: orchestrator")
    Rel(mcp_client_moex, telemetry, "Логирует MCP")
```

---

## 2. Описание компонентов

### 2.1. A2A Adapter

**Ответственность:**

- Единственная точка входа для HTTP/A2A-запросов.
- Валидация входящего JSON по A2A-схеме.
- Создание `AgentContext` и передача в `OrchestratorAgent`.
- Логирование запросов/ответов через Telemetry.

### 2.2. OrchestratorAgent

**Ответственность:**

- Центральный координатор мультиагентной системы.
- Получает `AgentContext`, вызывает `ResearchPlannerSubagent` для определения сценария.
- Делегирует задачи соответствующим сабагентам согласно плану.
- Агрегирует результаты и формирует финальный A2A-ответ.
- Обрабатывает ошибки сабагентов, обеспечивает graceful degradation.

**Не делает:**

- Не вызывает MCP напрямую (только через сабагентов).
- Не генерирует текст напрямую через LLM (только через сабагентов).

### 2.3. AgentRegistry

**Ответственность:**

- Хранит реестр зарегистрированных сабагентов.
- Инициализирует сабагентов с нужными зависимостями (MCP-клиенты, LLM-клиент).
- Предоставляет доступ к сабагентам по имени/роли.

### 2.4. AgentContext

**Ответственность:**

- Разделяемый контекст выполнения запроса.
- Содержит: `user_query`, `locale`, `user_role`, `scenario_type`, `plan`, `intermediate_results`, `errors`, `telemetry_span`.
- Передаётся между Orchestrator и Subagents.

---

## 3. Сабагенты (Subagents)

### 3.1. ResearchPlannerSubagent

**Роль:** Планировщик сценария.

**Ответственность:**

- Анализирует `user_query` и определяет `scenario_type` (single_security_overview, compare_securities, portfolio_risk_basic и т.д.).
- Строит план действий: какие сабагенты вызвать, в каком порядке.
- Валидирует ограничения (глубина истории, количество тикеров).

**Зависимости:** LLM Client.

### 3.2. MarketDataSubagent

**Роль:** Провайдер рыночных данных.

**Ответственность:**

- Инкапсулирует всю работу с `moex-iss-mcp`.
- Вызывает tools: `get_security_snapshot`, `get_ohlcv_timeseries`, `get_index_constituents_metrics`.
- Следит за правилами по датам (дефолты, MAX_LOOKBACK_DAYS).
- Нормализует ошибки ISS.

**Зависимости:** MCP Client (moex-iss).

### 3.3. RiskAnalyticsSubagent

**Роль:** Риск-аналитика.

**Ответственность:**

- Обёртка над `risk-analytics-mcp`.
- Вызывает tools: `compute_portfolio_risk_basic`, `compute_correlation_matrix`, `suggest_rebalance`, `build_cfo_liquidity_report`.
- Валидирует входные позиции, обрабатывает ошибки.

**Зависимости:** MCP Client (risk-analytics).

### 3.4. DashboardSubagent

**Роль:** Формирование UI-дашборда.

**Ответственность:**

- Собирает данные от MarketDataSubagent и RiskAnalyticsSubagent.
- Формирует структурированный JSON `RiskDashboardSpec` для `output.dashboard`.
- Определяет виджеты, метрики, графики, alerts.

**Зависимости:** (опционально) LLM Client для генерации структуры.

### 3.5. ExplainerSubagent

**Роль:** Генерация текстового отчёта.

**Ответственность:**

- Генерирует человекочитаемый `output.text` для разных ролей (CFO, риск-менеджер, аналитик).
- Интерпретирует метрики и данные дашборда.
- Объединяет численные данные и RAG-контекст (если доступен).

**Зависимости:** LLM Client, (опционально) данные от KnowledgeSubagent.

### 3.6. KnowledgeSubagent

**Роль:** Провайдер знаний (RAG).

**Ответственность:**

- Тонкий слой над `kb-rag-mcp`.
- Формирует запросы к базе знаний с учётом сценария и роли пользователя.
- Возвращает snippets (методики, регламенты, новости) для ExplainerSubagent.

**Зависимости:** MCP Client (kb-rag).

---

## 4. MCP Clients

Каждый MCP-клиент:

- Инкапсулирует протокол MCP (streamable-http).
- Управляет тайм-аутами и ретраями.
- Логирует вызовы через Telemetry.
- Маппит исключения в нормализованные ошибки.

| MCP Client      | Сервер             | Используется          |
| --------------- | ------------------ | --------------------- |
| mcp_client_moex | moex-iss-mcp       | MarketDataSubagent    |
| mcp_client_risk | risk-analytics-mcp | RiskAnalyticsSubagent |
| mcp_client_rag  | kb-rag-mcp         | KnowledgeSubagent     |

---

## 5. Поток выполнения (пример: portfolio_risk_basic)

```
1. A2A Adapter получает запрос → создаёт AgentContext
2. OrchestratorAgent получает AgentContext
3. OrchestratorAgent → ResearchPlannerSubagent: определить сценарий
   → scenario_type = "portfolio_risk_basic"
   → plan = [RiskAnalytics → Dashboard → (опц.) Knowledge → Explainer]
4. OrchestratorAgent → RiskAnalyticsSubagent: compute_portfolio_risk_basic
   → RiskAnalyticsSubagent → MCP Client (risk) → risk-analytics-mcp
   → результат в AgentContext.intermediate_results
5. OrchestratorAgent → DashboardSubagent: сформировать RiskDashboardSpec
   → результат в AgentContext.intermediate_results["dashboard"]
6. (Опционально) OrchestratorAgent → KnowledgeSubagent: получить методики
   → результат в AgentContext.intermediate_results["rag_snippets"]
7. OrchestratorAgent → ExplainerSubagent: сгенерировать output.text
8. OrchestratorAgent агрегирует: output.text + output.dashboard
9. A2A Adapter возвращает A2A-ответ
```
