"""
Bulk GHL Push v2 -- push all APPROVED, un-pushed leads to GoHighLevel.

Fixes vs skills/ghl_push.py:
- Config keys match ghl_config.json ("Lead Score" not "lead_score")
- Custom field key is "value" not "field_value"
- Pipeline accessed via config["pipeline"]["id"] and config["pipeline"]["stages"]
- Relaxed: leads without first_name get company name split as fallback
- Leads without email/phone skip dedup and are created directly
- Score 2 leads are skipped (only score >= 3 pushed)
- Sleep 200ms between API calls

Usage:
    python3 ghl/bulk_push_v2.py
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ghl.ghl_client import GHLAuthError, GHLClient, GHLRateLimitError, GHLValidationError
from skills.db_utils import get_db, log_activity

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "ghl" / "ghl_config.json"


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_annual_value(fleet_size) -> int:
    try:
        size = int(fleet_size)
    except (TypeError, ValueError):
        return 79 * 12
    if size <= 0:
        return 79 * 12
    if size <= 10:
        return max(size * 29, 79) * 12
    if size <= 25:
        return 399 * 12
    if size <= 75:
        return 899 * 12
    return 1799 * 12


def _get_tier(fleet_size) -> str:
    try:
        size = int(fleet_size)
    except (TypeError, ValueError):
        return "Starter (est.)"
    if size <= 0:
        return "Starter (est.)"
    if size <= 10:
        return "Starter"
    if size <= 25:
        return "Professional"
    if size <= 75:
        return "Business"
    return "Enterprise"


def _build_tags(lead: dict) -> list:
    tags = ["exotiq-pipeline"]
    score = lead.get("scoring_score")
    if score is not None:
        tags.append(f"score-{int(score)}")
        if int(score) == 5:
            tags.append("gregory-only")
    market = (lead.get("market") or "").strip()
    if market:
        tags.append(market.lower().replace(" ", "-"))
    # fleet tier tag
    tier = _get_tier(lead.get("fleet_size"))
    tags.append(tier.lower().replace(" ", "-").replace("(est.)", "est"))
    return tags


def _build_contact_payload(lead: dict, config: dict) -> dict:
    cf = config["custom_fields"]
    location_id = config["location_id"]
    tags = _build_tags(lead)

    # Name fallback: use company name if no contact name
    first = lead.get("contact_first_name") or ""
    last = lead.get("contact_last_name") or ""
    if not first and not last:
        parts = (lead.get("company") or "").split()
        first = parts[0] if parts else "Unknown"
        last = " ".join(parts[1:]) if len(parts) > 1 else ""

    # Address parsing
    address_raw = lead.get("company_address") or ""
    parts = [p.strip() for p in address_raw.split(",")]
    address1 = parts[0] if parts else ""
    city = parts[1] if len(parts) > 1 else ""

    # Vehicle types
    vt_raw = lead.get("fleet_vehicle_types") or "[]"
    try:
        vt_list = json.loads(vt_raw)
        vehicle_str = ", ".join(vt_list) if isinstance(vt_list, list) else str(vt_raw)
    except (json.JSONDecodeError, TypeError):
        vehicle_str = str(vt_raw)

    # Do not say
    dns_raw = lead.get("outreach_do_not_say") or "[]"
    try:
        dns_list = json.loads(dns_raw)
        dns_str = ", ".join(dns_list) if isinstance(dns_list, list) else ""
    except (json.JSONDecodeError, TypeError):
        dns_str = str(dns_raw)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    custom_fields = [
        {"id": cf["Lead Score"],            "value": str(lead.get("scoring_score") or "")},
        {"id": cf["Score Confidence"],      "value": str(lead.get("scoring_confidence") or "")},
        {"id": cf["Fleet Size"],            "value": str(lead.get("fleet_size") or "")},
        {"id": cf["Fleet Size Confidence"], "value": str(lead.get("fleet_size_confidence") or "")},
        {"id": cf["IG Handle"],             "value": str(lead.get("company_ig_handle") or "")},
        {"id": cf["IG Followers"],          "value": str(lead.get("company_ig_followers") or "")},
        {"id": cf["Google Rating"],         "value": str(lead.get("company_google_rating") or "")},
        {"id": cf["Google Reviews"],        "value": str(lead.get("company_google_reviews") or "")},
        {"id": cf["Vehicle Types"],         "value": vehicle_str},
        {"id": cf["DM Template Used"],      "value": str(lead.get("outreach_template_used") or "")},
        {"id": cf["DM Draft"],              "value": str(lead.get("outreach_dm_draft") or "")},
        {"id": cf["DO NOT SAY"],            "value": dns_str},
        {"id": cf["Enrichment Sources"],    "value": str(lead.get("lead_source") or "")},
        {"id": cf["OpenClaw Lead ID"],      "value": str(lead.get("id") or "")},
        {"id": cf["Pipeline Entry Date"],   "value": today},
    ]

    payload = {
        "firstName": first,
        "lastName": last,
        "companyName": lead.get("company") or "",
        "address1": address1,
        "city": city,
        "website": lead.get("company_website") or "",
        "locationId": location_id,
        "source": "OpenClaw Pipeline",
        "tags": tags,
        "customFields": custom_fields,
    }

    if lead.get("contact_email"):
        payload["email"] = lead["contact_email"]
    if lead.get("contact_phone"):
        payload["phone"] = lead["contact_phone"]

    return payload


def _dedup_check(client: GHLClient, location_id: str, email: str, phone: str):
    """Return existing GHL contact ID or None."""
    params = {"locationId": location_id}
    if email:
        params["email"] = email
    elif phone:
        params["number"] = phone
    else:
        return None
    try:
        data = client.get("/contacts/search/duplicate", params=params)
        contacts = data.get("contacts") or []
        return contacts[0]["id"] if contacts else None
    except Exception:
        return None


def _create_opportunity(client: GHLClient, contact_id: str, lead: dict, config: dict) -> str:
    pipeline = config["pipeline"]
    pipeline_id = pipeline["id"]
    stages = pipeline["stages"]

    score = int(lead.get("scoring_score") or 3)
    stage_name = "Gregory -- Personal Outreach" if score >= 5 else "DM Drafted"
    stage_id = stages.get(stage_name, "")
    market = lead.get("market") or ""

    payload = {
        "pipelineId": pipeline_id,
        "pipelineStageId": stage_id,
        "name": f"{lead.get('company', 'Unknown')} - {market}",
        "contactId": contact_id,
        "monetaryValue": _compute_annual_value(lead.get("fleet_size")),
        "locationId": config["location_id"],
        "status": "open",
    }
    resp = client.post("/opportunities/", payload)
    opp = resp.get("opportunity") or resp
    return opp.get("id", "")


def _log_sync(conn: sqlite3.Connection, lead_id, ghl_contact_id, endpoint, http_status,
              payload_summary=None, error_message=None):
    conn.execute(
        """INSERT INTO ghl_sync_log
           (timestamp, direction, lead_id, ghl_contact_id, endpoint, http_status, payload_summary, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (_now_iso(), "outbound", lead_id, ghl_contact_id, endpoint,
         http_status, payload_summary, error_message),
    )
    conn.commit()


def bulk_push() -> dict:
    config = _load_config()
    client = GHLClient()
    location_id = config["location_id"]

    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM leads
           WHERE outreach_approval_status = 'APPROVED'
             AND (ghl_in_ghl = 0 OR ghl_in_ghl IS NULL)
             AND scoring_score >= 3
           ORDER BY scoring_score DESC, created_at ASC"""
    ).fetchall()
    conn.close()

    pushed = 0
    skipped = 0
    errors = []

    print(f"\n=== Exotiq Bulk GHL Push v2 ===")
    print(f"Found {len(rows)} approved leads (score >= 3) to push\n")

    for row in rows:
        lead = dict(row)
        lead_id = lead["id"]
        company = lead.get("company", "?")
        score = lead.get("scoring_score")

        print(f"[{lead_id}] {company} (score={score})")

        try:
            # Dedup check
            existing_id = _dedup_check(
                client, location_id,
                lead.get("contact_email", ""),
                lead.get("contact_phone", ""),
            )
            time.sleep(0.2)

            payload = _build_contact_payload(lead, config)

            conn = get_db()
            if existing_id:
                resp = client.put(f"/contacts/{existing_id}", payload)
                contact_id = existing_id
                action = "updated"
                _log_sync(conn, lead_id, contact_id, f"PUT /contacts/{existing_id}", 200,
                          f"Updated contact for {company}")
                print(f"  ↳ Updated existing contact {contact_id}")
            else:
                resp = client.post("/contacts/", payload)
                contact = resp.get("contact") or resp
                contact_id = contact.get("id", "")
                action = "created"
                _log_sync(conn, lead_id, contact_id, "POST /contacts/", 201,
                          f"Created contact for {company}")
                print(f"  ↳ Created contact {contact_id}")
            conn.close()

            time.sleep(0.2)

            # Create opportunity
            opp_id = _create_opportunity(client, contact_id, lead, config)
            stage_name = "Gregory -- Personal Outreach" if int(score) >= 5 else "DM Drafted"
            tags = _build_tags(lead)
            annual_value = _compute_annual_value(lead.get("fleet_size"))
            tier = _get_tier(lead.get("fleet_size"))

            conn = get_db()
            _log_sync(conn, lead_id, contact_id, "POST /opportunities/", 201,
                      f"Created opportunity {opp_id} stage={stage_name}")

            # Update lead record
            conn.execute(
                """UPDATE leads SET
                   ghl_contact_id = ?, ghl_opportunity_id = ?, ghl_in_ghl = 1,
                   ghl_tags = ?, ghl_last_sync = ?, ghl_pipeline_stage = ?
                   WHERE id = ?""",
                (contact_id, opp_id, json.dumps(tags), _now_iso(), stage_name, lead_id),
            )
            conn.commit()

            log_activity(
                type="ghl_push",
                description=(
                    f"Pushed {company} to GHL. contact={contact_id} opp={opp_id} "
                    f"stage={stage_name} tags={','.join(tags)} tier={tier} "
                    f"annual=${annual_value:,} action={action}"
                ),
                lead_id=lead_id,
                agent="bulk_push_v2",
            )
            conn.close()

            print(f"  ↳ Opportunity {opp_id} → {stage_name} | {tier} ${annual_value:,}/yr")
            pushed += 1

        except GHLAuthError as e:
            print(f"  ✗ AUTH ERROR - stopping batch: {e}")
            errors.append({"lead_id": lead_id, "error": str(e)})
            break
        except GHLRateLimitError:
            print(f"  ⚠ Rate limited -- sleeping 30s then retrying")
            time.sleep(30)
        except GHLValidationError as e:
            print(f"  ✗ Validation error (skipping): {e}")
            errors.append({"lead_id": lead_id, "error": str(e)})
            skipped += 1
        except Exception as e:
            print(f"  ✗ Error (skipping): {e}")
            errors.append({"lead_id": lead_id, "error": str(e)})
            skipped += 1

        time.sleep(0.2)

    print(f"\n=== Summary ===")
    print(f"  Pushed:  {pushed}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {len(errors)}")
    if errors:
        for e in errors:
            print(f"    {e['lead_id']}: {e['error']}")

    return {"pushed": pushed, "skipped": skipped, "errors": errors}


if __name__ == "__main__":
    result = bulk_push()
    sys.exit(0 if result["pushed"] > 0 or result["skipped"] == 0 else 1)
