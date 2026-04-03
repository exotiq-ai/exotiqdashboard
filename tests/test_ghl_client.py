# tests/test_ghl_client.py
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ghl.ghl_client import (
    GHLAuthError,
    GHLClient,
    GHLRateLimitError,
    GHLServerError,
    GHLValidationError,
    RateLimiter,
)


def _make_client():
    return GHLClient(token="test-token", location_id="loc-123")


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


class TestRateLimiter:
    def test_allows_calls_within_limit(self):
        rl = RateLimiter(max_calls=5, window=10.0)
        start = time.monotonic()
        for _ in range(5):
            rl.acquire()
        assert time.monotonic() - start < 1.0

    def test_blocks_when_limit_reached(self):
        # Tiny window so the test completes quickly
        rl = RateLimiter(max_calls=2, window=0.1)
        rl.acquire()
        rl.acquire()
        start = time.monotonic()
        rl.acquire()  # should block briefly
        assert time.monotonic() - start >= 0.05


class TestGHLClientInit:
    def test_init_with_explicit_token(self):
        client = GHLClient(token="my-token", location_id="loc-abc")
        assert client.token == "my-token"
        assert client.location_id == "loc-abc"

    def test_init_loads_token_from_env(self, monkeypatch):
        monkeypatch.setenv("GHL_API_TOKEN", "env-token")
        monkeypatch.setenv("GHL_LOCATION_ID", "env-loc")
        client = GHLClient()
        assert client.token == "env-token"
        assert client.location_id == "env-loc"

    def test_init_raises_when_no_token(self, monkeypatch):
        monkeypatch.delenv("GHL_API_TOKEN", raising=False)
        with pytest.raises(ValueError, match="GHL_API_TOKEN"):
            GHLClient()


class TestGHLClientGet:
    @patch("requests.get")
    def test_successful_get(self, mock_get):
        mock_get.return_value = _mock_response(200, {"contacts": []})
        client = _make_client()
        result = client.get("/contacts")
        assert result == {"contacts": []}
        headers = mock_get.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Version"] == "2021-07-28"

    @patch("requests.get")
    def test_401_raises_auth_error(self, mock_get):
        mock_get.return_value = _mock_response(401, {})
        with pytest.raises(GHLAuthError):
            _make_client().get("/contacts")

    @patch("requests.get")
    def test_403_raises_auth_error(self, mock_get):
        mock_get.return_value = _mock_response(403, {})
        with pytest.raises(GHLAuthError):
            _make_client().get("/contacts")

    @patch("requests.get")
    def test_429_raises_rate_limit_error(self, mock_get):
        mock_get.return_value = _mock_response(429, {})
        with pytest.raises(GHLRateLimitError):
            _make_client().get("/contacts")

    @patch("requests.get")
    def test_422_raises_validation_error(self, mock_get):
        mock_get.return_value = _mock_response(422, {})
        with pytest.raises(GHLValidationError):
            _make_client().get("/contacts")

    @patch("requests.get")
    def test_500_raises_server_error(self, mock_get):
        mock_get.return_value = _mock_response(500, {})
        with pytest.raises(GHLServerError):
            _make_client().get("/contacts")


class TestGHLClientPost:
    @patch("requests.post")
    def test_successful_post(self, mock_post):
        mock_post.return_value = _mock_response(201, {"contact": {"id": "cid-abc"}})
        result = _make_client().post("/contacts/", {"firstName": "Xavier"})
        assert result == {"contact": {"id": "cid-abc"}}
        assert mock_post.call_args.kwargs["json"] == {"firstName": "Xavier"}

    @patch("requests.post")
    def test_401_raises_auth_error(self, mock_post):
        mock_post.return_value = _mock_response(401, {})
        with pytest.raises(GHLAuthError):
            _make_client().post("/contacts/", {})


class TestGHLClientPut:
    @patch("requests.put")
    def test_successful_put(self, mock_put):
        mock_put.return_value = _mock_response(200, {"contact": {"id": "cid-abc"}})
        result = _make_client().put("/contacts/cid-abc", {"firstName": "Xavier"})
        assert result == {"contact": {"id": "cid-abc"}}
