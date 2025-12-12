---
id: TASK-2025-141
title: "Подготовка манифестов MCP для Evolution AI Agents"
status: backlog
priority: high
type: chore
estimate: 4h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-002, TASK-2025-076]
children: []
arch_refs: [ARCH-mcp-moex-iss, ARCH-mcp-risk-analytics]
risk: medium
benefit: "Обеспечивает успешный деплой и валидацию MCP-серверов в каталоге платформы."
audit_log:
  - {date: 2025-12-12, user: "@AI-Architect", action: "created"}
---

## Описание

Привести конфигурационные файлы `moex-iss-mcp` и `risk-analytics-mcp` в полное соответствие со спецификацией Evolution AI Agents. Разделить переменные на `rawEnvs` (публичные) и `secretEnvs` (секретные).

## Контекст

Платформа требует наличия файла `mcp-server-catalog.yaml` (или аналога в UI) с четким разделением конфигурации. Неправильная конфигурация приведет к ошибке деплоя или утечке секретов.

## Ссылки на документацию
https://cloud.ru/docs/foundation-models/ug/topics/guides?source-platform=Evolution
https://cloud.ru/docs/ai-agents/ug/topics/concepts__variables-mcp-server?source-platform=Evolution

## Критерии приёмки

### moex-iss-mcp
- [ ] Обновлен `mcp-server-catalog.yaml`:
  - `rawEnvs`: `MOEX_ISS_BASE_URL`, `MOEX_ISS_RATE_LIMIT_RPS`, `LOG_LEVEL`.
  - `secretEnvs`: (если есть, например, для платного доступа, иначе пусто).
  - `exposed_ports`: 8000 (HTTP).
  - `cmd`: Команда запуска соответствует Dockerfile (`python -m moex_iss_mcp.main`).
- [ ] Проверен `Dockerfile`:
  - Используется `EXPOSE 8000`.
  - Установлены все зависимости (включая `uvicorn`/`fastapi` если используется FastMCP HTTP).

### risk-analytics-mcp
- [ ] Обновлен `mcp-server-catalog.yaml`:
  - `rawEnvs`: `RISK_MAX_PORTFOLIO_TICKERS`, `MOEX_ISS_MCP_URL` (для связи между MCP, если применимо, или настройки SDK).
  - `secretEnvs`: `LLM_API_KEY` (если MCP ходит в LLM, хотя в нашей архитектуре это делает Агент).
  - `exposed_ports`: 8010.

### Документация
- [ ] В `README.md` каждого MCP добавлен раздел "Deploy to Evolution" с примером заполнения переменных.

## Определение готовности

- Файлы `mcp-server-catalog.yaml` проходят валидацию (визуальную или через CLI платформы).
- Переменные окружения четко разделены на конфиг и секреты.

## Ссылки

- [Документация MCP Server Variables](https://cloud.ru/docs/ai-agents/ug/topics/concepts__variables-mcp-server?source-platform=Evolution)


