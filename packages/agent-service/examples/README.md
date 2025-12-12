# E2E Тестирование мультиагентной архитектуры

Скрипты для прогонки агента и MCP-серверов end-to-end: реалистичные вызовы инструментов, сабагентов и оркестратора.

## Требования
- Python 3.12+
- Установленные зависимости (`uv sync` в корне)
- Запущенные MCP: `moex-iss-mcp` (8000), `risk-analytics-mcp` (8010)

## Как запустить MCP
### Вариант A: docker-compose (рекомендуется)
```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
make local-up   # поднимет moex-iss-mcp:8000, risk-analytics-mcp:8010, agent:8100, web:3000
```

### Вариант B: локально без Docker
```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP
uv run python -m moex_iss_mcp.main           # порт 8000
uv run python -m risk_analytics_mcp.main     # порт 8010 (в другом терминале)
```
Проверьте: `curl http://localhost:8000/health` и `curl http://localhost:8010/health`.

## Запуск E2E/интерактивных тестов
```bash
cd /Users/Admin/CursorProject/MOEX-Agent-MCP/packages/agent-service
python examples/e2e_test.py                  # интерактивное меню
```
Переопределить адреса MCP:
```bash
MOEX_ISS_MCP_URL=http://localhost:8000 \
RISK_ANALYTICS_MCP_URL=http://localhost:8010 \
python examples/e2e_test.py --orchestrator
```

### Режимы CLI
- `--all` — все проверки подряд
- `--mcp` — только прямые вызовы MCP-клиентов
- `--subagents` — тесты сабагентов
- `--orchestrator` — полный pipeline (intent → сабагенты → A2A-ответ)

## Что проверяется
- Доступность MCP и корректность JSON-RPC
- Взаимодействие сабагентов (`market_data`, `risk_analytics`, `dashboard`, `explainer`)
- Полный цикл оркестрации A2A с примером запросов пользователя

## Траблшутинг
- MCP недоступен: проверьте URL/порты и запущенные сервисы; `make local-up` поднимет всё.
- `INVALID_TICKER`: используйте реальные тикеры MOEX (SBER, GAZP, LKOH, IMOEX).
- Таймауты: увеличьте таймаут в конфиге MCP или убедитесь в доступности ISS.
