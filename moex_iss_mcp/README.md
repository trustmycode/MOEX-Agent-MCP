# MOEX ISS MCP Server

MCP-сервер, который проксирует ISS API Московской биржи и отдаёт данные инструментов через протокол MCP. Используется A2A-агентом и сабагентами `market_data`/`risk_analytics`.

## Что умеет
- `get_security_snapshot` — текущая цена, изменение, ликвидность.
- `get_ohlcv_timeseries` — OHLCV с метриками доходности/волатильности.
- `get_index_constituents_metrics` — состав индекса с весами и агрегатами.
- Эндпоинты: `GET /health`, `GET /metrics` (если включён мониторинг), `POST /mcp`.

## Переменные окружения (дефолты в скобках)
- `PORT` / `HOST` (`8000` / `0.0.0.0`)
- `MOEX_ISS_BASE_URL` (`https://iss.moex.com/iss`)
- `MOEX_ISS_RATE_LIMIT_RPS` (`3`) — ограничение запросов в секунду.
- `MOEX_ISS_TIMEOUT_SECONDS` (`10`)
- `ENABLE_MONITORING` (`false`) — включает Prometheus метрики на `/metrics`.
- `OTEL_ENDPOINT`, `OTEL_SERVICE_NAME` — экспорт трейсов (опционально).
- `MOEX_API_KEY` — нужен только при платном доступе к ISS.
- Подхватывает `.env.mcp`, затем `.env`, затем `.env.sdk` (см. `env.example`).

## Быстрый старт локально
```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
uv sync
uv run python -m moex_iss_mcp.main    # http://localhost:8000
curl http://localhost:8000/health
```
Для запуска всех сервисов сразу используйте `make local-up` в корне — поднимется `moex-iss-mcp:8000`, `risk-analytics-mcp:8010`, агент и web.

## Docker / docker-compose
- Собрать образ: `docker build -t moex-iss-mcp:local -f moex_iss_mcp/Dockerfile .`
- Запуск: `docker run -p 8000:8000 --env-file env.example moex-iss-mcp:local`
- В составе стека: `make local-up` (compose в корне).

## Деплой в Evolution AI Agents
- Соберите и запушьте образ `linux/amd64`, например:
```bash
docker buildx build --platform linux/amd64 -t <registry>/<project>/moex-iss-mcp:<tag> -f moex_iss_mcp/Dockerfile .
docker push <registry>/<project>/moex-iss-mcp:<tag>
```
- Зарегистрируйте MCP с транспортом `streamable-http`, endpoint `/mcp`, health `/health`.
- rawEnvs: `PORT`, `HOST`, `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `MOEX_ISS_TIMEOUT_SECONDS`, `ENABLE_MONITORING`, `OTEL_*`.
- secretEnvs: `MOEX_API_KEY` (если требуется).

## Траблшутинг
- 429/ограничения: уменьшите частоту или поднимите `MOEX_ISS_RATE_LIMIT_RPS` при наличии квоты.
- Таймауты: увеличьте `MOEX_ISS_TIMEOUT_SECONDS` или проверьте доступность `iss.moex.com`.
- Нет трейсов/метрик: убедитесь, что заданы `ENABLE_MONITORING=true` или `OTEL_ENDPOINT`.

