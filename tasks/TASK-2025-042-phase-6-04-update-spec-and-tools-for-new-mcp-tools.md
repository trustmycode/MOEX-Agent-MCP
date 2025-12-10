---
id: TASK-2025-042
title: "Фаза 6.4. Обновление SPEC/REQUIREMENTS под новые tools"
status: backlog
priority: medium
type: chore
estimate: 8h
assignee: @unassigned
created: 2025-12-09
updated: 2025-12-09
parents: [TASK-2025-007]
arch_refs: [ARCH-mcp-moex-iss, ARCH-agent-moex-market-analyst]
risk: low
benefit: "Синхронизирует документацию и tools.json с новыми инструментами MCP для портфельного анализа."
audit_log:
  - {date: 2025-12-09, user: "@AI-DocArchitect", action: "created with status backlog"}
---

## Описание

Обновить SPEC, REQUIREMENTS и `tools.json`, добавив описания и схемы для `get_multi_ohlcv_timeseries` и `get_portfolio_metrics`, а также соответствующие изменения в разделе требований к портфельному анализу.

## Критерии приемки

- В SPEC добавлены JSON Schema для новых инструментов и их описания.
- В REQUIREMENTS есть раздел, описывающий функциональность портфельного анализа v1 и ограничения (без сложного VaR/stress).
- `tools.json` обновлён и включает новые инструменты с корректными ссылками на схемы.

## Определение готовности

- Платформа Evolution AI Agents видит все реализованные инструменты MCP и корректно передаёт их описание агенту.

## Заметки

Соответствует пункту 6.4 плана архитектора (Фаза 6).

