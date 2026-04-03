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
