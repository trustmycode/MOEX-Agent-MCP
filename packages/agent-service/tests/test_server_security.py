"""Проверки безопасных значений по умолчанию HTTP-адаптера."""

import pytest
from fastapi import HTTPException

from agent_service.server import _require_api_key


def test_api_key_is_required(monkeypatch):
    monkeypatch.delenv("AGENT_API_KEY", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        _require_api_key(None)

    assert exc_info.value.status_code == 503


def test_invalid_api_key_is_rejected(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEY", "expected-value")

    with pytest.raises(HTTPException) as exc_info:
        _require_api_key("Bearer wrong-value")

    assert exc_info.value.status_code == 401


def test_valid_api_key_is_accepted(monkeypatch):
    monkeypatch.setenv("AGENT_API_KEY", "expected-value")

    assert _require_api_key("Bearer expected-value") is None
