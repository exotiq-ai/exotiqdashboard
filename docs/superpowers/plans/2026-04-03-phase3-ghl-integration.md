# Phase 3: GHL Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full GHL webhook bridge -- shared HTTP client, one-time setup script (15 custom fields + 16-stage pipeline), push skill for approved leads, Netlify inbound webhook function, and local event poller.

**Architecture:** `ghl/ghl_client.py` is the shared HTTP layer with rate limiting and typed error classes. `ghl/setup_ghl.py` runs once to create GHL resources and writes all IDs to `ghl/ghl_config.json`. `skills/ghl_push.py` reads that config to push approved leads to GHL contacts + opportunities. `netlify/functions/ghl-webhook.js` receives GHL outbound events and writes them to a JSON queue. `skills/ghl_listener_poller.py` reads the queue and syncs changes back to SQLite.

**Tech Stack:** Python 3.11, requests, python-dotenv, Node.js 18 (Netlify Functions), SQLite, pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `ghl/__init__.py` | Package marker |
| `ghl/ghl_client.py` | HTTP client: auth headers, sliding-window rate limiter (100/10s), typed exceptions |
| `ghl/setup_ghl.py` | Idempotent setup: location lookup, 15 custom fields, 16-stage pipeline, writes `ghl/ghl_config.json` and updates `.env` |
| `ghl/ghl_config.json` | Written by setup_ghl.py; consumed by ghl_push.py and ghl_listener_poller.py |
| `skills/ghl_push.py` | `push_lead_to_ghl(lead_id)`, `push_approved_batch()` |
| `netlify/functions/ghl-webhook.js` | Netlify Function: receives GHL webhooks, writes to event queue dir |
| `netlify/functions/health.js` | Netlify Function: health check endpoint |
| `netlify/functions/event_queue/.gitkeep` | Directory placeholder for event queue |
| `skills/ghl_listener_poller.py` | `poll_event_queue()`: read queue files, sync to SQLite, archive processed |
| `netlify.toml` | Netlify build + functions config |
| `requirements.txt` | Add python-dotenv>=1.0.0, cryptography>=42.0.0 |
| `tests/test_ghl_client.py` | Unit tests for ghl_client.py |
| `tests/test_setup_ghl.py` | Unit tests for setup_ghl.py |
| `tests/test_ghl_push.py` | Unit tests for ghl_push.py |
| `tests/test_ghl_listener_poller.py` | Unit tests for ghl_listener_poller.py |

---

## Task 1: GHL HTTP Client

**Files:**
- Create: `ghl/__init__.py`
- Create: `ghl/ghl_client.py`
- Test: `tests/test_ghl_client.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify tests fail**

```
pytest tests/test_ghl_client.py -v
```
Expected: `ModuleNotFoundError: No module named 'ghl.ghl_client'`

- [ ] **Step 3: Create `ghl/__init__.py`**

```python
# ghl/__init__.py
```
(empty file)

- [ ] **Step 4: Implement `ghl/ghl_client.py`**

```python
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
            load_dotenv()
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
```

- [ ] **Step 5: Run tests and verify all pass**

```
pytest tests/test_ghl_client.py -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add ghl/__init__.py ghl/ghl_client.py tests/test_ghl_client.py
git commit -m "feat: add GHL HTTP client with sliding-window rate limiter and typed exceptions"
```

---

## Task 2: GHL Setup Script

**Files:**
- Create: `ghl/setup_ghl.py`
- Test: `tests/test_setup_ghl.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_setup_ghl.py
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ghl.setup_ghl import (
    CUSTOM_FIELD_DEFS,
    PIPELINE_STAGES,
    ensure_custom_fields,
    ensure_pipeline,
    get_location_id,
    write_config,
)


def _mock_client(get_returns=None, post_returns=None):
    client = MagicMock()
    if get_returns is not None:
        client.get.return_value = get_returns
    if post_returns is not None:
        client.post.return_value = post_returns
    return client


class TestGetLocationId:
    def test_extracts_location_id_from_first_result(self):
        client = _mock_client(get_returns={
            "locations": [{"id": "loc-123", "name": "Exotiq"}]
        })
        assert get_location_id(client) == "loc-123"
        client.get.assert_called_once_with(
            "/locations/search", params={"limit": 20}
        )

    def test_raises_when_locations_empty(self):
        client = _mock_client(get_returns={"locations": []})
        with pytest.raises(RuntimeError, match="No locations found"):
            get_location_id(client)

    def test_raises_when_locations_key_missing(self):
        client = _mock_client(get_returns={})
        with pytest.raises(RuntimeError, match="No locations found"):
            get_location_id(client)


class TestEnsureCustomFields:
    def test_skips_fields_that_already_exist(self):
        existing = {
            "customFields": [
                {"id": "cf-001", "fieldKey": "contact.lead_score", "name": "Lead Score"},
                {"id": "cf-002", "fieldKey": "contact.fleet_size", "name": "Fleet Size"},
            ]
        }
        client = _mock_client(get_returns=existing)
        # post should only be called for the 13 missing fields
        client.post.return_value = {
            "customField": {"id": "cf-new", "fieldKey": "contact.ig_handle"}
        }
        result = ensure_custom_fields(client, "loc-123")
        assert client.post.call_count == len(CUSTOM_FIELD_DEFS) - 2
        assert result["lead_score"] == "cf-001"
        assert result["fleet_size"] == "cf-002"

    def test_creates_all_fields_when_none_exist(self):
        client = _mock_client(get_returns={"customFields": []})
        client.post.return_value = {"customField": {"id": "cf-new"}}
        ensure_custom_fields(client, "loc-123")
        assert client.post.call_count == len(CUSTOM_FIELD_DEFS)

    def test_all_15_field_keys_present(self):
        expected_keys = {
            "lead_score", "lead_score_confidence", "fleet_size",
            "fleet_size_confidence", "ig_handle", "ig_followers",
            "google_rating", "google_reviews", "vehicle_types",
            "dm_template_used", "dm_draft", "do_not_say",
            "enrichment_sources", "openclaw_lead_id", "pipeline_entry_date",
        }
        assert {d["key"] for d in CUSTOM_FIELD_DEFS} == expected_keys

    def test_dropdown_fields_include_options(self):
        dropdown = [d for d in CUSTOM_FIELD_DEFS if d["dataType"] == "DROPDOWN"]
        for d in dropdown:
            assert "options" in d and len(d["options"]) > 0


class TestEnsurePipeline:
    def test_skips_creation_if_pipeline_exists(self):
        existing = {
            "pipelines": [{
                "id": "pip-001",
                "name": "Exotiq Operator Sales",
                "stages": [{"id": "stg-001", "name": "New Lead"}],
            }]
        }
        client = _mock_client(get_returns=existing)
        result = ensure_pipeline(client, "loc-123")
        client.post.assert_not_called()
        assert result["pipeline_id"] == "pip-001"
        assert result["stages"]["New Lead"] == "stg-001"

    def test_creates_pipeline_with_16_stages_when_missing(self):
        client = _mock_client(get_returns={"pipelines": []})
        stage_objs = [
            {"id": f"stg-{i:03d}", "name": s}
            for i, s in enumerate(PIPELINE_STAGES)
        ]
        client.post.return_value = {
            "pipeline": {
                "id": "pip-new",
                "name": "Exotiq Operator Sales",
                "stages": stage_objs,
            }
        }
        result = ensure_pipeline(client, "loc-123")
        client.post.assert_called_once()
        payload = client.post.call_args.args[1]
        assert payload["name"] == "Exotiq Operator Sales"
        assert len(payload["stages"]) == 16
        assert result["pipeline_id"] == "pip-new"

    def test_pipeline_stages_are_all_16_in_order(self):
        expected = [
            "New Lead",
            "Gregory -- Personal Outreach",
            "DM Drafted",
            "DM Sent",
            "Follow-Up 1 Due",
            "Follow-Up 2 Due",
            "Responded -- Warm",
            "Responded -- Cold",
            "Call Scheduled",
            "Demo Scheduled",
            "Demo Complete",
            "Pilot Proposed",
            "Pilot Active",
            "Customer",
            "Not a Fit",
            "Nurture",
        ]
        assert PIPELINE_STAGES == expected


class TestWriteConfig:
    def test_writes_valid_json_to_path(self, tmp_path):
        config_path = str(tmp_path / "ghl_config.json")
        write_config(
            location_id="loc-123",
            custom_field_ids={"lead_score": "cf-001", "fleet_size": "cf-002"},
            pipeline_result={"pipeline_id": "pip-001", "stages": {"New Lead": "stg-001"}},
            config_path=config_path,
        )
        data = json.loads(Path(config_path).read_text())
        assert data["location_id"] == "loc-123"
        assert data["pipeline_id"] == "pip-001"
        assert data["custom_fields"]["lead_score"] == "cf-001"
        assert data["stages"]["New Lead"] == "stg-001"
```

- [ ] **Step 2: Run to verify tests fail**

```
pytest tests/test_setup_ghl.py -v
```
Expected: `ModuleNotFoundError: No module named 'ghl.setup_ghl'`

- [ ] **Step 3: Implement `ghl/setup_ghl.py`**

```python
"""
GHL one-time setup script for the Exotiq Lead Intelligence Pipeline.

Run this once to:
  1. Discover the Exotiq sub-account location ID
  2. Create all 15 custom fields (idempotent -- skips existing ones)
  3. Create the "Exotiq Operator Sales" pipeline with 16 stages (idempotent)
  4. Write ghl/ghl_config.json with all IDs for other skills to consume
  5. Write GHL_LOCATION_ID to the .env file

Usage:
    python ghl/setup_ghl.py
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

# Allow running as a script from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from ghl.ghl_client import GHLClient

_GHL_DIR = Path(__file__).parent
_CONFIG_PATH = str(_GHL_DIR / "ghl_config.json")
_ENV_PATH = _GHL_DIR.parent / ".env"

# ---------------------------------------------------------------------------
# Custom field definitions (all 15)
# ---------------------------------------------------------------------------

CUSTOM_FIELD_DEFS: list[dict[str, Any]] = [
    {"key": "lead_score",            "name": "Lead Score",            "dataType": "NUMERICAL"},
    {"key": "lead_score_confidence", "name": "Score Confidence",      "dataType": "DROPDOWN",
     "options": ["HIGH", "MEDIUM", "LOW"]},
    {"key": "fleet_size",            "name": "Fleet Size",            "dataType": "NUMERICAL"},
    {"key": "fleet_size_confidence", "name": "Fleet Size Confidence", "dataType": "DROPDOWN",
     "options": ["CONFIRMED", "ESTIMATED", "INFERRED"]},
    {"key": "ig_handle",             "name": "IG Handle",             "dataType": "TEXT"},
    {"key": "ig_followers",          "name": "IG Followers",          "dataType": "NUMERICAL"},
    {"key": "google_rating",         "name": "Google Rating",         "dataType": "NUMERICAL"},
    {"key": "google_reviews",        "name": "Google Reviews",        "dataType": "NUMERICAL"},
    {"key": "vehicle_types",         "name": "Vehicle Types",         "dataType": "TEXT"},
    {"key": "dm_template_used",      "name": "DM Template Used",      "dataType": "DROPDOWN",
     "options": ["B", "D", "E", "F"]},
    {"key": "dm_draft",              "name": "DM Draft",              "dataType": "LARGE_TEXT"},
    {"key": "do_not_say",            "name": "DO NOT SAY",            "dataType": "LARGE_TEXT"},
    {"key": "enrichment_sources",    "name": "Enrichment Sources",    "dataType": "TEXT"},
    {"key": "openclaw_lead_id",      "name": "OpenClaw Lead ID",      "dataType": "TEXT"},
    {"key": "pipeline_entry_date",   "name": "Pipeline Entry Date",   "dataType": "DATE"},
]

# ---------------------------------------------------------------------------
# Pipeline stages (all 16, in order)
# ---------------------------------------------------------------------------

PIPELINE_STAGES: list[str] = [
    "New Lead",
    "Gregory -- Personal Outreach",
    "DM Drafted",
    "DM Sent",
    "Follow-Up 1 Due",
    "Follow-Up 2 Due",
    "Responded -- Warm",
    "Responded -- Cold",
    "Call Scheduled",
    "Demo Scheduled",
    "Demo Complete",
    "Pilot Proposed",
    "Pilot Active",
    "Customer",
    "Not a Fit",
    "Nurture",
]


# ---------------------------------------------------------------------------
# Step 1: Discover location ID
# ---------------------------------------------------------------------------

def get_location_id(client: GHLClient) -> str:
    """
    Query GHL for the Exotiq sub-account location ID.

    Returns:
        The locationId string of the first returned location.

    Raises:
        RuntimeError: If no locations are returned.
    """
    data = client.get("/locations/search", params={"limit": 20})
    locations = data.get("locations") or []
    if not locations:
        raise RuntimeError(
            "No locations found in GHL account. "
            "Verify GHL_API_TOKEN has access to the Exotiq sub-account."
        )
    return locations[0]["id"]


# ---------------------------------------------------------------------------
# Step 2: Custom fields (idempotent)
# ---------------------------------------------------------------------------

def ensure_custom_fields(client: GHLClient, location_id: str) -> dict[str, str]:
    """
    Create all 15 custom fields, skipping any that already exist.

    Checks existing fields by matching the fieldKey suffix (the part after
    "contact." in GHL's full fieldKey format).

    Args:
        client:      Authenticated GHLClient.
        location_id: GHL sub-account location ID.

    Returns:
        Dict mapping short key (e.g. "lead_score") -> GHL field ID.
    """
    existing_resp = client.get(f"/locations/{location_id}/customFields")
    existing = existing_resp.get("customFields") or []

    # Build map: key suffix (after "contact.") -> field ID
    existing_by_key: dict[str, str] = {}
    for field in existing:
        fk = field.get("fieldKey", "")
        suffix = fk.split(".")[-1]  # "contact.lead_score" -> "lead_score"
        existing_by_key[suffix] = field["id"]

    result: dict[str, str] = {}
    for defn in CUSTOM_FIELD_DEFS:
        key = defn["key"]
        if key in existing_by_key:
            print(f"  [skip] {key} already exists ({existing_by_key[key]})")
            result[key] = existing_by_key[key]
            continue

        payload: dict[str, Any] = {
            "name": defn["name"],
            "dataType": defn["dataType"],
            "locationId": location_id,
        }
        if "options" in defn:
            payload["options"] = [{"label": o, "value": o} for o in defn["options"]]

        resp = client.post(f"/locations/{location_id}/customFields", payload)
        created = resp.get("customField") or resp
        field_id = created.get("id", "unknown")
        result[key] = field_id
        print(f"  [created] {key} ({field_id})")

    return result


# ---------------------------------------------------------------------------
# Step 3: Pipeline (idempotent)
# ---------------------------------------------------------------------------

def ensure_pipeline(client: GHLClient, location_id: str) -> dict[str, Any]:
    """
    Create the "Exotiq Operator Sales" pipeline with 16 stages, or return
    the existing one if it already exists (matched by name).

    Args:
        client:      Authenticated GHLClient.
        location_id: GHL sub-account location ID.

    Returns:
        Dict with ``pipeline_id`` (str) and ``stages`` (name -> stage_id) keys.
    """
    existing_resp = client.get(
        "/opportunities/pipelines", params={"locationId": location_id}
    )
    pipelines = existing_resp.get("pipelines") or []
    for pip in pipelines:
        if pip.get("name") == "Exotiq Operator Sales":
            print(f"  [skip] pipeline already exists ({pip['id']})")
            stages = {s["name"]: s["id"] for s in pip.get("stages", [])}
            return {"pipeline_id": pip["id"], "stages": stages}

    payload = {
        "name": "Exotiq Operator Sales",
        "locationId": location_id,
        "stages": [{"name": s} for s in PIPELINE_STAGES],
    }
    resp = client.post("/opportunities/pipelines", payload)
    pip = resp.get("pipeline") or resp
    stages = {s["name"]: s["id"] for s in pip.get("stages", [])}
    print(f"  [created] pipeline ({pip['id']}) with {len(stages)} stages")
    return {"pipeline_id": pip["id"], "stages": stages}


# ---------------------------------------------------------------------------
# Step 4: Write config
# ---------------------------------------------------------------------------

def write_config(
    location_id: str,
    custom_field_ids: dict[str, str],
    pipeline_result: dict[str, Any],
    config_path: str = _CONFIG_PATH,
) -> None:
    """
    Write all GHL IDs to ghl/ghl_config.json.

    This is the single source of truth for field and pipeline IDs consumed
    by skills/ghl_push.py and skills/ghl_listener_poller.py.

    Args:
        location_id:      GHL sub-account location ID.
        custom_field_ids: Dict mapping field key -> GHL field ID.
        pipeline_result:  Dict with ``pipeline_id`` and ``stages`` keys.
        config_path:      Output path (override for tests).
    """
    config = {
        "location_id": location_id,
        "pipeline_id": pipeline_result["pipeline_id"],
        "stages": pipeline_result["stages"],
        "custom_fields": custom_field_ids,
    }
    Path(config_path).write_text(json.dumps(config, indent=2))
    print(f"  [saved] config to {config_path}")


# ---------------------------------------------------------------------------
# Step 5: Update .env
# ---------------------------------------------------------------------------

def update_env_file(location_id: str) -> None:
    """
    Write or update GHL_LOCATION_ID in the .env file.

    Does not overwrite existing lines for other variables.

    Args:
        location_id: The GHL sub-account location ID to persist.
    """
    lines: list[str] = []
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text().splitlines()
    lines = [ln for ln in lines if not ln.startswith("GHL_LOCATION_ID=")]
    lines.append(f"GHL_LOCATION_ID={location_id}")
    _ENV_PATH.write_text("\n".join(lines) + "\n")
    print(f"  [saved] GHL_LOCATION_ID={location_id} to .env")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full GHL setup sequence."""
    print("=== GHL Setup: Exotiq Operator Sales ===\n")

    client = GHLClient()

    print("1. Discovering location ID...")
    location_id = get_location_id(client)
    print(f"   Location ID: {location_id}\n")

    print("2. Ensuring custom fields (15 total)...")
    field_ids = ensure_custom_fields(client, location_id)
    print(f"   {len(field_ids)} fields ready.\n")

    print("3. Ensuring pipeline...")
    pipeline_result = ensure_pipeline(client, location_id)
    print(f"   Pipeline ID: {pipeline_result['pipeline_id']}\n")

    print("4. Writing config...")
    write_config(location_id, field_ids, pipeline_result)
    print()

    print("5. Updating .env...")
    update_env_file(location_id)
    print()

    print("=== Setup complete. ===")
    print(f"   Config written to ghl/ghl_config.json")
    print(f"   Run 'python ghl/setup_ghl.py' again at any time -- it is idempotent.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests and verify all pass**

```
pytest tests/test_setup_ghl.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add ghl/setup_ghl.py tests/test_setup_ghl.py
git commit -m "feat: add GHL setup script -- idempotent custom fields and pipeline creation"
```

---

## Task 3: GHL Push Skill

**Files:**
- Create: `skills/ghl_push.py`
- Test: `tests/test_ghl_push.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ghl_push.py
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.ghl_push import (
    _build_contact_payload,
    _build_tags,
    _compute_monetary_value,
    _load_config,
    push_approved_batch,
    push_lead_to_ghl,
)


MOCK_CONFIG = {
    "location_id": "loc-123",
    "pipeline_id": "pip-001",
    "stages": {
        "Gregory -- Personal Outreach": "stg-001",
        "DM Drafted": "stg-002",
        "New Lead": "stg-003",
    },
    "custom_fields": {
        "lead_score": "cf-001",
        "lead_score_confidence": "cf-002",
        "fleet_size": "cf-003",
        "fleet_size_confidence": "cf-004",
        "ig_handle": "cf-005",
        "ig_followers": "cf-006",
        "google_rating": "cf-007",
        "google_reviews": "cf-008",
        "vehicle_types": "cf-009",
        "dm_template_used": "cf-010",
        "dm_draft": "cf-011",
        "do_not_say": "cf-012",
        "enrichment_sources": "cf-013",
        "openclaw_lead_id": "cf-014",
        "pipeline_entry_date": "cf-015",
    },
}


def _make_lead(**overrides) -> dict:
    base = {
        "id": "lead_mia_001",
        "company": "Prestige Luxury Rentals",
        "contact_first_name": "Xavier",
        "contact_last_name": "Guerrero",
        "contact_email": "xavier@prestige.com",
        "contact_phone": "+17862024892",
        "company_address": "4019 NW 25th Street, Miami",
        "company_website": "prestigeluxuryrentals.com",
        "market": "Miami",
        "scoring_score": 4,
        "scoring_confidence": "HIGH",
        "fleet_size": 20,
        "fleet_size_confidence": "ESTIMATED",
        "company_ig_handle": "@prestige",
        "company_ig_followers": 5000,
        "company_google_rating": 4.7,
        "company_google_reviews": 100,
        "fleet_vehicle_types": json.dumps(["Lamborghini", "Ferrari"]),
        "outreach_approval_status": "APPROVED",
        "outreach_template_used": "D",
        "outreach_dm_draft": "Hey, Gregory here...",
        "outreach_do_not_say": json.dumps([]),
        "ghl_in_ghl": 0,
        "ghl_contact_id": None,
        "ghl_opportunity_id": None,
        "ghl_tags": json.dumps([]),
        "lead_source": "Apollo + IG Research",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _build_tags
# ---------------------------------------------------------------------------

class TestBuildTags:
    def test_always_includes_exotiq_pipeline(self):
        assert "exotiq-pipeline" in _build_tags(_make_lead())

    def test_score_tag(self):
        assert "score-4" in _build_tags(_make_lead(scoring_score=4))

    def test_market_lowercased_and_hyphenated(self):
        assert "phoenix-scottsdale" in _build_tags(_make_lead(market="Phoenix Scottsdale"))

    def test_fleet_tier_under_10(self):
        assert "under-10-fleet" in _build_tags(_make_lead(fleet_size=5))

    def test_fleet_tier_10_to_24(self):
        assert "10-to-24-fleet" in _build_tags(_make_lead(fleet_size=15))

    def test_fleet_tier_25_plus(self):
        assert "25-plus-fleet" in _build_tags(_make_lead(fleet_size=30))

    def test_score_5_gets_gregory_only(self):
        assert "gregory-only" in _build_tags(_make_lead(scoring_score=5, fleet_size=30))

    def test_score_4_no_gregory_only(self):
        assert "gregory-only" not in _build_tags(_make_lead(scoring_score=4, fleet_size=20))


# ---------------------------------------------------------------------------
# _compute_monetary_value
# ---------------------------------------------------------------------------

class TestComputeMonetaryValue:
    def test_formula_fleet_times_350_times_365_times_0_6(self):
        assert _compute_monetary_value(10) == round(10 * 350 * 365 * 0.6)

    def test_none_returns_zero(self):
        assert _compute_monetary_value(None) == 0

    def test_zero_returns_zero(self):
        assert _compute_monetary_value(0) == 0


# ---------------------------------------------------------------------------
# _build_contact_payload
# ---------------------------------------------------------------------------

class TestBuildContactPayload:
    def test_native_fields_mapped(self):
        payload = _build_contact_payload(_make_lead(), MOCK_CONFIG)
        assert payload["firstName"] == "Xavier"
        assert payload["lastName"] == "Guerrero"
        assert payload["email"] == "xavier@prestige.com"
        assert payload["phone"] == "+17862024892"
        assert payload["companyName"] == "Prestige Luxury Rentals"
        assert payload["locationId"] == "loc-123"
        assert payload["source"] == "OpenClaw Pipeline"

    def test_custom_fields_are_list_of_id_value_pairs(self):
        payload = _build_contact_payload(_make_lead(), MOCK_CONFIG)
        cf = payload["customFields"]
        assert isinstance(cf, list)
        cf_by_id = {item["id"]: item["field_value"] for item in cf}
        assert cf_by_id["cf-001"] == "4"              # lead_score
        assert cf_by_id["cf-014"] == "lead_mia_001"   # openclaw_lead_id

    def test_tags_included(self):
        payload = _build_contact_payload(
            _make_lead(scoring_score=4, fleet_size=20, market="Miami"), MOCK_CONFIG
        )
        assert "exotiq-pipeline" in payload["tags"]
        assert "score-4" in payload["tags"]
        assert "miami" in payload["tags"]


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_valid_config(self, tmp_path):
        f = tmp_path / "ghl_config.json"
        f.write_text(json.dumps(MOCK_CONFIG))
        result = _load_config(str(f))
        assert result["location_id"] == "loc-123"

    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ghl_config.json"):
            _load_config(str(tmp_path / "missing.json"))


# ---------------------------------------------------------------------------
# push_lead_to_ghl -- pre-flight failures
# ---------------------------------------------------------------------------

class TestPushLeadPreflightChecks:
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_raises_when_score_below_3(self, mock_get, mock_cfg):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(scoring_score=2)
        with pytest.raises(ValueError, match="score"):
            push_lead_to_ghl("lead_mia_001")

    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_raises_when_not_approved(self, mock_get, mock_cfg):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(outreach_approval_status="PENDING")
        with pytest.raises(ValueError, match="approval_status"):
            push_lead_to_ghl("lead_mia_001")

    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_raises_when_no_email_or_phone(self, mock_get, mock_cfg):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(contact_email=None, contact_phone=None)
        with pytest.raises(ValueError, match="email or phone"):
            push_lead_to_ghl("lead_mia_001")


# ---------------------------------------------------------------------------
# push_lead_to_ghl -- create vs. update
# ---------------------------------------------------------------------------

class TestPushLeadToGHL:
    def _setup_mocks(self, scoring_score=4, fleet_size=20):
        lead = _make_lead(scoring_score=scoring_score, fleet_size=fleet_size)
        return lead

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_creates_new_contact_when_no_duplicate(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": []}
        mock_client.post.side_effect = [
            {"contact": {"id": "ghl-contact-001"}},
            {"opportunity": {"id": "ghl-opp-001"}},
        ]
        result = push_lead_to_ghl("lead_mia_001")
        assert result["contact_id"] == "ghl-contact-001"
        assert result["opportunity_id"] == "ghl-opp-001"
        assert result["action"] == "created"
        update_fields = mock_upd.call_args.args[1]
        assert update_fields["ghl_contact_id"] == "ghl-contact-001"
        assert update_fields["ghl_in_ghl"] == 1

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_updates_existing_contact_when_duplicate_found(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": [{"id": "existing-ghl-001"}]}
        mock_client.put.return_value = {"contact": {"id": "existing-ghl-001"}}
        mock_client.post.return_value = {"opportunity": {"id": "opp-002"}}
        result = push_lead_to_ghl("lead_mia_001")
        mock_client.put.assert_called_once()
        assert result["contact_id"] == "existing-ghl-001"
        assert result["action"] == "updated"

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_score_5_uses_gregory_personal_outreach_stage(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(scoring_score=5, fleet_size=30)
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": []}
        mock_client.post.side_effect = [
            {"contact": {"id": "ghl-s5"}},
            {"opportunity": {"id": "opp-s5"}},
        ]
        push_lead_to_ghl("lead_mia_001")
        opp_payload = mock_client.post.call_args_list[1].args[1]
        assert opp_payload["pipelineStageId"] == "stg-001"  # Gregory stage

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_score_4_uses_dm_drafted_stage(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(scoring_score=4, fleet_size=20)
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": []}
        mock_client.post.side_effect = [
            {"contact": {"id": "ghl-s4"}},
            {"opportunity": {"id": "opp-s4"}},
        ]
        push_lead_to_ghl("lead_mia_001")
        opp_payload = mock_client.post.call_args_list[1].args[1]
        assert opp_payload["pipelineStageId"] == "stg-002"  # DM Drafted


# ---------------------------------------------------------------------------
# push_approved_batch
# ---------------------------------------------------------------------------

class TestPushApprovedBatch:
    @patch("skills.ghl_push.push_lead_to_ghl")
    @patch("skills.ghl_push.get_db")
    def test_pushes_all_qualifying_leads(self, mock_get_db, mock_push):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [
            {"id": "lead_001"}, {"id": "lead_002"}
        ]
        mock_push.return_value = {"contact_id": "c1", "opportunity_id": "o1", "action": "created"}
        result = push_approved_batch()
        assert result["pushed"] == 2
        assert result["errors"] == 0

    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.push_lead_to_ghl")
    @patch("skills.ghl_push.get_db")
    def test_continues_after_validation_error(self, mock_get_db, mock_push, mock_log):
        from ghl.ghl_client import GHLValidationError
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [{"id": "lead_001"}]
        mock_push.side_effect = GHLValidationError("bad field")
        result = push_approved_batch()
        assert result["pushed"] == 0
        assert result["errors"] == 1
```

- [ ] **Step 2: Run to verify tests fail**

```
pytest tests/test_ghl_push.py -v
```
Expected: `ModuleNotFoundError: No module named 'skills.ghl_push'`

- [ ] **Step 3: Implement `skills/ghl_push.py`**

```python
"""
GHL Push Skill -- push approved leads to GoHighLevel.

Entry points:
  push_lead_to_ghl(lead_id)   -- push a single lead by ID
  push_approved_batch()       -- find all approved, un-pushed leads and push them
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ghl.ghl_client import GHLAuthError, GHLClient, GHLRateLimitError, GHLValidationError
from skills.db_utils import get_db, get_lead, log_activity, update_lead

_CONFIG_PATH = str(Path(__file__).parent.parent / "ghl" / "ghl_config.json")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_config(config_path: str = _CONFIG_PATH) -> dict:
    """Load ghl_config.json. Raises FileNotFoundError if setup_ghl.py hasn't run."""
    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(
            f"ghl_config.json not found at {config_path}. "
            "Run 'python ghl/setup_ghl.py' first."
        )
    return json.loads(p.read_text())


def _compute_monetary_value(fleet_size: Optional[int]) -> int:
    """
    Estimate annual contract value: fleet_size * $350 ADR * 365 days * 0.60 utilization.

    Returns 0 for None or zero fleet size.
    """
    try:
        size = int(fleet_size)
    except (TypeError, ValueError):
        return 0
    if size <= 0:
        return 0
    return round(size * 350 * 365 * 0.6)


def _build_tags(lead: dict) -> list[str]:
    """Compute the GHL tag array from lead attributes."""
    tags = ["exotiq-pipeline"]

    score = lead.get("scoring_score")
    if score is not None:
        tags.append(f"score-{score}")
        if int(score) == 5:
            tags.append("gregory-only")

    market = lead.get("market") or ""
    if market:
        tags.append(market.lower().replace(" ", "-"))

    fleet = lead.get("fleet_size")
    try:
        f = int(fleet)
        if f < 10:
            tags.append("under-10-fleet")
        elif f < 25:
            tags.append("10-to-24-fleet")
        else:
            tags.append("25-plus-fleet")
    except (TypeError, ValueError):
        pass

    return tags


def _build_contact_payload(lead: dict, config: dict) -> dict:
    """Map lead store fields to the GHL contact creation/update payload."""
    tags = _build_tags(lead)

    address_raw = lead.get("company_address") or ""
    parts = [p.strip() for p in address_raw.split(",")]
    address1 = parts[0] if parts else ""
    city = parts[1] if len(parts) > 1 else ""

    vehicle_types_raw = lead.get("fleet_vehicle_types") or "[]"
    try:
        vehicle_list = json.loads(vehicle_types_raw)
        vehicle_str = ", ".join(vehicle_list) if isinstance(vehicle_list, list) else str(vehicle_types_raw)
    except (json.JSONDecodeError, TypeError):
        vehicle_str = str(vehicle_types_raw)

    do_not_say_raw = lead.get("outreach_do_not_say") or "[]"
    try:
        dns_list = json.loads(do_not_say_raw)
        dns_str = ", ".join(dns_list) if isinstance(dns_list, list) else ""
    except (json.JSONDecodeError, TypeError):
        dns_str = str(do_not_say_raw)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cf = config["custom_fields"]

    custom_fields = [
        {"id": cf["lead_score"],            "field_value": str(lead.get("scoring_score") or "")},
        {"id": cf["lead_score_confidence"], "field_value": str(lead.get("scoring_confidence") or "")},
        {"id": cf["fleet_size"],            "field_value": str(lead.get("fleet_size") or "")},
        {"id": cf["fleet_size_confidence"], "field_value": str(lead.get("fleet_size_confidence") or "")},
        {"id": cf["ig_handle"],             "field_value": str(lead.get("company_ig_handle") or "")},
        {"id": cf["ig_followers"],          "field_value": str(lead.get("company_ig_followers") or "")},
        {"id": cf["google_rating"],         "field_value": str(lead.get("company_google_rating") or "")},
        {"id": cf["google_reviews"],        "field_value": str(lead.get("company_google_reviews") or "")},
        {"id": cf["vehicle_types"],         "field_value": vehicle_str},
        {"id": cf["dm_template_used"],      "field_value": str(lead.get("outreach_template_used") or "")},
        {"id": cf["dm_draft"],              "field_value": str(lead.get("outreach_dm_draft") or "")},
        {"id": cf["do_not_say"],            "field_value": dns_str},
        {"id": cf["enrichment_sources"],    "field_value": str(lead.get("lead_source") or "")},
        {"id": cf["openclaw_lead_id"],      "field_value": str(lead.get("id") or "")},
        {"id": cf["pipeline_entry_date"],   "field_value": today},
    ]

    return {
        "firstName": lead.get("contact_first_name") or "",
        "lastName": lead.get("contact_last_name") or "",
        "email": lead.get("contact_email") or "",
        "phone": lead.get("contact_phone") or "",
        "companyName": lead.get("company") or "",
        "address1": address1,
        "city": city,
        "website": lead.get("company_website") or "",
        "locationId": config["location_id"],
        "source": "OpenClaw Pipeline",
        "tags": tags,
        "customFields": custom_fields,
    }


def _log_ghl_sync(
    lead_id: Optional[str],
    ghl_contact_id: Optional[str],
    endpoint: str,
    http_status: int,
    direction: str = "outbound",
    payload_summary: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Write a row to the ghl_sync_log table."""
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO ghl_sync_log
              (timestamp, direction, lead_id, ghl_contact_id, endpoint,
               http_status, payload_summary, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                direction,
                lead_id,
                ghl_contact_id,
                endpoint,
                http_status,
                payload_summary,
                error_message,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _dedup_check(
    client: GHLClient,
    location_id: str,
    email: Optional[str],
    phone: Optional[str],
) -> Optional[str]:
    """
    Check for an existing GHL contact by email or phone.

    Returns the existing contact's GHL ID, or None if no match.
    """
    params: dict[str, str] = {"locationId": location_id}
    if email:
        params["email"] = email
    elif phone:
        params["number"] = phone
    else:
        return None

    data = client.get("/contacts/search/duplicate", params=params)
    contacts = data.get("contacts") or []
    return contacts[0]["id"] if contacts else None


def _create_opportunity(
    client: GHLClient,
    contact_id: str,
    lead: dict,
    config: dict,
) -> str:
    """
    Create a GHL opportunity in the Exotiq pipeline.

    Stage assignment:
      Score 5 -> "Gregory -- Personal Outreach"
      Score 3-4 -> "DM Drafted"

    Returns the new opportunity ID.
    """
    score = int(lead.get("scoring_score") or 3)
    stage_name = "Gregory -- Personal Outreach" if score == 5 else "DM Drafted"
    stage_id = config["stages"].get(stage_name, "")
    market = lead.get("market") or ""

    payload = {
        "pipelineId": config["pipeline_id"],
        "pipelineStageId": stage_id,
        "name": f"{lead.get('company', 'Unknown')} - {market}",
        "contactId": contact_id,
        "monetaryValue": _compute_monetary_value(lead.get("fleet_size")),
        "locationId": config["location_id"],
        "status": "open",
    }
    resp = client.post("/opportunities/", payload)
    opp = resp.get("opportunity") or resp
    return opp.get("id", "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def push_lead_to_ghl(lead_id: str, config_path: str = _CONFIG_PATH) -> dict:
    """
    Push a single lead to GHL.

    Pre-flight checks:
      - score >= 3
      - approval_status == APPROVED
      - has company + first name + (email or phone)

    Dedup: checks for existing GHL contact by email or phone.
      If found: PUT (update). If not: POST (create).

    After contact: creates GHL opportunity in the correct pipeline stage.

    Stores ghl_contact_id, ghl_opportunity_id, ghl_tags, ghl_pipeline_stage
    back in the lead record. Logs to activity_log and ghl_sync_log.

    Args:
        lead_id:     Lead primary key.
        config_path: Path to ghl_config.json (override for tests).

    Returns:
        Dict with ``contact_id``, ``opportunity_id``, ``action`` keys.

    Raises:
        ValueError:         Pre-flight check failed.
        FileNotFoundError:  ghl_config.json missing (run setup_ghl.py).
        GHLAuthError:       Token invalid -- stop all pushes.
        GHLRateLimitError:  Rate limited (bubble up to batch handler).
    """
    config = _load_config(config_path)

    lead = get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead '{lead_id}' not found.")

    # Pre-flight checks
    try:
        score = int(lead.get("scoring_score") or 0)
    except (TypeError, ValueError):
        score = 0
    if score < 3:
        raise ValueError(
            f"Lead {lead_id} score is {score} -- minimum is 3 for GHL push."
        )

    approval = (lead.get("outreach_approval_status") or "").upper()
    if approval != "APPROVED":
        raise ValueError(
            f"Lead {lead_id} approval_status is '{approval}' -- must be APPROVED."
        )

    if not lead.get("company"):
        raise ValueError(f"Lead {lead_id} has no company name.")
    if not lead.get("contact_first_name"):
        raise ValueError(f"Lead {lead_id} has no contact first name.")
    if not lead.get("contact_email") and not lead.get("contact_phone"):
        raise ValueError(
            f"Lead {lead_id} must have at least one of email or phone."
        )

    client = GHLClient()
    location_id = config["location_id"]

    # Dedup check
    existing_id = _dedup_check(
        client, location_id,
        lead.get("contact_email"),
        lead.get("contact_phone"),
    )

    payload = _build_contact_payload(lead, config)
    action: str

    if existing_id:
        resp = client.put(f"/contacts/{existing_id}", payload)
        contact_id = existing_id
        action = "updated"
        _log_ghl_sync(
            lead_id, contact_id, f"PUT /contacts/{existing_id}", 200,
            payload_summary=f"Updated contact for {lead.get('company')}",
        )
    else:
        resp = client.post("/contacts/", payload)
        contact = resp.get("contact") or resp
        contact_id = contact.get("id", "")
        action = "created"
        _log_ghl_sync(
            lead_id, contact_id, "POST /contacts/", 201,
            payload_summary=f"Created contact for {lead.get('company')}",
        )

    # Create opportunity
    opp_id = _create_opportunity(client, contact_id, lead, config)
    _log_ghl_sync(
        lead_id, contact_id, "POST /opportunities/", 201,
        payload_summary=f"Created opportunity {opp_id}",
    )

    # Update lead record with GHL IDs
    tags = _build_tags(lead)
    stage_name = "Gregory -- Personal Outreach" if score == 5 else "DM Drafted"
    update_lead(lead_id, {
        "ghl_contact_id": contact_id,
        "ghl_opportunity_id": opp_id,
        "ghl_in_ghl": 1,
        "ghl_tags": json.dumps(tags),
        "ghl_last_sync": datetime.now(timezone.utc).isoformat(),
        "ghl_pipeline_stage": stage_name,
    })

    log_activity(
        type="ghl_push",
        description=(
            f"Pushed {lead.get('company')} to GHL. "
            f"Contact ID: {contact_id}. "
            f"Opportunity: {opp_id}. "
            f"Stage: {stage_name}. "
            f"Tags: {', '.join(tags)}. "
            f"Action: {action}."
        ),
        lead_id=lead_id,
        agent="ghl_push",
    )

    return {"contact_id": contact_id, "opportunity_id": opp_id, "action": action}


def push_approved_batch() -> dict:
    """
    Find all approved, un-pushed leads with score >= 3 and push them to GHL.

    Error handling per spec:
      - GHLAuthError (401/403): stop the batch immediately, re-raise.
      - GHLValidationError (422): log, skip this lead, continue.
      - Any other exception: log, skip this lead, continue.

    Returns:
        Dict with ``pushed`` and ``errors`` counts.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT id FROM leads
            WHERE outreach_approval_status = 'APPROVED'
              AND (ghl_in_ghl = 0 OR ghl_in_ghl IS NULL)
              AND scoring_score >= 3
              AND company IS NOT NULL
              AND contact_first_name IS NOT NULL
              AND (contact_email IS NOT NULL OR contact_phone IS NOT NULL)
            ORDER BY scoring_score DESC, created_at ASC
            """
        ).fetchall()
    finally:
        conn.close()

    pushed = 0
    errors = 0

    for row in rows:
        lead_id = row["id"]
        try:
            push_lead_to_ghl(lead_id)
            pushed += 1
        except GHLAuthError:
            log_activity(
                type="ghl_push",
                description=f"GHL auth error -- stopping batch. Lead {lead_id} not pushed.",
                agent="ghl_push",
            )
            raise  # Auth failures are fatal for the batch
        except (GHLValidationError, Exception) as e:
            log_activity(
                type="ghl_push",
                description=f"Error pushing {lead_id}: {e}. Skipping.",
                lead_id=lead_id,
                agent="ghl_push",
            )
            errors += 1

    return {"pushed": pushed, "errors": errors}
```

- [ ] **Step 4: Run tests and verify all pass**

```
pytest tests/test_ghl_push.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/ghl_push.py tests/test_ghl_push.py
git commit -m "feat: add ghl_push skill -- push approved leads to GHL contacts and opportunities"
```

---

## Task 4: Netlify Webhook Function

**Files:**
- Create: `netlify/functions/ghl-webhook.js`
- Create: `netlify/functions/health.js`
- Create: `netlify/functions/event_queue/.gitkeep`

No Python tests. Manual test with curl after deploy or local `netlify dev`.

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p netlify/functions/event_queue
```

- [ ] **Step 2: Create `netlify/functions/event_queue/.gitkeep`**

Empty file to track the directory in git.

- [ ] **Step 3: Create `netlify/functions/health.js`**

```javascript
// netlify/functions/health.js
// Health check endpoint. Access at: /.netlify/functions/health

exports.handler = async (event, context) => {
  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      status: "ok",
      service: "exotiq-ghl-listener",
      timestamp: new Date().toISOString(),
    }),
  };
};
```

- [ ] **Step 4: Create `netlify/functions/ghl-webhook.js`**

```javascript
// netlify/functions/ghl-webhook.js
//
// Receives GHL outbound webhook events and writes them to an event queue
// for skills/ghl_listener_poller.py to process.
//
// SIGNATURE VERIFICATION (X-GHL-Signature, Ed25519):
//   GHL signs the raw request body with Ed25519. To enable in production:
//   1. npm install tweetnacl
//   2. Set GHL_WEBHOOK_PUBLIC_KEY env var to the base64-encoded public key
//      from https://services.leadconnectorhq.com/.well-known/webhooks-public-key
//   3. Uncomment the verification block in verifySignature() below.
//
// EVENT QUEUE:
//   Events are written as timestamped JSON files to QUEUE_PATH.
//   Set the QUEUE_PATH env var to a path readable by the Python poller.
//   For local dev: point QUEUE_PATH to netlify/functions/event_queue/
//   For production: replace with a persistent store (Netlify Blobs, Supabase).

const fs = require("fs");
const path = require("path");

const SUPPORTED_EVENTS = new Set([
  "ContactCreate",
  "ContactUpdate",
  "OpportunityStatusUpdate",
  "NoteCreate",
  "InboundMessage",
  "AppointmentCreate",
]);

const QUEUE_PATH =
  process.env.QUEUE_PATH ||
  path.join(__dirname, "event_queue");

function verifySignature(body, signature) {
  // STUB: Ed25519 verification. Logs a warning in v1 but does not block.
  //
  // To enable:
  // const nacl = require('tweetnacl');
  // const publicKey = Buffer.from(process.env.GHL_WEBHOOK_PUBLIC_KEY, 'base64');
  // const sigBytes = Buffer.from(signature, 'base64');
  // const bodyBytes = Buffer.from(body, 'utf-8');
  // return nacl.sign.detached.verify(bodyBytes, sigBytes, publicKey);
  if (!signature) {
    console.warn("[ghl-webhook] No X-GHL-Signature header -- verification not enforced in v1");
  }
  return true;
}

function writeEventToQueue(event) {
  const timestamp = Date.now();
  const eventType = (event.type || "unknown").replace(/[^a-zA-Z0-9_-]/g, "_");
  const filename = `${timestamp}_${eventType}.json`;
  const filepath = path.join(QUEUE_PATH, filename);

  if (!fs.existsSync(QUEUE_PATH)) {
    fs.mkdirSync(QUEUE_PATH, { recursive: true });
  }

  fs.writeFileSync(filepath, JSON.stringify(event, null, 2), "utf-8");
  return filename;
}

exports.handler = async (netlifyEvent, context) => {
  if (netlifyEvent.httpMethod !== "POST") {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: "Method not allowed" }),
    };
  }

  const signature = netlifyEvent.headers["x-ghl-signature"] || "";
  const rawBody = netlifyEvent.body || "";

  verifySignature(rawBody, signature);

  let payload;
  try {
    payload = JSON.parse(rawBody);
  } catch (e) {
    console.error("[ghl-webhook] Invalid JSON body:", e.message);
    return {
      statusCode: 400,
      body: JSON.stringify({ error: "Invalid JSON body" }),
    };
  }

  const eventType = payload.type || payload.event || "unknown";

  if (!SUPPORTED_EVENTS.has(eventType)) {
    console.log(`[ghl-webhook] Ignoring unsupported event type: ${eventType}`);
    return {
      statusCode: 200,
      body: JSON.stringify({ status: "ignored", type: eventType }),
    };
  }

  const enrichedEvent = {
    ...payload,
    type: eventType,
    received_at: new Date().toISOString(),
  };

  let filename;
  try {
    filename = writeEventToQueue(enrichedEvent);
  } catch (e) {
    console.error("[ghl-webhook] Failed to write event to queue:", e.message);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: "Failed to queue event" }),
    };
  }

  console.log(`[ghl-webhook] Queued ${eventType} -> ${filename}`);

  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "queued", type: eventType, file: filename }),
  };
};
```

- [ ] **Step 5: Manual smoke test (after setup)**

```bash
# Start Netlify dev server:
npx netlify dev

# Test health endpoint:
curl http://localhost:8888/.netlify/functions/health

# Test webhook with a ContactUpdate event:
curl -X POST http://localhost:8888/.netlify/functions/ghl-webhook \
  -H "Content-Type: application/json" \
  -d '{"type":"ContactUpdate","contactId":"test-001","contact":{"email":"test@test.com"}}'

# Verify file appears in event_queue/
ls netlify/functions/event_queue/
```
Expected: health returns `{"status":"ok",...}`, webhook returns `{"status":"queued",...}`, JSON file appears in event_queue.

- [ ] **Step 6: Commit**

```bash
git add netlify/functions/ghl-webhook.js netlify/functions/health.js netlify/functions/event_queue/.gitkeep
git commit -m "feat: add Netlify GHL webhook listener and health endpoint"
```

---

## Task 5: GHL Listener Poller

**Files:**
- Create: `skills/ghl_listener_poller.py`
- Test: `tests/test_ghl_listener_poller.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ghl_listener_poller.py
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.ghl_listener_poller import (
    _handle_appointment_create,
    _handle_contact_update,
    _handle_inbound_message,
    _handle_note_create,
    _handle_opportunity_status_update,
    poll_event_queue,
    process_event,
)


def _make_event(event_type: str, **kwargs) -> dict:
    base = {
        "type": event_type,
        "received_at": "2026-04-03T12:00:00Z",
        "locationId": "loc-123",
    }
    base.update(kwargs)
    return base


class TestHandleContactUpdate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_updates_contact_fields(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event(
            "ContactUpdate",
            contactId="ghl-001",
            contact={"email": "new@email.com", "phone": "+1555000"},
        )
        _handle_contact_update(event)
        fields = mock_update.call_args.args[1]
        assert fields["contact_email"] == "new@email.com"
        assert fields["contact_phone"] == "+1555000"

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_noop_when_lead_not_found(self, mock_find, mock_log):
        mock_find.return_value = None
        _handle_contact_update(_make_event("ContactUpdate", contactId="unknown"))
        # no exception -- just returns


class TestHandleOpportunityStatusUpdate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_updates_pipeline_stage(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event(
            "OpportunityStatusUpdate",
            contactId="ghl-001",
            opportunity={"pipelineStage": {"name": "Responded -- Warm"}},
        )
        _handle_opportunity_status_update(event)
        fields = mock_update.call_args.args[1]
        assert fields["ghl_pipeline_stage"] == "Responded -- Warm"
        assert fields["outreach_status"] == "Responded -- Warm"

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_demo_scheduled_sets_flag(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event(
            "OpportunityStatusUpdate",
            contactId="ghl-001",
            opportunity={"pipelineStage": {"name": "Demo Scheduled"}},
        )
        _handle_opportunity_status_update(event)
        fields = mock_update.call_args.args[1]
        assert fields["outreach_demo_scheduled"] == 1


class TestHandleNoteCreate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.get_lead")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_appends_note_to_existing(self, mock_find, mock_update, mock_get, mock_log):
        mock_find.return_value = "lead_mia_001"
        mock_get.return_value = {"id": "lead_mia_001", "notes": "Old note.", "contact_phone": None, "fleet_size": None}
        event = _make_event("NoteCreate", contactId="ghl-001", note={"body": "New intel."})
        _handle_note_create(event)
        fields = mock_update.call_args.args[1]
        assert "Old note." in fields["notes"]
        assert "New intel." in fields["notes"]

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.get_lead")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_sets_note_when_none_exists(self, mock_find, mock_update, mock_get, mock_log):
        mock_find.return_value = "lead_mia_001"
        mock_get.return_value = {"id": "lead_mia_001", "notes": None, "contact_phone": None, "fleet_size": None}
        event = _make_event("NoteCreate", contactId="ghl-001", note={"body": "First note."})
        _handle_note_create(event)
        fields = mock_update.call_args.args[1]
        assert "First note." in fields["notes"]


class TestHandleInboundMessage:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_sets_response_received(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("InboundMessage", contactId="ghl-001",
                            message={"body": "Hey, sounds interesting."})
        _handle_inbound_message(event)
        fields = mock_update.call_args.args[1]
        assert fields["outreach_response_received"] == 1

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_positive_message_categorized_as_interested(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("InboundMessage", contactId="ghl-001",
                            message={"body": "Yes, I'm interested! Let's schedule."})
        _handle_inbound_message(event)
        assert mock_update.call_args.args[1]["outreach_response_category"] == "interested"

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_negative_message_categorized_as_cold(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("InboundMessage", contactId="ghl-001",
                            message={"body": "Not interested, please stop."})
        _handle_inbound_message(event)
        assert mock_update.call_args.args[1]["outreach_response_category"] == "cold"


class TestHandleAppointmentCreate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_sets_demo_scheduled(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("AppointmentCreate", contactId="ghl-001",
                            appointment={"startTime": "2026-04-10T14:00:00Z", "title": "Demo"})
        _handle_appointment_create(event)
        assert mock_update.call_args.args[1]["outreach_demo_scheduled"] == 1


class TestPollEventQueue:
    def test_processes_and_archives_event_files(self, tmp_path):
        queue_dir = tmp_path / "event_queue"
        queue_dir.mkdir()
        processed_dir = queue_dir / "processed"

        event_data = {
            "type": "ContactUpdate",
            "contactId": "ghl-001",
            "contact": {"email": "test@test.com"},
            "received_at": "2026-04-03T12:00:00Z",
        }
        event_file = queue_dir / "1234567890_ContactUpdate.json"
        event_file.write_text(json.dumps(event_data))

        with patch("skills.ghl_listener_poller._handle_contact_update"), \
             patch("skills.ghl_listener_poller._find_lead_by_ghl_id", return_value="lead_001"), \
             patch("skills.ghl_listener_poller.update_lead"), \
             patch("skills.ghl_listener_poller.log_activity"):
            result = poll_event_queue(queue_path=str(queue_dir))

        assert result["processed"] == 1
        assert result["errors"] == 0
        assert not event_file.exists()
        assert (processed_dir / "1234567890_ContactUpdate.json").exists()

    def test_ignores_non_json_files(self, tmp_path):
        queue_dir = tmp_path / "eq"
        queue_dir.mkdir()
        (queue_dir / ".gitkeep").write_text("")
        result = poll_event_queue(queue_path=str(queue_dir))
        assert result["processed"] == 0

    def test_handles_malformed_json_gracefully(self, tmp_path):
        queue_dir = tmp_path / "eq"
        queue_dir.mkdir()
        (queue_dir / "123_bad.json").write_text("{not valid json")
        with patch("skills.ghl_listener_poller.log_activity"):
            result = poll_event_queue(queue_path=str(queue_dir))
        assert result["errors"] == 1

    def test_returns_zero_counts_when_queue_dir_missing(self, tmp_path):
        result = poll_event_queue(queue_path=str(tmp_path / "nonexistent"))
        assert result == {"processed": 0, "errors": 0}
```

- [ ] **Step 2: Run to verify tests fail**

```
pytest tests/test_ghl_listener_poller.py -v
```
Expected: `ModuleNotFoundError: No module named 'skills.ghl_listener_poller'`

- [ ] **Step 3: Implement `skills/ghl_listener_poller.py`**

```python
"""
GHL Listener Poller -- sync GHL webhook events to the SQLite lead store.

The Netlify Function (netlify/functions/ghl-webhook.js) writes incoming GHL
events as timestamped JSON files to the event queue directory. This poller
reads those files, updates the lead store, and archives processed files.

Run periodically (e.g., every 5 minutes) from OpenClaw's scheduled tasks:
    from skills.ghl_listener_poller import poll_event_queue
    poll_event_queue()
"""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from skills.db_utils import get_db, get_lead, log_activity, update_lead

_DEFAULT_QUEUE_PATH = str(
    Path(__file__).parent.parent / "netlify" / "functions" / "event_queue"
)


# ---------------------------------------------------------------------------
# Lead lookup helper
# ---------------------------------------------------------------------------

def _find_lead_by_ghl_id(ghl_contact_id: str) -> Optional[str]:
    """
    Look up a lead_id by GHL contact ID.

    Returns the lead_id string, or None if not found.
    """
    if not ghl_contact_id:
        return None
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id FROM leads WHERE ghl_contact_id = ?",
            (ghl_contact_id,),
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Event handlers -- one per GHL event type
# ---------------------------------------------------------------------------

def _handle_contact_update(event: dict) -> None:
    """Sync updated contact fields back to lead store (email, phone, name)."""
    ghl_contact_id = event.get("contactId") or event.get("id")
    lead_id = _find_lead_by_ghl_id(ghl_contact_id)
    if not lead_id:
        return

    contact = event.get("contact") or {}
    fields: dict[str, Any] = {}
    if contact.get("email"):
        fields["contact_email"] = contact["email"]
    if contact.get("phone"):
        fields["contact_phone"] = contact["phone"]
    if contact.get("firstName"):
        fields["contact_first_name"] = contact["firstName"]
    if contact.get("lastName"):
        fields["contact_last_name"] = contact["lastName"]
    if contact.get("companyName"):
        fields["company"] = contact["companyName"]

    if fields:
        update_lead(lead_id, fields)
        log_activity(
            type="ghl_sync",
            description=f"GHL sync: contact updated. Fields: {list(fields.keys())}",
            lead_id=lead_id,
            source="ghl_sync",
            agent="ghl_listener_poller",
        )


def _handle_opportunity_status_update(event: dict) -> None:
    """
    Sync pipeline stage changes to lead store.

    Special cases:
      "Demo Scheduled" -> set outreach_demo_scheduled = 1
    """
    ghl_contact_id = event.get("contactId") or event.get("id")
    lead_id = _find_lead_by_ghl_id(ghl_contact_id)
    if not lead_id:
        return

    opportunity = event.get("opportunity") or {}
    stage = opportunity.get("pipelineStage") or {}
    stage_name = stage.get("name") or opportunity.get("stageName") or ""
    if not stage_name:
        return

    fields: dict[str, Any] = {
        "ghl_pipeline_stage": stage_name,
        "outreach_status": stage_name,
        "ghl_last_sync": datetime.now(timezone.utc).isoformat(),
    }
    if stage_name == "Demo Scheduled":
        fields["outreach_demo_scheduled"] = 1

    update_lead(lead_id, fields)

    description = f"GHL sync: moved to '{stage_name}'"
    if stage_name == "Responded -- Warm":
        description += " -- HOT LEAD flagged"

    log_activity(
        type="ghl_sync",
        description=description,
        lead_id=lead_id,
        source="ghl_sync",
        agent="ghl_listener_poller",
    )


def _handle_note_create(event: dict) -> None:
    """
    Append GHL note to lead store. Parses structured intel from note text:
    - Phone numbers -> contact_phone (if lead has none)
    - Fleet size mentions -> fleet_size (if lead has none)
    """
    ghl_contact_id = event.get("contactId") or event.get("id")
    lead_id = _find_lead_by_ghl_id(ghl_contact_id)
    if not lead_id:
        return

    note = event.get("note") or {}
    note_text = note.get("body") or note.get("text") or ""
    if not note_text:
        return

    lead = get_lead(lead_id)
    if lead is None:
        return

    existing_notes = lead.get("notes") or ""
    ts = event.get("received_at", datetime.now(timezone.utc).isoformat())
    separator = "\n---\n" if existing_notes else ""
    new_notes = f"{existing_notes}{separator}[GHL note, {ts}] {note_text}"

    fields: dict[str, Any] = {"notes": new_notes}

    # Parse phone number from note text if lead has none
    if not lead.get("contact_phone"):
        phone_match = re.search(
            r"(\+1[\s\d\-]{10,}|\b\d{10}\b)", note_text
        )
        if phone_match:
            fields["contact_phone"] = re.sub(r"[\s\-]", "", phone_match.group(1))
            fields["contact_phone_source"] = "ghl_sync"

    # Parse fleet size if lead has none
    if not lead.get("fleet_size"):
        fleet_match = re.search(
            r"(?:fleet of|has)\s+(\d+)|(\d+)\s+(?:cars?|vehicles?|fleet)",
            note_text, re.IGNORECASE
        )
        if fleet_match:
            size_str = fleet_match.group(1) or fleet_match.group(2)
            try:
                fields["fleet_size"] = int(size_str)
                fields["fleet_size_source"] = "ghl_sync"
                fields["fleet_size_confidence"] = "INFERRED"
            except ValueError:
                pass

    update_lead(lead_id, fields)
    log_activity(
        type="ghl_sync",
        description=f"GHL sync: note added. Preview: {note_text[:80]}",
        lead_id=lead_id,
        source="ghl_sync",
        agent="ghl_listener_poller",
    )


def _handle_inbound_message(event: dict) -> None:
    """
    Set response_received and categorize intent.

    Positive keywords -> "interested"
    Negative keywords -> "cold"
    Anything else -> "inquiry"
    """
    ghl_contact_id = event.get("contactId") or event.get("id")
    lead_id = _find_lead_by_ghl_id(ghl_contact_id)
    if not lead_id:
        return

    message = event.get("message") or {}
    body = (message.get("body") or "").lower()

    negative = {"not interested", "remove me", "unsubscribe", "stop", "don't contact"}
    positive = {"interested", "yes", "love to", "let's talk", "schedule", "call", "demo"}

    if any(kw in body for kw in negative):
        category = "cold"
    elif any(kw in body for kw in positive):
        category = "interested"
    else:
        category = "inquiry"

    ts = event.get("received_at") or datetime.now(timezone.utc).isoformat()
    update_lead(lead_id, {
        "outreach_response_received": 1,
        "outreach_response_category": category,
        "outreach_response_date": ts,
        "ghl_last_sync": datetime.now(timezone.utc).isoformat(),
    })

    preview = body[:80] + ("..." if len(body) > 80 else "")
    log_activity(
        type="ghl_sync",
        description=f"GHL sync: inbound message. Category: {category}. Preview: {preview}",
        lead_id=lead_id,
        source="ghl_sync",
        agent="ghl_listener_poller",
    )


def _handle_appointment_create(event: dict) -> None:
    """Mark demo as scheduled and log appointment details."""
    ghl_contact_id = event.get("contactId") or event.get("id")
    lead_id = _find_lead_by_ghl_id(ghl_contact_id)
    if not lead_id:
        return

    appointment = event.get("appointment") or {}
    start_time = appointment.get("startTime") or appointment.get("start") or ""
    title = appointment.get("title") or "Appointment"

    update_lead(lead_id, {
        "outreach_demo_scheduled": 1,
        "ghl_last_sync": datetime.now(timezone.utc).isoformat(),
    })
    log_activity(
        type="ghl_sync",
        description=f"GHL sync: demo scheduled -- '{title}' at {start_time}",
        lead_id=lead_id,
        source="ghl_sync",
        agent="ghl_listener_poller",
    )


# ---------------------------------------------------------------------------
# Event router
# ---------------------------------------------------------------------------

_EVENT_HANDLERS = {
    "ContactCreate": _handle_contact_update,
    "ContactUpdate": _handle_contact_update,
    "OpportunityStatusUpdate": _handle_opportunity_status_update,
    "NoteCreate": _handle_note_create,
    "InboundMessage": _handle_inbound_message,
    "AppointmentCreate": _handle_appointment_create,
}


def process_event(event: dict) -> None:
    """Route a parsed event dict to the appropriate handler. Unknown types are ignored."""
    event_type = event.get("type") or event.get("event") or "unknown"
    handler = _EVENT_HANDLERS.get(event_type)
    if handler is None:
        log_activity(
            type="ghl_sync",
            description=f"GHL sync: ignored unsupported event type '{event_type}'",
            source="ghl_sync",
            agent="ghl_listener_poller",
        )
        return
    handler(event)


# ---------------------------------------------------------------------------
# Poller
# ---------------------------------------------------------------------------

def poll_event_queue(queue_path: str = _DEFAULT_QUEUE_PATH) -> dict:
    """
    Scan the event queue directory for unprocessed JSON files.

    For each .json file (excluding .gitkeep):
      1. Parse the JSON event
      2. Route to the appropriate handler
      3. Move the file to a 'processed/' subdirectory

    Malformed or failing files are moved to processed/ with an _ERROR suffix.

    Args:
        queue_path: Directory to scan. Override in tests with tmp_path.

    Returns:
        Dict with ``processed`` and ``errors`` counts.
    """
    queue_dir = Path(queue_path)
    if not queue_dir.exists():
        return {"processed": 0, "errors": 0}

    processed_dir = queue_dir / "processed"
    processed_dir.mkdir(exist_ok=True)

    processed = 0
    errors = 0

    for filepath in sorted(queue_dir.glob("*.json")):
        if filepath.name == ".gitkeep":
            continue

        try:
            raw = filepath.read_text(encoding="utf-8")
            event = json.loads(raw)
            process_event(event)
            shutil.move(str(filepath), str(processed_dir / filepath.name))
            processed += 1
        except json.JSONDecodeError as e:
            error_name = filepath.stem + "_PARSE_ERROR.json"
            shutil.move(str(filepath), str(processed_dir / error_name))
            log_activity(
                type="ghl_sync",
                description=f"GHL sync: failed to parse {filepath.name}: {e}",
                source="ghl_sync",
                agent="ghl_listener_poller",
            )
            errors += 1
        except Exception as e:
            error_name = filepath.stem + "_ERROR.json"
            shutil.move(str(filepath), str(processed_dir / error_name))
            log_activity(
                type="ghl_sync",
                description=f"GHL sync: error processing {filepath.name}: {e}",
                source="ghl_sync",
                agent="ghl_listener_poller",
            )
            errors += 1

    return {"processed": processed, "errors": errors}
```

- [ ] **Step 4: Run tests and verify all pass**

```
pytest tests/test_ghl_listener_poller.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/ghl_listener_poller.py tests/test_ghl_listener_poller.py
git commit -m "feat: add GHL listener poller -- sync webhook events to SQLite"
```

---

## Task 6: Config Files and Requirements

**Files:**
- Create: `netlify.toml`
- Update: `requirements.txt`

- [ ] **Step 1: Create `netlify.toml`**

```toml
# netlify.toml -- Netlify build and functions configuration
# Dashboard and GHL webhook listener deploy together from this repo.

[build]
  publish = "public"
  functions = "netlify/functions"

[functions]
  node_bundler = "esbuild"

# Netlify serves /.netlify/functions/* automatically before checking redirects.
# This SPA redirect catches all other routes and serves index.html.
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[dev]
  port = 3000
  functions = "netlify/functions"
```

- [ ] **Step 2: Update `requirements.txt`**

```
openpyxl>=3.1.0
requests>=2.31.0
flask>=3.0.0
pytest>=8.0.0
python-dotenv>=1.0.0
cryptography>=42.0.0
```

- [ ] **Step 3: Run the full test suite**

```
pytest -v
```
Expected: all 235 existing tests + all new Phase 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add netlify.toml requirements.txt
git commit -m "feat: add netlify.toml and update requirements for Phase 3"
```

---

## Spec Coverage Check

| Spec Section | Covered By |
|---|---|
| 3.1 Trigger conditions (score >= 3, APPROVED, dedup) | `push_lead_to_ghl` pre-flight + `_dedup_check` |
| 3.2 Contact creation payload (native + customFields) | `_build_contact_payload` |
| 3.3 All 15 custom fields | `CUSTOM_FIELD_DEFS` (15 entries, tested) |
| 3.4 All 16 pipeline stages | `PIPELINE_STAGES` (16 entries, tested) |
| 5.1 ghl-push process (8 steps) | `push_lead_to_ghl` steps 1-8 |
| 5.1 Monetary value formula | `_compute_monetary_value` (fleet * 350 * 365 * 0.6) |
| 5.1 Tags: score, market, fleet tier, gregory-only | `_build_tags` (all tested) |
| 5.1 Error handling (401 stop, 422 skip, 429/5xx bubble) | `push_approved_batch` + GHLClient |
| 5.2 ContactUpdate | `_handle_contact_update` |
| 5.2 OpportunityStatusUpdate (stage + demo flag) | `_handle_opportunity_status_update` |
| 5.2 NoteCreate (append + parse phone/fleet) | `_handle_note_create` |
| 5.2 InboundMessage (response + categorize) | `_handle_inbound_message` |
| 5.2 AppointmentCreate | `_handle_appointment_create` |
| GHL rate limit 100/10s | `RateLimiter` in `ghl_client.py` |
| X-GHL-Signature verification | Stubbed with full documentation in `ghl-webhook.js` |
| ghl_sync_log writes | `_log_ghl_sync` called after every GHL API call |
| activity_log writes | `log_activity` called in all skills |
| Idempotent setup | `ensure_custom_fields` + `ensure_pipeline` check before creating |
| Config persistence | `write_config` -> `ghl/ghl_config.json` |
| Event queue + poller | Task 4 + Task 5 |
