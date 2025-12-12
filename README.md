# MOEX Market Analyst Agent (Evolution AI Agents + MCP)

Мультиагентное решение для анализа рынка Московской биржи: A2A-агент использует MCP-серверы для данных MOEX и риск-расчётов, формирует дашборды и человекочитаемые ответы для CFO/аналитиков. Агент вызывает LLM **только через Evolution Foundation Models API** (`https://foundation-models.api.cloud.ru/v1`), умеет работать на платформе Evolution AI Agents и поддерживает локальный запуск через `docker-compose`.

---

## Бизнес-ценность
- Быстрый ответ на вопросы о бумагах/индексах MOEX, сравнении эмитентов, рисках портфеля и ребалансировке.
- CFO-ориентированный отчёт по ликвидности и стресс-сценариям.
- Готовый UI (Next.js) с AG-UI протоколом и структурированным дашбордом.

## Краткая архитектура
- `packages/agent-service` — A2A-агент (FastAPI `/a2a`, `/agui`), оркестратор сабагентов:
  - `research_planner` (LLM-планировщик через Evolution FM),
  - `market_data` (тулзы MOEX ISS MCP),
  - `risk_analytics` (тулзы Risk MCP),
  - `dashboard` (детерминированный JSON-дашборд),
  - `explainer` (LLM-отчёт без выдумывания чисел).
- MCP-серверы:
  - `moex_iss_mcp` — данные MOEX (snapshot, OHLCV, индекс).
  - `risk_analytics_mcp` — портфельный риск, корреляции, ребалансировка, CFO-отчёт.
- `apps/web` — Next.js AG-UI, работает с `/agui` агента.
- Сценарий выполнения: пользовательский запрос → классификация / план → вызов MCP tool(s) → риск-дашборд → текстовое объяснение → A2A-ответ + SSE для UI.

## Репозиторий (основное)
- `packages/agent-service/` — код агента (FastAPI, сабагенты, MCP-клиенты, LLM).
- `moex_iss_mcp/` — MCP данных MOEX ISS (`mcp_tools.json`, `mcp-server-catalog.yaml`).
- `risk_analytics_mcp/` — MCP риск-аналитики (`mcp_tools.json`, `mcp-server-catalog.yaml`).
- `apps/web/` — веб-UI.
- `env.example` — шаблон переменных.
- `docker-compose.yml` — локальный стек (mcp + агент + web).
- `docs/EVOLUTION_DEPLOY.md` — детали деплоя в Evolution AI Agents.

## Конфигурация (.env)
Скопируйте `env.example` → `.env` и заполните секреты.

Ключевые переменные:
- LLM/Evolution: `LLM_API_KEY` (или `EVOLUTION_SERVICE_ACCOUNT_KEY_ID`/`SECRET`), `LLM_API_BASE=https://foundation-models.api.cloud.ru/v1`, `LLM_MODEL_MAIN`, `LLM_MODEL_FALLBACK`, `LLM_MODEL_DEV`.
- Агент: `AGENT_PORT`, `AGENT_ENABLE_DEBUG`, `AGENT_STEP_TIMEOUT_SECONDS`, `MOEX_ISS_MCP_URL`, `RISK_ANALYTICS_MCP_URL`.
- MCP (данные): `PORT`, `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `MOEX_API_KEY` (если нужен), `ENABLE_MONITORING`, `OTEL_*`.
- MCP (риск): `RISK_MCP_PORT`, `RISK_MAX_*`, `RISK_DEFAULT_INDEX_TICKER`, `RISK_ENABLE_MONITORING`, `RISK_OTEL_*`.
- Web: `WEB_PORT`, `AGENT_SERVICE_URL` (обычно `http://agent:8100/agui`).

Секреты хранятся только в Secret Manager/ENV, не хардкодятся.

## Быстрый старт локально (amd64 Linux/macOS)
1) Зависимости: Docker + Docker Compose, Python 3.12+, `uv` (если нужны локальные прогоны без контейнеров).
2) Подготовка окружения:
```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
cp env.example .env
# укажите LLM_API_KEY, MOEX_API_KEY при необходимости
```
3) Запуск стека:
```bash
make local-up           # соберёт и поднимет moex-iss-mcp:8000, risk-analytics-mcp:8010, agent:8100, web:3000
```
4) Проверки:
```bash
curl http://localhost:8000/health
curl http://localhost:8010/health
curl http://localhost:8100/health
```
5) UI: открыть `http://localhost:3000` (AG-UI).

6) Smoke/E2E:
```bash
cd packages/agent-service/examples
AGENT_URL=http://localhost:8100 python e2e_test.py --orchestrator
# или smoke_compare.py для базовой проверки
```

### Альтернатива: запуск без Docker
```bash
uv sync
uv run python -m moex_iss_mcp.main           # порт 8000
uv run python -m risk_analytics_mcp.main     # порт 8010
uv run uvicorn agent_service.server:app --host 0.0.0.0 --port 8100
```

## Деплой в Cloud.ru Evolution AI Agents (prod/dev)
Смотри `docs/EVOLUTION_DEPLOY.md` для полного чек-листа. Кратко:
1) Соберите образы для `linux/amd64` и запушьте в Registry проекта:
```bash
docker buildx build --platform linux/amd64 -t <registry>/<project>/moex-iss-mcp:<tag> -f moex_iss_mcp/Dockerfile .
docker buildx build --platform linux/amd64 -t <registry>/<project>/risk-analytics-mcp:<tag> -f risk_analytics_mcp/Dockerfile .
docker buildx build --platform linux/amd64 -t <registry>/<project>/moex-market-analyst-agent:<tag> -f packages/agent-service/Dockerfile .
docker push <registry>/<project>/<image>:<tag>
```
2) Зарегистрируйте MCP (каждый отдельно):
   - Endpoint `/mcp`, Health `/health`, Metrics `/metrics`, транспорт `streamable-http`.
   - Импортируйте `mcp-server-catalog.yaml`.
   - Укажите rawEnvs/secretEnvs (см. таблицы в `EVOLUTION_DEPLOY.md`).
3) Зарегистрируйте агента:
   - Endpoint A2A: `POST /a2a`, Health: `GET /health`.
   - Подключённые MCP: `MOEX_ISS_MCP_URL`, `RISK_ANALYTICS_MCP_URL`.
   - Секреты: `LLM_API_KEY` (или SA key), `MOEX_API_KEY` при необходимости.
4) Платформа: linux/amd64, без stateful зависимостей.

## MCP инструменты (каталог)
- Данные MOEX (`moex_iss_mcp/mcp_tools.json`): `get_security_snapshot`, `get_ohlcv_timeseries`, `get_index_constituents_metrics`.
- Риск (`risk_analytics_mcp/mcp_tools.json`): `compute_portfolio_risk_basic`, `compute_correlation_matrix`, `issuer_peers_compare`, `suggest_rebalance`, `build_cfo_liquidity_report`, `compute_tail_metrics`.

## Примеры запросов и демо-сценарии
- Портфельный риск:
  - Запрос: «Оцени риск портфеля SBER 40%, GAZP 30%, LKOH 30% за последний год».
  - План: `market_data.get_ohlcv_timeseries` → `risk_analytics.compute_portfolio_risk_basic` → `dashboard` → `explainer`.
- CFO ликвидность:
  - Запрос: «Сформируй CFO отчёт по ликвидности портфеля с ковенантой 25%».
  - План: `risk_analytics.cfo_liquidity_report` → `dashboard` → `explainer`.
- Индекс:
  - Запрос: «Покажи хвост индекса IMOEX и его волатильность за 30 дней».
  - План: `market_data.get_index_constituents_metrics` → `risk_analytics.compute_tail_metrics` → `explainer`.

### cURL к A2A
```bash
curl -X POST http://localhost:8100/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Оцени риск портфеля: SBER 40%, GAZP 30%, LKOH 30%"}],
    "session_id": "demo-1",
    "locale": "ru",
    "user_role": "analyst"
  }'
```

### AG-UI (SSE)
- UI ходит на `/agui`: `AGENT_SERVICE_URL=http://agent:8100/agui` (или локальный адрес).
- События: RUN_STARTED → TEXT_MESSAGE_* → STATE_SNAPSHOT (дашборд/таблицы) → RUN_FINISHED/ERROR.

## Тесты
- E2E/интерактив: `python packages/agent-service/examples/e2e_test.py`.
- Smoke: `python packages/agent-service/examples/smoke_compare.py`.
- Pytest (контракты/модели): `pytest tests/`.

## Траблшутинг
- MCP недоступен: проверьте `MOEX_ISS_MCP_URL` / `RISK_ANALYTICS_MCP_URL`, health и таймауты.
- Ошибка LLM: убедитесь в `LLM_API_KEY` и доступности `https://foundation-models.api.cloud.ru/v1`.
- Нет данных по тикеру: используйте реальные тикеры MOEX (SBER, GAZP, LKOH, IMOEX).

## Лицензия и ограничения
- Платформа выполнения: linux/amd64.
- Запрещён прямой веб-скрапинг; использованы официальные API MOEX ISS.


