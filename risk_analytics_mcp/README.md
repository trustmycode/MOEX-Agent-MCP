# Risk Analytics MCP Server

MCP-сервер для расчёта портфельного риска, корреляций, ребалансировки и CFO-отчётов. Забирает рыночные данные из MOEX ISS напрямую через `moex_iss_sdk`.

## Что умеет
- `compute_portfolio_risk_basic` — базовые риск-метрики, стресс-сценарии, VaR.
- `compute_correlation_matrix` — корреляции тикеров.
- `issuer_peers_compare` — поиск/сравнение пиров по индексам/сектору.
- `suggest_rebalance` — детерминированное предложение по ребалансировке.
- `build_cfo_liquidity_report` — CFO-ориентированный отчёт по ликвидности/ковенантам.
- `compute_tail_metrics` — хвостовые метрики индекса по OHLCV.
- Эндпоинты: `GET /health`, `GET /metrics` (при мониторинге), `POST /mcp`.

## Переменные окружения (дефолты в скобках)
- `RISK_MCP_PORT` / `PORT` (`8010`), `RISK_MCP_HOST` / `HOST` (`0.0.0.0`)
- `RISK_MAX_PORTFOLIO_TICKERS` (`50`), `RISK_MAX_CORRELATION_TICKERS` (`20`), `RISK_MAX_PEERS` (`15`)
- `RISK_MAX_LOOKBACK_DAYS` или `MOEX_ISS_MAX_LOOKBACK_DAYS` (`365`)
- `RISK_DEFAULT_INDEX_TICKER` (`IMOEX`)
- `RISK_ENABLE_MONITORING` или `ENABLE_MONITORING` (`false`)
- `RISK_OTEL_ENDPOINT` / `OTEL_ENDPOINT`, `RISK_OTEL_SERVICE_NAME` / `OTEL_SERVICE_NAME`
- `MOEX_ISS_BASE_URL` (`https://iss.moex.com/iss`), `MOEX_ISS_RATE_LIMIT_RPS` (`3`), `MOEX_ISS_TIMEOUT_SECONDS` (`10`)
- `MOEX_API_KEY` — если требуется платный доступ к ISS.
- Приоритет env: `.env.risk` → `.env.mcp` → `.env` → `.env.sdk` (см. `env.example`).

## Быстрый старт локально
```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
uv sync
uv run python -m risk_analytics_mcp.main   # http://localhost:8010
curl http://localhost:8010/health
```
Для одновременного запуска всех компонентов используйте `make local-up` в корне.

## Docker / docker-compose
- Собрать образ: `docker build -t risk-analytics-mcp:local -f risk_analytics_mcp/Dockerfile .`
- Запуск: `docker run -p 8010:8010 --env-file env.example risk-analytics-mcp:local`
- В составе стека: `make local-up` (compose в корне).

## Деплой в Evolution AI Agents
- Сборка/публикация (linux/amd64):
```bash
docker buildx build --platform linux/amd64 -t <registry>/<project>/risk-analytics-mcp:<tag> -f risk_analytics_mcp/Dockerfile .
docker push <registry>/<project>/risk-analytics-mcp:<tag>
```
- Регистрация MCP: endpoint `/mcp`, health `/health`, транспорт `streamable-http`.
- rawEnvs: `RISK_MCP_PORT`/`PORT`, `RISK_MCP_HOST`/`HOST`, `RISK_MAX_*`, `RISK_DEFAULT_INDEX_TICKER`, `RISK_ENABLE_MONITORING`/`ENABLE_MONITORING`, `RISK_OTEL_*`/`OTEL_*`, `MOEX_ISS_*`.
- secretEnvs: `MOEX_API_KEY` (если требуется для ISS).

## Траблшутинг
- `INVALID_TICKER` или пустые данные: используйте реальные тикеры MOEX (SBER, GAZP, LKOH, IMOEX).
- История не загружается: уменьшите `RISK_MAX_LOOKBACK_DAYS` или проверьте доступность ISS.
- Высокая задержка: сократите объём входных данных (`RISK_MAX_*`) и проверьте `MOEX_ISS_RATE_LIMIT_RPS`.
