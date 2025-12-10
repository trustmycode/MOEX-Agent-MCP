import json
import socket
from urllib.error import HTTPError, URLError

import pytest

from moex_iss_sdk import endpoints
from moex_iss_sdk.client import IssClient, IssClientSettings
from moex_iss_sdk.exceptions import InvalidTickerError, IssServerError, IssTimeoutError, UnknownIssError


class DummyResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _spec():
    return endpoints.EndpointSpec(url="http://example/test", params={})


def test_get_json_http_500_raises_server_error(monkeypatch):
    client = IssClient(IssClientSettings(base_url="http://example", rate_limit_rps=0))
    http_err = HTTPError(url="http://example", code=500, msg="boom", hdrs=None, fp=None)
    monkeypatch.setattr("moex_iss_sdk.client.urlopen", lambda req, timeout=None: (_ for _ in ()).throw(http_err))
    with pytest.raises(IssServerError):
        client._get_json(_spec())


def test_get_json_http_404_raises_invalid_ticker(monkeypatch):
    client = IssClient(IssClientSettings(base_url="http://example", rate_limit_rps=0))
    http_err = HTTPError(url="http://example", code=404, msg="notfound", hdrs=None, fp=None)
    monkeypatch.setattr("moex_iss_sdk.client.urlopen", lambda req, timeout=None: (_ for _ in ()).throw(http_err))
    with pytest.raises(InvalidTickerError):
        client._get_json(_spec())


def test_get_json_timeout_raises_timeout(monkeypatch):
    client = IssClient(IssClientSettings(base_url="http://example", rate_limit_rps=0))
    monkeypatch.setattr(
        "moex_iss_sdk.client.urlopen",
        lambda req, timeout=None: (_ for _ in ()).throw(URLError(socket.timeout())),
    )
    with pytest.raises(IssTimeoutError):
        client._get_json(_spec())


def test_get_json_network_error_raises_unknown(monkeypatch):
    client = IssClient(IssClientSettings(base_url="http://example", rate_limit_rps=0))
    monkeypatch.setattr(
        "moex_iss_sdk.client.urlopen",
        lambda req, timeout=None: (_ for _ in ()).throw(URLError("boom")),
    )
    with pytest.raises(UnknownIssError):
        client._get_json(_spec())


def test_get_json_invalid_json_raises_unknown(monkeypatch):
    client = IssClient(IssClientSettings(base_url="http://example", rate_limit_rps=0))
    monkeypatch.setattr("moex_iss_sdk.client.urlopen", lambda req, timeout=None: DummyResponse(b"<html>"))
    with pytest.raises(UnknownIssError):
        client._get_json(_spec())


def test_get_json_valid_json_passes(monkeypatch):
    client = IssClient(IssClientSettings(base_url="http://example", rate_limit_rps=0))
    monkeypatch.setattr(
        "moex_iss_sdk.client.urlopen",
        lambda req, timeout=None: DummyResponse(json.dumps({"ok": True}).encode()),
    )
    assert client._get_json(_spec()) == {"ok": True}


def test_get_json_retries_on_timeout(monkeypatch):
    attempts = {"count": 0}

    def fake_urlopen(req, timeout=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError(socket.timeout())
        return DummyResponse(json.dumps({"ok": True}).encode())

    settings = IssClientSettings(base_url="http://example", rate_limit_rps=0, max_retries=1, retry_backoff_seconds=0)
    client = IssClient(settings, sleep_func=lambda _: None)
    monkeypatch.setattr("moex_iss_sdk.client.urlopen", fake_urlopen)
    assert client._get_json(_spec()) == {"ok": True}
    assert attempts["count"] == 2


def test_get_json_does_not_retry_invalid_ticker(monkeypatch):
    attempts = {"count": 0}
    http_err = HTTPError(url="http://example", code=404, msg="notfound", hdrs=None, fp=None)

    def fake_urlopen(req, timeout=None):
        attempts["count"] += 1
        raise http_err

    settings = IssClientSettings(base_url="http://example", rate_limit_rps=0, max_retries=3, retry_backoff_seconds=0)
    client = IssClient(settings, sleep_func=lambda _: None)
    monkeypatch.setattr("moex_iss_sdk.client.urlopen", fake_urlopen)
    with pytest.raises(InvalidTickerError):
        client._get_json(_spec())
    assert attempts["count"] == 1
