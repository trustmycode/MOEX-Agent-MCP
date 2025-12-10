# ARCHITECTURE_LOW_LEVEL

## Связь low-level компонентов с JSON-схемами MCP Risk Analytics

### MCP-сервер `risk-analytics-mcp`

Компоненты MCP-сервера для работы со сценариями портфельного риска, ликвидности и ребалансировки используют формальные JSON-контракты, описанные в:

- [SCENARIOS_PORTFOLIO_RISK.md](./SCENARIOS_PORTFOLIO_RISK.md)

#### Контракты входа/выхода

- **PortfolioRiskInput** / **PortfolioRiskReport**  

  Используются в обработчике инструмента `analyze_portfolio_risk`.

- **RebalanceInput** / **RebalanceProposal**  

  Используются в обработчике инструмента `propose_rebalance_trades`.

- **CfoLiquidityReportInput** / **CfoLiquidityReport**  

  Используются в обработчике инструмента `build_cfo_liquidity_report`.

#### Использование схем в коде

- В слое адаптеров MCP-сервера необходимо валидировать входящие JSON-payloads по соответствующим схемам до передачи в доменную логику.

- В доменном слое выходные DTO должны маппиться 1-в-1 на структуры, описанные в схемах (названия полей, типы, обязательность).

- Авто-тесты контролируют соответствие фактических ответов схемам, чтобы не ломать контракты при изменении реализации.
