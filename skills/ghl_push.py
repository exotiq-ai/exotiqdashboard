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
    Calculate annual SaaS contract value based on Exotiq pricing tiers.

    Starter (1-10 vehicles):  $29/vehicle/month, min $79/month
    Professional (11-25):     $399/month
    Business (26-75):         $899/month
    Enterprise (76+):         $1,799/month

    Returns annual value (monthly * 12). Returns Starter minimum for unknown fleet size.
    """
    try:
        size = int(fleet_size)
    except (TypeError, ValueError):
        return 79 * 12  # Starter minimum

    if size <= 0:
        return 79 * 12  # Starter minimum
    if size <= 10:
        return max(size * 29, 79) * 12
    if size <= 25:
        return 399 * 12
    if size <= 75:
        return 899 * 12
    return 1799 * 12  # Enterprise


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
