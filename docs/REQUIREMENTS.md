# REQUIREMENTS

## Функциональные требования: связь с JSON-схемами

### FR-PRISK-JSON-01

Все запросы/ответы по сценариям анализа портфельного риска, предложений по ребалансировке и отчётов для CFO должны соответствовать JSON-контрактам, описанным в:

- [SCENARIOS_PORTFOLIO_RISK.md](./SCENARIOS_PORTFOLIO_RISK.md)

### FR-PRISK-JSON-02

Клиентские слои (UI, внешние API) обязаны использовать те же структуры данных, что и MCP-сервер `risk-analytics-mcp`:

- **PortfolioRiskInput**

- **PortfolioRiskReport**

- **RebalanceInput**

- **RebalanceProposal**

- **CfoLiquidityReportInput**

- **CfoLiquidityReport**

### FR-PRISK-JSON-03

`ScenarioTemplate` в планировщике агента должен ссылаться на те же схемы (`PortfolioRiskInput/Report`, `RebalanceInput/Proposal`, `CfoLiquidityReportInput/Report`), что использует `risk-analytics-mcp`, чтобы исключить рассинхрон UX/API ↔ MCP.

### FR-PRISK-JSON-04

`risk-analytics-mcp` получает рыночные данные только через `moex-iss-mcp` (data-provider), сохраняя единую точку контроля лимитов и ошибок ISS.

## Нефункциональные требования: управляемость контрактов

### NFR-JSON-SCHEMA-01

JSON-схемы для MCP-инструментов должны рассматриваться как единый источник правды (SSOT) для:

- генерации клиентских моделей (типизация, SDK),

- валидации входных и исходящих сообщений,

- авто-тестов контрактов.

### NFR-JSON-SCHEMA-02

Любые изменения в схемах, описанных в [SCENARIOS_PORTFOLIO_RISK.md](./SCENARIOS_PORTFOLIO_RISK.md), должны сопровождаться:

- обновлением соответствующих частей архитектурной документации (`ARCHITECTURE_*`),

- миграцией/обновлением авто-тестов и проверкой обратной совместимости (backward compatibility), если это критично для продакшн-интеграций.

### NFR-JSON-SCHEMA-03

- Валидация входов/выходов `risk-analytics-mcp` выполняется на уровне адаптера по JSON Schema/Pydantic до доменной логики.
- Доменные DTO маппятся 1-в-1 на схемы; контрактные тесты фиксируют соответствие и должны падать при любом расхождении.
