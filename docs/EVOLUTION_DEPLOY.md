# Деплой в Cloud.ru Evolution AI Agents

Документ описывает подготовку MCP-серверов и агента `moex-market-analyst-agent` к публикации в Evolution AI Agents (dev → prod), а также требования к секретам и конфигурации.

## 1. Образы и теги
- `moex-iss-mcp:<tag>` — MCP данных ISS.
- `risk-analytics-mcp:<tag>` — MCP риск-аналитики.
- `moex-market-analyst-agent:<tag>` — A2A-агент.

Сборка для linux/amd64:
```bash
docker buildx build --platform linux/amd64 -t <registry>/<project>/moex-iss-mcp:<tag> -f moex_iss_mcp/Dockerfile .
docker buildx build --platform linux/amd64 -t <registry>/<project>/risk-analytics-mcp:<tag> -f risk_analytics_mcp/Dockerfile .
docker buildx build --platform linux/amd64 -t <registry>/<project>/moex-market-analyst-agent:<tag> -f packages/agent-service/Dockerfile .
docker push <registry>/<project>/<image>:<tag>
```

## 2. Регистрация MCP в Evolution
Для каждого MCP:
1) Выберите образ и тег в Registry проекта.
2) Endpoint: `/mcp`, Health: `/health`, Metrics: `/metrics`.
3) Транспорт: `streamable-http`.
4) Импортируйте `mcp-server-catalog.yaml` из каталога MCP (описание инструментов, версий).
5) Переменные окружения — из таблицы ниже.

## 3. Регистрация агента
1) Образ: `<registry>/<project>/moex-market-analyst-agent:<tag>`.
2) Endpoint A2A: `POST /a2a`, Health: `GET /health`.
3) Укажите подключённые MCP: URLs из переменных `MOEX_ISS_MCP_URL`, `RISK_ANALYTICS_MCP_URL`.
4) Настройте секреты через Secret Manager (LLM/FMs ключи, MOEX ключ при необходимости).

## 4. Переменные окружения (dev/prod)

### Агент
| Переменная | Назначение | Обяз. | Dev | Prod | Секрет |
| --- | --- | --- | --- | --- | --- |
| ENVIRONMENT | dev/prod | да | dev | prod | нет |
| AGENT_PORT | Порт HTTP | да | 8100 | 8100 | нет |
| AGENT_ENABLE_DEBUG | Debug в ответе | нет | true | false | нет |
| AGENT_STEP_TIMEOUT_SECONDS | Таймаут шага | нет | 45 | 45 | нет |
| MOEX_ISS_MCP_URL | URL MCP данных | да | http://moex-iss-mcp:8000 | prod URL | нет |
| RISK_ANALYTICS_MCP_URL | URL MCP риска | да | http://risk-analytics-mcp:8010 | prod URL | нет |
| LLM_API_BASE | FM endpoint | да | https://foundation-models.api.cloud.ru/v1 | тот же | нет |
| LLM_API_KEY или EVOLUTION_SERVICE_ACCOUNT_KEY_ID/SECRET | Доступ к FM | да | secret | secret | да |

### moex-iss-mcp
| Переменная | Назначение | Обяз. | Dev | Prod | Секрет |
| --- | --- | --- | --- | --- | --- |
| PORT | Порт MCP | да | 8000 | 8000 | нет |
| HOST | Сетевой интерфейс | да | 0.0.0.0 | 0.0.0.0 | нет |
| MOEX_ISS_BASE_URL | База ISS | да | https://iss.moex.com/iss/ | тот же | нет |
| MOEX_ISS_RATE_LIMIT_RPS | Лимит RPS | нет | 3 | 3 | нет |
| MOEX_ISS_TIMEOUT_SECONDS | Таймаут | нет | 10 | 10 | нет |
| ENABLE_MONITORING | Метрики/OTEL | нет | false | true/false | нет |
| OTEL_ENDPOINT | OTEL экспорт | нет | — | prod endpoint | может |
| OTEL_SERVICE_NAME | Имя сервиса | нет | moex-iss-mcp | moex-iss-mcp | нет |
| MOEX_API_KEY | Ключ ISS (если нужен) | нет | secret | secret | да |

### risk-analytics-mcp
| Переменная | Назначение | Обяз. | Dev | Prod | Секрет |
| --- | --- | --- | --- | --- | --- |
| RISK_MCP_PORT | Порт MCP | да | 8010 | 8010 | нет |
| HOST | Сетевой интерфейс | да | 0.0.0.0 | 0.0.0.0 | нет |
| RISK_MAX_PORTFOLIO_TICKERS | Лимит позиций | нет | 50 | 50 | нет |
| RISK_MAX_CORRELATION_TICKERS | Лимит корреляций | нет | 20 | 20 | нет |
| RISK_MAX_PEERS | Лимит пиров | нет | 15 | 15 | нет |
| RISK_MAX_LOOKBACK_DAYS | Глубина истории | нет | 365 | 365 | нет |
| RISK_DEFAULT_INDEX_TICKER | Индекс по умолчанию | нет | IMOEX | IMOEX | нет |
| RISK_ENABLE_MONITORING | Метрики/OTEL | нет | false | true/false | нет |
| RISK_OTEL_ENDPOINT | OTEL экспорт | нет | — | prod endpoint | может |
| RISK_OTEL_SERVICE_NAME | Имя сервиса | нет | risk-analytics-mcp | risk-analytics-mcp | нет |

## 5. Секреты (только через Secret Manager)
- `LLM_API_KEY` или `EVOLUTION_SERVICE_ACCOUNT_KEY_ID` / `EVOLUTION_SERVICE_ACCOUNT_KEY_SECRET`.
- `MOEX_API_KEY` (если используется).
- OTEL tokens/credentials (если требуются для экспорта).

## 6. Локальная проверка (smoke)
1) Сборка и запуск: `make local-build && make local-up`.
2) Проверить health:
   - `curl http://localhost:8000/health`
   - `curl http://localhost:8010/health`
   - `curl http://localhost:8100/health`
3) Запустить smoke-тест:  
   ```bash
   cd packages/agent-service/examples
   AGENT_URL=http://localhost:8100 python smoke_compare.py
   ```

## 7. Чек-лист перед публикацией
- Образы собраны для `linux/amd64` и запушены в Registry.
- MCP endpoints `/mcp` отвечают, `/health` возвращает 200.
- Таблицы переменных и секретов заполнены в UI Evolution.
- Smoke-тест проходит против развернутого стека (dev).
- Agent Card отражает подключённые MCP и домен (MOEX данные, read-only).
