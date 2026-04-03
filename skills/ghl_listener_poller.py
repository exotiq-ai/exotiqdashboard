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
