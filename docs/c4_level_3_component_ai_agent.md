```mermaid
C4Component
    title C4 Level 3 — Components: AI Agent (A2A)

    Container_Boundary(agent, "AI Agent (A2A, Python + ADK)") {

        Component(api_adapter, "A2A Adapter", "FastAPI / HTTP handler", "Принимает HTTP/A2A-запросы, валидирует JSON по A2A-схеме, преобразует в внутреннюю модель запроса.")

        Component(session_mgr, "Session & Context Manager", "Python module", "Управляет контекстом сессии, хранит историю сообщений (ограниченно), подготавливает промпт для FM с учётом предыдущих запросов.")

        Component(planner, "Planner", "LLM-powered planning", "Формулирует план действий: какие MCP tools вызвать, в каком порядке, с какими аргументами. Работает через FM.")

        Component(tool_orchestrator, "Tool Orchestrator", "Python module", "Исполняет план: вызывает MCP-инструменты, агрегирует результаты, обрабатывает ошибки и ретраи.")

        Component(mcp_client, "MCP Client", "FastMCP client", "Инкапсулирует протокол MCP и вызовы tools на moex-iss-mcp и других MCP. Следит за тайм-аутами, логирует результаты.")

        Component(llm_client, "FM Client", "HTTP client to FM", "Обёртка над Foundation Models API: /chat/completions, управление параметрами генерации (model, temperature, max_tokens).")

        Component(response_formatter, "Response Formatter", "Python module", "Преобразует результаты MCP и вывод FM в A2A-ответ: text + tables + debug. Следит за размером ответа и структурой JSON.")

        Component(telemetry, "Telemetry Adapter", "Phoenix / OTEL client", "Отправляет трейсы, метрики и логи в Phoenix/Prometheus/OTEL. Не содержит бизнес-логики.")
    }

    Rel(api_adapter, session_mgr, "Передаёт нормализованный запрос и контекст")
    Rel(session_mgr, planner, "Передаёт NL-запрос и контекст для построения плана")
    Rel(planner, llm_client, "Вызывает FM для генерации плана")
    Rel(planner, tool_orchestrator, "Передаёт план действий (список tool-вызовов)")
    Rel(tool_orchestrator, mcp_client, "Запрашивает выполнение MCP tools")
    Rel(mcp_client, telemetry, "Логирует вызовы MCP и ошибки")
    Rel(tool_orchestrator, response_formatter, "Передаёт сырые данные/метрики для упаковки")
    Rel(response_formatter, api_adapter, "Возвращает готовый A2A-ответ")
    Rel(api_adapter, telemetry, "Логирует запрос/ответ и технические метрики")
```

**Кратко по компонентам:**

- **A2A Adapter** — слой интеграции с платформой (HTTP + JSON, A2A протокол).
- **Planner** — единственное место, где мы используем FM для «reasoning» по плану (минимизируем число LLM-вызовов).
- **Tool Orchestrator + MCP Client** — вся работа с tools, включая обработку ошибок и ретраи, чтобы не засорять агента.
- **Response Formatter** — изолирует «как показать результат пользователю» от «как мы считаем данные».
