# Обзор архитектуры moex-market-analyst-agent

Этот раздел фиксирует связку между высокоуровневой архитектурой из `docs/` и
детализированными архитектурными описаниями в каталоге `architecture/`.

Актуальные компоненты системы описаны четырьмя основными архитектурными
артефактами:

- `architecture/agent/ARCH-agent-moex-market-analyst-v1.md` — AI‑агент
  `moex-market-analyst-agent` (A2A‑сервис в Evolution AI Agents), который:
  принимает NL‑запросы, использует Foundation Models, вызывает MCP‑серверы и
  реализует планировщик сценариев 5/7/9 (`issuer_peers_compare`,
  `portfolio_risk`, `cfo_liquidity_report`).

- `architecture/mcp/ARCH-mcp-moex-iss-v1.md` — MCP‑сервер `moex-iss-mcp`,
  единственная точка доступа агента и других сервисов к MOEX ISS API. Даёт
  бизнес‑ориентированные инструменты (`get_security_snapshot`,
  `get_ohlcv_timeseries`, `get_index_constituents_metrics` и будущие
  расширения), опираясь на общий SDK `moex_iss_sdk`.

- `architecture/mcp/ARCH-mcp-risk-analytics-v1.md` — MCP‑сервер
  `risk-analytics-mcp`, который реализует числовые расчёты для сценариев
  портфельного риска и ликвидности (7/9) и опирается на формальные схемы из
  `docs/SCENARIOS_PORTFOLIO_RISK.md` (`PortfolioRiskInput/Report`,
  `RebalanceInput/Proposal`, `CfoLiquidityReportInput/Report`). Он получает
  рыночные данные через `moex-iss-mcp`/`moex_iss_sdk` и предоставляет
  инструменты уровня `analyze_portfolio_risk`, `suggest_rebalance`,
  `build_cfo_liquidity_report`, а также вспомогательные расчёты корреляций.

- `architecture/sdk/ARCH-sdk-moex-iss-v1.md` — библиотека `moex_iss_sdk`,
  единый типизированный клиент MOEX ISS, используемый всеми MCP‑серверами
  проекта. В нём сосредоточены HTTP‑логика, rate limiting, кэширование и
  нормализованные исключения (`InvalidTickerError`, `DateRangeTooLargeError`,
  и т.д.), которые далее мапятся в `error_type` на уровне MCP.

## Связь с документацией в docs/

- `docs/ARCHITECTURE.md` даёт системный обзор (C4 L2/L3/L4) и описывает место
  агента, `moex-iss-mcp`, `risk-analytics-mcp` и (опционально) RAG‑MCP в
  контуре Evolution AI Agents.
- `docs/SCENARIOS_PORTFOLIO_RISK.md` является SSOT для сценариев 5/7/9 и JSON
  схем MCP‑инструментов портфельного риска, ребалансировки и отчётов CFO.
- `docs/SPEC_moex-iss-mcp.md` фиксирует контракт `moex-iss-mcp` и A2A‑схемы.
- `docs/REQUIREMENTS_moex-market-analyst-agent.md` устанавливает FR/NFR и
  платформенные ограничения (Cloud.ru Evolution AI Agents, Foundation Models,
  MCP, безопасность, наблюдаемость).

Архитектурные файлы в `architecture/` должны рассматриваться как
детализированная проекция этих документов на уровень конкретных компонент
(агент, MCP‑сервера, SDK) и обновляться по мере развития реализации и схем в
`docs/`.
