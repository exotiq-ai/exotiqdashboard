"""
GHL Sync Health Check -- compare local SQLite DB against live GHL contacts.

Verifies each contact by ID (GET /contacts/{id}) rather than tag search
since the GHL v2 API does not support filtering by tags in GET /contacts/.

Usage:
    python3 skills/ghl_health_check.py

Reports:
    - In SQLite (ghl_in_ghl=1) but contact ID not found in GHL
    - Missing key custom fields (Lead Score, OpenClaw Lead ID) on verified contacts
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from ghl.ghl_client import GHLClient
from skills.db_utils import get_db, log_activity

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "ghl" / "ghl_config.json"
STATUS_PATH = PROJECT_ROOT / "public" / "data" / "ghl_sync_status.json"


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_ghl_contact_by_id(client: GHLClient, contact_id: str) -> Optional[dict]:
    """Fetch a single GHL contact by ID. Returns dict or None if not found."""
    try:
        data = client.get(f"/contacts/{contact_id}")
        time.sleep(0.2)
        return data.get("contact") or data
    except Exception:
        time.sleep(0.2)
        return None


def _get_sqlite_ghl_leads(conn) -> dict:
    """Return {ghl_contact_id: lead_row_dict} for all leads with ghl_in_ghl=1."""
    rows = conn.execute(
        "SELECT id, ghl_contact_id, company FROM leads WHERE ghl_in_ghl = 1 AND ghl_contact_id IS NOT NULL"
    ).fetchall()
    return {row["ghl_contact_id"]: dict(row) for row in rows}


def run_health_check(output_dir: str = "public/data") -> dict:
    """
    Verify all leads marked ghl_in_ghl=1 exist in GHL and have key custom fields.

    Returns dict with health data and updates ghl_sync_status.json.
    """
    config = _load_config()
    client = GHLClient()
    cf = config["custom_fields"]
    key_field_ids = {cf["OpenClaw Lead ID"], cf["Lead Score"]}

    print("\n=== GHL Sync Health Check ===\n")

    conn = get_db()
    sqlite_leads = _get_sqlite_ghl_leads(conn)
    print(f"  {len(sqlite_leads)} leads marked ghl_in_ghl=1 in SQLite")
    print(f"  Verifying each contact via GHL API...\n")

    in_sqlite_not_ghl = []
    in_both = []
    missing_fields = []

    for contact_id, lead in sqlite_leads.items():
        contact = _get_ghl_contact_by_id(client, contact_id)
        if contact is None:
            in_sqlite_not_ghl.append(contact_id)
            print(f"  ✗ NOT FOUND: {lead['company']} | {contact_id}")
        else:
            in_both.append(contact_id)
            contact_cf_ids = {f.get("id") for f in (contact.get("customFields") or [])}
            missing = key_field_ids - contact_cf_ids
            if missing:
                missing_fields.append({
                    "contact_id": contact_id,
                    "company": lead.get("company"),
                    "missing_field_ids": list(missing),
                })
                print(f"  ⚠ MISSING FIELDS: {lead['company']} | {contact_id}")
            else:
                print(f"  ✓ OK: {lead['company']} | {contact_id}")

    is_healthy = len(in_sqlite_not_ghl) == 0 and len(missing_fields) == 0

    print(f"\nIn SQLite but NOT in GHL: {len(in_sqlite_not_ghl)}")
    print(f"In both (verified):        {len(in_both)}")
    print(f"Missing key custom fields: {len(missing_fields)}")

    health = {
        "checked_at": _now_iso(),
        "ghl_contacts_verified": len(in_both),
        "sqlite_ghl_leads": len(sqlite_leads),
        "in_sqlite_not_ghl": in_sqlite_not_ghl,
        "missing_custom_fields": missing_fields,
        "healthy": is_healthy,
    }

    # Log to activity_log
    summary = (
        f"Health check: {len(in_both)} verified / {len(sqlite_leads)} SQLite "
        f"missing_in_ghl={len(in_sqlite_not_ghl)} missing_fields={len(missing_fields)} "
        f"healthy={is_healthy}"
    )
    log_activity(type="ghl_sync", description=summary, agent="ghl_health_check")

    # Update ghl_sync_status.json
    try:
        status_path = PROJECT_ROOT / output_dir / "ghl_sync_status.json"
        existing = {}
        if status_path.exists():
            existing = json.loads(status_path.read_text())
        existing["health_check"] = health
        existing["generated_at"] = _now_iso()
        status_path.write_text(json.dumps(existing, indent=2))
        print(f"\nUpdated {status_path}")
    except Exception as e:
        print(f"\nWarning: could not update ghl_sync_status.json: {e}")

    conn.close()
    print(f"\n=== Health: {'OK' if is_healthy else 'ISSUES FOUND'} ===\n")
    return health


if __name__ == "__main__":
    result = run_health_check()
    sys.exit(0 if result["healthy"] else 1)
