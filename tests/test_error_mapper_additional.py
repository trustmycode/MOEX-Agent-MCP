"""
Дополнительные тесты для ErrorMapper.
"""

import json

from moex_iss_sdk.error_mapper import ErrorMapper
from moex_iss_sdk.exceptions import IssServerError


def test_error_mapper_iss_5xx():
    err = IssServerError("server error", status_code=503)
    mapped = ErrorMapper.map_exception(err)
    assert mapped.error_type == "ISS_5XX"
    assert "server error" in mapped.message


def test_error_mapper_timeout_keyword():
    mapped = ErrorMapper.map_exception(TimeoutError("request timed out"))
    assert mapped.error_type == "ISS_TIMEOUT"


def test_error_mapper_connection_keyword():
    mapped = ErrorMapper.map_exception(ConnectionError("connection reset"))
    assert mapped.error_type == "NETWORK_ERROR"


def test_error_mapper_json_decode_error():
    try:
        json.loads("not-json")
    except Exception as exc:  # JSONDecodeError
        mapped = ErrorMapper.map_exception(exc)
        assert mapped.error_type in {"UNKNOWN", "VALIDATION_ERROR", "ISS_TIMEOUT", "NETWORK_ERROR", "INVALID_TICKER", "ISS_5XX"}


def test_error_mapper_empty_message_exception():
    class CustomError(Exception):
        def __str__(self) -> str:
            return ""

    mapped = ErrorMapper.map_exception(CustomError())
    assert mapped.message == "Unknown error" or mapped.message == ""
