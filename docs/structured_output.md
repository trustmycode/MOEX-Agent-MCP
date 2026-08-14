# Структурированный вывод через OpenRouter

## Настройки окружения

- `OPENROUTER_MODEL` — основная модель, по умолчанию `google/gemini-3.7-flash`.
- `OPENROUTER_FALLBACK_MODEL` — резервная модель, по умолчанию `openai/gpt-5.6-luna`.
- `OPENROUTER_REASONING_EFFORT` — уровень рассуждения, по умолчанию `low`.

## Формат ответа

Планировщик передаёт совместимый с OpenAI параметр `response_format` со схемой JSON:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "planner_plan",
    "schema": {
      "type": "object",
      "properties": {
        "reasoning": { "type": "string" },
        "steps": { "type": "array" }
      },
      "required": ["steps"]
    }
  }
}
```

Если выбранная модель не принимает схему JSON, клиент повторяет запрос с `json_object`. Следующая ступень совместимости — вызов инструмента с извлечением `function.arguments`. После исчерпания вариантов запрос направляется резервной модели.

## Пример запроса

```bash
curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-3.7-flash",
    "messages": [
      {"role": "system", "content": "Верни объект JSON по заданной схеме"},
      {"role": "user", "content": "Верни ok=true"}
    ],
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "healthcheck",
        "schema": {
          "type": "object",
          "required": ["ok"],
          "properties": {"ok": {"type": "boolean"}}
        }
      }
    },
    "reasoning": {"effort": "low"},
    "temperature": 0
  }'
```

## Требования к плану

- Не более пяти шагов, без циклов.
- Для сценариев портфельного риска и финансового директора: `market_data` перед `risk_analytics`, в конце `explainer`.
- Все аргументы инструментов обязательны согласно каталогу.
