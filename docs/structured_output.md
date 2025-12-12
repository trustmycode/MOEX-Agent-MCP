# Structured output для Cloud.ru моделей

## Флаги окружения
- `LLM_USE_STRUCTURED_TAG=true` — включает структурированный вывод (по умолчанию true).
- `LLM_STRUCTURED_MODELS` — список моделей через запятую (по умолчанию `openai/gpt-oss-120b,Qwen/Qwen3-235B-A22B-Instruct-2507`).
- `LLM_MODEL_MAIN`, `LLM_MODEL_FALLBACK`, `LLM_MODEL_DEV` — выбор моделей.

## Формат `structural_tag`
Клиент собирает `response_format` вида:
```json
{
  "type": "structural_tag",
  "format": {
    "type": "triggered_tags",
    "triggers": ["<result>"],
    "tags": [{
      "begin": "<result>",
      "end": "</result>",
      "content": {
        "type": "json_schema",
        "json_schema": {
          "name": "planner_plan",
          "schema": { "...": "JSON Schema" }
        }
      }
    }]
  }
}
```

## Fallback
Если Cloud.ru возвращает ошибку (например, 400), клиент делает повтор через tool-calling (`tools`) с извлечением `function.arguments`.

## Пример curl (healthcheck)
```bash
TOKEN="***"
curl -s -X POST "https://foundation-models.api.cloud.ru/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-120b",
    "messages": [
      {"role": "system", "content": "Отвечай строго в <result>{...}</result>"},
      {"role": "user", "content": "верни ok=true"}
    ],
    "response_format": {
      "type": "structural_tag",
      "format": {
        "type": "triggered_tags",
        "triggers": ["<result>"],
        "tags": [{
          "begin": "<result>",
          "end": "</result>",
          "content": {
            "type": "json_schema",
            "json_schema": {
              "name": "healthcheck",
              "schema": {
                "type": "object",
                "required": ["ok"],
                "properties": { "ok": { "type": "boolean" } }
              }
            }
          }
        }]
      }
    },
    "temperature": 0
  }'
```

## Требования к плану планировщика
- ≤5 шагов, без циклов.
- Для портфельных/CFO сценариев: `market_data` перед `risk_analytics`, финальный `explainer`.
- Все tool-аргументы обязательны согласно каталогу.

