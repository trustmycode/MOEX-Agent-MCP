from __future__ import annotations

import time
from typing import Any, Dict


class SessionStateStore:
    """Простое in-memory хранилище parsed_params по session_id с TTL."""

    def __init__(self, ttl_seconds: float = 900.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, session_id: str) -> dict[str, Any]:
        if not session_id:
            return {}
        entry = self._store.get(session_id)
        if not entry:
            return {}
        expires_at, data = entry
        if expires_at < time.time():
            self._store.pop(session_id, None)
            return {}
        return dict(data)

    def set(self, session_id: str, parsed_params: dict[str, Any]) -> None:
        if not session_id:
            return
        expires_at = time.time() + self.ttl_seconds
        self._store[session_id] = (expires_at, dict(parsed_params))

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
