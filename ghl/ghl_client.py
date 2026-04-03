"""
Shared HTTP client for the GHL (GoHighLevel) API.

Handles authentication headers, a sliding-window rate limiter (100 req/10s),
and maps HTTP error codes to typed exceptions so callers can handle them
without inspecting raw response objects.
"""

import os
import threading
import time
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

GHL_BASE = "https://services.leadconnectorhq.com"
GHL_VERSION = "2021-07-28"
_RATE_MAX = 100
_RATE_WINDOW = 10.0  # seconds


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class GHLAuthError(Exception):
    """401 or 403 -- token invalid or revoked. Stop all calls immediately."""


class GHLRateLimitError(Exception):
    """429 -- caller should wait 30s then retry."""


class GHLValidationError(Exception):
    """422 -- payload failed validation. Skip this record and continue batch."""


class GHLServerError(Exception):
    """5xx -- GHL side issue. Retry entire batch next cycle."""


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Sliding-window rate limiter.

    Tracks timestamps of recent acquires. When the window is full, sleeps
    until the oldest call ages out.

    Args:
        max_calls: Maximum calls permitted per window.
        window:    Window length in seconds.
    """

    def __init__(self, max_calls: int, window: float) -> None:
        self._max = max_calls
        self._window = window
        self._calls: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a call slot is available, then claim it."""
        with self._lock:
            now = time.monotonic()
            self._calls = [t for t in self._calls if now - t < self._window]
            if len(self._calls) >= self._max:
                wait_until = self._calls[0] + self._window
                wait_for = wait_until - time.monotonic()
                if wait_for > 0:
                    time.sleep(wait_for)
                now = time.monotonic()
                self._calls = [t for t in self._calls if now - t < self._window]
            self._calls.append(time.monotonic())


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class GHLClient:
    """
    Thin wrapper around the GHL REST API.

    Adds auth headers (Bearer token + Version: 2021-07-28), rate limiting,
    and error classification on every outgoing request.

    Args:
        token:       GHL Private Integration Token. If not provided, reads
                     GHL_API_TOKEN from environment / .env file.
        location_id: GHL sub-account location ID. If not provided, reads
                     GHL_LOCATION_ID from environment.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> None:
        if token is None:
            token = os.getenv("GHL_API_TOKEN")
        if not token:
            raise ValueError(
                "GHL_API_TOKEN is required. Set it in your .env file or environment."
            )
        self.token = token
        self.location_id = location_id or os.getenv("GHL_LOCATION_ID")
        self._rate_limiter = RateLimiter(_RATE_MAX, _RATE_WINDOW)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Version": GHL_VERSION,
        }

    def _handle_response(self, resp: requests.Response, label: str) -> Any:
        if resp.status_code in (401, 403):
            raise GHLAuthError(
                f"Auth failed ({resp.status_code}) on {label}. "
                "Verify GHL_API_TOKEN is valid."
            )
        if resp.status_code == 429:
            raise GHLRateLimitError(f"Rate limited on {label}.")
        if resp.status_code == 422:
            raise GHLValidationError(
                f"Validation error on {label}: {resp.text}"
            )
        if resp.status_code >= 500:
            raise GHLServerError(
                f"GHL server error ({resp.status_code}) on {label}: {resp.text}"
            )
        resp.raise_for_status()
        return resp.json()

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        """GET {GHL_BASE}{path} and return parsed JSON."""
        self._rate_limiter.acquire()
        resp = requests.get(
            f"{GHL_BASE}{path}",
            headers=self._headers(),
            params=params or {},
        )
        return self._handle_response(resp, f"GET {path}")

    def post(self, path: str, payload: dict) -> Any:
        """POST {GHL_BASE}{path} with JSON body and return parsed JSON."""
        self._rate_limiter.acquire()
        resp = requests.post(
            f"{GHL_BASE}{path}",
            headers=self._headers(),
            json=payload,
        )
        return self._handle_response(resp, f"POST {path}")

    def put(self, path: str, payload: dict) -> Any:
        """PUT {GHL_BASE}{path} with JSON body and return parsed JSON."""
        self._rate_limiter.acquire()
        resp = requests.put(
            f"{GHL_BASE}{path}",
            headers=self._headers(),
            json=payload,
        )
        return self._handle_response(resp, f"PUT {path}")
