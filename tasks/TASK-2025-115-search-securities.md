---
id: TASK-2025-115
title: "Реализация поиска инструментов (search_securities)"
status: backlog
priority: high
type: feature
estimate: 4h
assignee: @unassigned
created: 2025-12-12
updated: 2025-12-12
parents: [TASK-2025-002]
children: []
arch_refs: [ARCH-mcp-moex-iss]
risk: low
benefit: "Позволяет агенту находить правильные тикеры по названию компании (например, 'Ашинский' -> 'AMEZ'), снижая риск галлюцинаций."
audit_log:
  - {date: 2025-12-12, user: "@AI-Architect", action: "created"}
---

## Контекст

Пользователи часто используют названия компаний ("Сбер", "Норникель", "Ашинский метзавод") вместо тикеров. Хотя LLM знают тикеры "голубых фишек", они часто ошибаются или не знают тикеры компаний 2-3 эшелона.

Для надежной работы `MarketDataSubagent` необходим инструмент, который преобразует поисковый запрос в список валидных тикеров через API Мосбиржи.

## Цель

Реализовать в `moex-iss-mcp` инструмент `search_securities`, который использует endpoint поиска MOEX ISS.

## Объём работ

### 1. Расширение SDK (`moex_iss_sdk`)

- Добавить метод `build_search_endpoint(query: str)` в `endpoints.py`.
  - URL: `https://iss.moex.com/iss/securities.json`
  - Params: `q={query}`, `iss.meta=off`, `engine=stock`, `market=shares` (опционально фильтровать, но лучше искать широко).
- Добавить модель `SecuritySearchResult` в `models.py`:
  - `ticker` (secid)
  - `short_name` (name)
  - `isin`
  - `type` (group/type)
- Реализовать метод `search_securities(query: str) -> List[SecuritySearchResult]` в `IssClient`.

### 2. Реализация MCP Tool (`moex_iss_mcp`)

- Создать файл `tools/search_securities.py`.
- Реализовать инструмент `search_securities`:
  - **Input:** `query` (строка, мин. 3 символа).
  - **Output:** Список найденных бумаг (ограничить топ-5 или топ-10 для экономии контекста).
  - **Логика:** Вызов SDK -> Фильтрация (оставлять только акции/облигации, убирать мусор) -> Возврат результата.

### 3. Регистрация

- Добавить инструмент в `server.py`.
- Обновить `tools.json`.

## Критерии приемки

- [ ] Вызов `search_securities(query="Сбер")` возвращает JSON, где есть `SBER` и `SBERP`.
- [ ] Вызов `search_securities(query="Ашинский")` возвращает `AMEZ`.
- [ ] Инструмент корректно обрабатывает пустой результат (возвращает пустой список, а не ошибку).
- [ ] Написан unit-тест для SDK и интеграционный тест для MCP.

## Определение готовности

Агент (или curl-запрос) может получить правильный тикер, не зная его заранее.

```bash
curl -X POST http://localhost:8000/mcp \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_securities","arguments":{"query":"Яндекс"}}}'
```
