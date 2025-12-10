# ARCHITECTURE_HIGH_LEVEL

## Связанные бизнес-сценарии и JSON-схемы

### Анализ портфельного риска, ликвидности и ребалансировки

Данный сценарий описан в отдельном документе:

- [SCENARIOS_PORTFOLIO_RISK.md](./SCENARIOS_PORTFOLIO_RISK.md)

В этом документе зафиксированы формальные JSON-контракты для MCP-инструментов `risk-analytics-mcp`:

- **PortfolioRiskInput** — входной контракт для `analyze_portfolio_risk`

- **PortfolioRiskReport** — выходной контракт для `analyze_portfolio_risk`

- **RebalanceInput** — входной контракт для `propose_rebalance_trades`

- **RebalanceProposal** — выходной контракт для `propose_rebalance_trades`

- **CfoLiquidityReportInput** — входной контракт для `build_cfo_liquidity_report`

- **CfoLiquidityReport** — выходной контракт для `build_cfo_liquidity_report`

Архитектура AI-агента и MCP-слоя должна рассматриваться совместно с этими схемами как с источником правды (single source of truth) для всех интеграций:

- UX/API → JSON-контракты → MCP-сервер `risk-analytics-mcp`

- Авто-тесты и валидация запросов/ответов также опираются на эти схемы.
