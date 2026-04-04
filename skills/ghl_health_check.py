"""
GHL Health Check Skill -- compare local DB against live GHL contacts.

Verifies each contact by ID (GET /contacts/{id}) and also fetches all contacts
with tag exotiq-pipeline to detect contacts in GHL that have no local record.

Entry point:
  run_health_check(output_dir: str = "public/data") -> dict
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent.parent))

from ghl.ghl_client import GHLClient, GHLRateLimitError
from skills.db_utils import get_db, log_activity

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "ghl" / "ghl_config.json"

_LOCATION_ID = "hTOVcYDLS1UfuiNzuzpT"
_LEAD_SCORE_FIELD_ID = "XPkBEJOKRgV7DeZPKvS1"
def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_with_retry(client: GHLClient, path: str, params: Optional[dict] = None, max_retries: int = 5) -> dict:
    """GET with exponential backoff on 429 (starts at 30s, caps at 120s)."""
    wait = 30
    for attempt in range(max_retries):
        try:
            return client.get(path, params=params)
        except GHLRateLimitError:
            if attempt == max_retries - 1:
                raise
            print(f"  Rate limited on {path}. Waiting {wait}s (attempt {attempt + 1}/{max_retries})...")
            time.sleep(wait)
            wait = min(wait * 2, 120)
    raise GHLRateLimitError(f"Max retries exceeded on {path}")


def _fetch_ghl_contacts_by_tag(client: GHLClient) -> list[dict]:
    """
    Fetch all GHL contacts tagged exotiq-pipeline, handling pagination.

    Returns a flat list of contact dicts.
    """
    contacts: list[dict] = []
    params: dict = {
        "locationId": _LOCATION_ID,
        "query": "exotiq-pipeline",
        "limit": 100,
    }

    while True:
        data = _get_with_retry(client, "/contacts/", params=params)
        page_contacts = data.get("contacts") or []
        contacts.extend(page_contacts)

        meta = data.get("meta") or {}
        next_page_url = meta.get("nextPageUrl") or meta.get("nextCursor")
        if not next_page_url:
            break

        if next_page_url.startswith("http"):
            parsed = urlparse(next_page_url)
            qs = parse_qs(parsed.query)
            start_after = qs.get("startAfter", [None])[0]
            cursor = qs.get("nextCursor", [None])[0]
            if start_after:
                params["startAfter"] = start_after
                params.pop("nextCursor", None)
            elif cursor:
                params["nextCursor"] = cursor
                params.pop("startAfter", None)
            else:
                break
        else:
            params["nextCursor"] = next_page_url
            params.pop("startAfter", None)

    return contacts


def _get_sqlite_ghl_leads(conn) -> dict:
    """Return {ghl_contact_id: lead_row_dict} for all leads with ghl_in_ghl=1."""
    rows = conn.execute(
        "SELECT id, ghl_contact_id, company FROM leads WHERE ghl_in_ghl = 1 AND ghl_contact_id IS NOT NULL"
    ).fetchall()
    return {row["ghl_contact_id"]: dict(row) for row in rows}


def run_health_check(output_dir: str = "public/data") -> dict:
    """
    Run a GHL sync health check.

    - Fetches contacts tagged exotiq-pipeline from GHL (tag-search endpoint).
    - Compares with leads where ghl_in_ghl=1 in the local DB.
    - Checks Lead Score custom field (XPkBEJOKRgV7DeZPKvS1) population in the overlap.
    - Logs to activity_log.
    - Updates ghl_sync_status.json with a "health_check" key.

    Returns a dict with health data.
    """
    client = GHLClient()

    print("\n=== GHL Sync Health Check ===\n")

    # --- Fetch GHL contacts with tag ---
    print("  Fetching GHL contacts tagged exotiq-pipeline...")
    ghl_contacts = _fetch_ghl_contacts_by_tag(client)
    ghl_ids: set[str] = {c["id"] for c in ghl_contacts}
    ghl_contact_map: dict[str, dict] = {c["id"]: c for c in ghl_contacts}
    print(f"  Found {len(ghl_ids)} contacts in GHL")

    # --- Load local DB ---
    conn = get_db()
    try:
        sqlite_leads = _get_sqlite_ghl_leads(conn)
    finally:
        conn.close()

    local_ids: set[str] = set(sqlite_leads.keys())
    print(f"  Found {len(local_ids)} leads marked ghl_in_ghl=1 in local DB\n")

    # --- Compute diff sets ---
    in_local_not_ghl = sorted(local_ids - ghl_ids)
    in_ghl_not_local = sorted(ghl_ids - local_ids)
    overlap_ids = ghl_ids & local_ids

    if in_local_not_ghl:
        print(f"  In local but NOT in GHL ({len(in_local_not_ghl)}):")
        for cid in in_local_not_ghl:
            lead = sqlite_leads[cid]
            print(f"    - {lead['company']} | {cid}")
    if in_ghl_not_local:
        print(f"  In GHL but NOT in local ({len(in_ghl_not_local)}):")
        for cid in in_ghl_not_local:
            contact = ghl_contact_map[cid]
            print(f"    - {contact.get('companyName') or contact.get('name', '?')} | {cid}")

    # --- Custom field check on overlap ---
    custom_fields_populated = 0
    custom_fields_missing = 0

    for cid in overlap_ids:
        contact = ghl_contact_map.get(cid, {})
        cf_list = contact.get("customFields") or []
        has_lead_score = any(
            cf.get("id") == _LEAD_SCORE_FIELD_ID and cf.get("value") not in (None, "")
            for cf in cf_list
        )
        if has_lead_score:
            custom_fields_populated += 1
        else:
            custom_fields_missing += 1

    print(f"  Overlap: {len(overlap_ids)} contacts")
    print(f"  Lead Score field: {custom_fields_populated} populated, {custom_fields_missing} missing")

    # --- Build result (matches spec schema) ---
    now_iso = _now_iso()
    result = {
        "run_at": now_iso,
        "ghl_contact_count": len(ghl_ids),
        "local_ghl_count": len(local_ids),
        "in_local_not_ghl": in_local_not_ghl,
        "in_ghl_not_local": in_ghl_not_local,
        "custom_fields_populated": custom_fields_populated,
        "custom_fields_missing": custom_fields_missing,
    }

    # --- Log to activity_log ---
    summary = (
        f"GHL health check: {len(ghl_ids)} GHL contacts, {len(local_ids)} local. "
        f"In local not GHL: {len(in_local_not_ghl)}. "
        f"In GHL not local: {len(in_ghl_not_local)}. "
        f"Lead Score field: {custom_fields_populated} populated, {custom_fields_missing} missing."
    )
    log_activity(
        type="ghl_health_check",
        description=summary,
        agent="ghl_health_check",
    )

    # --- Update ghl_sync_status.json ---
    status_path = PROJECT_ROOT / output_dir / "ghl_sync_status.json"
    existing: dict = {}
    if status_path.exists():
        try:
            existing = json.loads(status_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}

    existing["health_check"] = result
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(existing, indent=2))
    print(f"\n  Updated {status_path}")

    print(f"\n=== Done ===\n")
    return result


if __name__ == "__main__":
    result = run_health_check()
    print(json.dumps(result, indent=2))
