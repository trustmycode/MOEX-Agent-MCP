"""Проверки безопасных значений по умолчанию HTTP-адаптера."""

import pytest
from fastapi import HTTPException

from agent_service import server
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


def test_registry_reuses_one_openrouter_client(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(
        server,
        "build_openrouter_llm_client_from_env",
        lambda: sentinel,
    )

    registry = server._build_registry()

    assert registry.get_required("research_planner").llm_client is sentinel
    assert registry.get_required("explainer").llm_client is sentinel
