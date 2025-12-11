#!/usr/bin/env python3
"""
Простой smoke-тест A2A: сравнение SBER и GAZP за год.

Запуск:
    AGENT_URL=http://localhost:8100 python smoke_compare.py

Успех, если:
- HTTP 200
- status in output == "success" или "partial"
- output.text непустой
- есть хотя бы одна таблица
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import httpx


AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8100")

PAYLOAD: dict[str, Any] = {
    "messages": [
        {
            "role": "user",
            "content": "Сравни SBER и GAZP за год",
        }
    ],
    "user_role": "CFO",
    "locale": "ru",
}


async def main() -> int:
    url = f"{AGENT_URL.rstrip('/')}/a2a"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=PAYLOAD)

    if resp.status_code != 200:
        print(f"❌ HTTP {resp.status_code}: {resp.text}")
        return 1

    body = resp.json()
    output = body.get("output") or {}

    status = output.get("status")
    text = output.get("text") or ""
    tables = output.get("tables") or []

    if status not in {"success", "partial"}:
        print(f"❌ Некорректный статус: {status}")
        return 1

    if not text.strip():
        print("❌ Пустой output.text")
        return 1

    if not isinstance(tables, list) or len(tables) == 0:
        print("❌ Нет таблиц в output.tables")
        return 1

    print("✅ Smoke-тест пройден: статус OK, текст и таблицы присутствуют")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
