"""
Sequence Engine -- orchestrates multi-touch outreach campaigns.

Core responsibilities:
- Enroll leads into sequences
- Detect when a lead's next touch is due
- Generate personalized drafts using content templates + lead context
- Queue drafts for approval (phase 1 = approve-every-touch)
- Stop sequences when leads respond

Phase 1: drafts go into outreach_queue with status='pending'. No auto-send.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "exotiq.db"

sys.path.insert(0, str(PROJECT_ROOT))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

def enroll_lead(lead_id: str, sequence_id: str) -> dict:
    """
    Add a lead to a sequence. If already enrolled in this sequence, no-op.
    Returns enrollment record.
    """
    conn = _get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM lead_sequences WHERE lead_id = ? AND sequence_id = ? AND status IN ('active','paused')",
            (lead_id, sequence_id),
        ).fetchone()

        if existing:
            return dict(existing)

        # Verify lead exists
        lead = conn.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if not lead:
            raise ValueError(f"Lead not found: {lead_id}")

        # Verify sequence exists and is active
        seq = conn.execute(
            "SELECT id, active FROM sequences WHERE id = ?", (sequence_id,)
        ).fetchone()
        if not seq:
            raise ValueError(f"Sequence not found: {sequence_id}")

        now = _now_iso()
        # Find first step delay
        first_step = conn.execute(
            "SELECT delay_days FROM sequence_steps WHERE sequence_id = ? ORDER BY step_order LIMIT 1",
            (sequence_id,),
        ).fetchone()
        delay_days = first_step["delay_days"] if first_step else 0
        next_due = (datetime.now(timezone.utc) + timedelta(days=delay_days)).isoformat()

        cur = conn.execute(
            """INSERT INTO lead_sequences (lead_id, sequence_id, started_at, current_step, status, next_touch_due, updated_at)
               VALUES (?, ?, ?, 0, 'active', ?, ?)""",
            (lead_id, sequence_id, now, next_due, now),
        )
        conn.commit()

        _log_activity(
            conn,
            "sequence_enroll",
            lead_id,
            f"Enrolled in sequence {sequence_id}",
            "sequence_engine",
            "saul",
        )
        conn.commit()

        return {
            "id": cur.lastrowid,
            "lead_id": lead_id,
            "sequence_id": sequence_id,
            "started_at": now,
            "current_step": 0,
            "status": "active",
            "next_touch_due": next_due,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Due touch processing
# ---------------------------------------------------------------------------

def process_due_touches() -> list[dict]:
    """
    Find all active enrollments with next_touch_due <= now.
    For each: draft the touch, add to outreach_queue, advance state.
    """
    conn = _get_db()
    drafted: list[dict] = []
    try:
        now = _now_iso()
        due = conn.execute(
            """SELECT * FROM lead_sequences
               WHERE status = 'active' AND next_touch_due IS NOT NULL AND next_touch_due <= ?""",
            (now,),
        ).fetchall()

        for enrollment in due:
            result = _draft_next_touch(conn, dict(enrollment))
            if result:
                drafted.append(result)

        conn.commit()
    finally:
        conn.close()

    return drafted


def _draft_next_touch(conn: sqlite3.Connection, enrollment: dict) -> Optional[dict]:
    """Generate the next touch for an enrollment."""
    lead_id = enrollment["lead_id"]
    seq_id = enrollment["sequence_id"]
    current = enrollment["current_step"]
    next_step_order = current + 1

    step = conn.execute(
        "SELECT * FROM sequence_steps WHERE sequence_id = ? AND step_order = ?",
        (seq_id, next_step_order),
    ).fetchone()

    if not step:
        # Sequence complete
        conn.execute(
            "UPDATE lead_sequences SET status = 'completed', next_touch_due = NULL, updated_at = ? WHERE id = ?",
            (_now_iso(), enrollment["id"]),
        )
        _log_activity(
            conn, "sequence_complete", lead_id,
            f"Sequence {seq_id} completed",
            "sequence_engine", "saul",
        )
        return None

    # Check skip_if_responded
    if step["skip_if_responded"]:
        lead = conn.execute(
            "SELECT outreach_response_received FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        if lead and lead["outreach_response_received"]:
            conn.execute(
                """UPDATE lead_sequences SET status = 'stopped_responded',
                   stopped_reason = 'Lead responded', next_touch_due = NULL, updated_at = ?
                   WHERE id = ?""",
                (_now_iso(), enrollment["id"]),
            )
            _log_activity(
                conn, "sequence_stop", lead_id,
                f"Sequence {seq_id} stopped: lead responded",
                "sequence_engine", "saul",
            )
            return None

    # Get lead for personalization
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        return None

    # Render content
    content, subject = _render_touch(conn, dict(step), dict(lead))

    # Queue it
    scheduled = _compute_send_time(step["channel"])
    cur = conn.execute(
        """INSERT INTO outreach_queue
           (lead_id, sequence_id, step_id, channel, subject, content, status, scheduled_for, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (lead_id, seq_id, step["id"], step["channel"], subject, content, scheduled, _now_iso()),
    )

    # Advance state
    # Next step delay from the step AFTER this one
    next_next_step = conn.execute(
        "SELECT delay_days FROM sequence_steps WHERE sequence_id = ? AND step_order = ?",
        (seq_id, next_step_order + 1),
    ).fetchone()
    if next_next_step:
        # delay_days on a step is relative to sequence start
        seq_start = datetime.fromisoformat(enrollment["started_at"])
        next_due = (seq_start + timedelta(days=next_next_step["delay_days"])).isoformat()
    else:
        next_due = None

    conn.execute(
        """UPDATE lead_sequences SET current_step = ?, next_touch_due = ?, updated_at = ? WHERE id = ?""",
        (next_step_order, next_due, _now_iso(), enrollment["id"]),
    )

    _log_activity(
        conn, "dm_draft", lead_id,
        f"Drafted {step['channel']} step {next_step_order} for sequence {seq_id}",
        "sequence_engine", "saul",
    )

    return {
        "queue_id": cur.lastrowid,
        "lead_id": lead_id,
        "sequence_id": seq_id,
        "step_order": next_step_order,
        "channel": step["channel"],
        "scheduled_for": scheduled,
    }


# ---------------------------------------------------------------------------
# Content rendering
# ---------------------------------------------------------------------------

def _render_touch(conn: sqlite3.Connection, step: dict, lead: dict) -> tuple[str, Optional[str]]:
    """Return (body, subject) for a step."""
    # Resolve template
    template_body = step.get("template_override")
    template_subject = None

    if not template_body and step.get("template_id"):
        tpl = conn.execute(
            "SELECT * FROM content_templates WHERE id = ?", (step["template_id"],)
        ).fetchone()
        if tpl:
            template_body = tpl["body_template"]
            template_subject = tpl["subject_template"]

    if not template_body:
        template_body = "Hey {first_name}, Gregory here from Exotiq. Worth a quick chat?"

    # Build variable context
    ctx = _build_lead_context(lead)

    body = _fill_template(template_body, ctx)
    subject = _fill_template(template_subject, ctx) if template_subject else None
    return body, subject


def _build_lead_context(lead: dict) -> dict:
    """Extract usable vars from a lead row."""
    return {
        "first_name": lead.get("contact_first_name") or "there",
        "last_name": lead.get("contact_last_name") or "",
        "company": lead.get("company") or "",
        "market": lead.get("market") or "",
        "fleet_size": lead.get("fleet_size") or "",
        "ig_handle": lead.get("company_ig_handle") or "",
        "score": lead.get("scoring_score") or "",
    }


def _fill_template(template: str, ctx: dict) -> str:
    if not template:
        return ""
    out = template
    for key, val in ctx.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def _compute_send_time(channel: str) -> str:
    """Compute an appropriate send time for the channel."""
    now = datetime.now(timezone.utc)
    # Phase 1: simple default (immediate for DMs, next business window for email)
    # Real business-hour windowing comes in phase 3 with actual send logic.
    return now.isoformat()


# ---------------------------------------------------------------------------
# Activity logging helper
# ---------------------------------------------------------------------------

def _log_activity(conn, type_: str, lead_id: Optional[str], desc: str, source: str, agent: str):
    conn.execute(
        """INSERT INTO activity_log (timestamp, type, lead_id, description, source, agent)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (_now_iso(), type_, lead_id, desc, source, agent),
    )


# ---------------------------------------------------------------------------
# Queue actions
# ---------------------------------------------------------------------------

def approve_queue_item(queue_id: int, approved_by: str = "gregory", edited_content: Optional[str] = None) -> dict:
    conn = _get_db()
    try:
        item = conn.execute("SELECT * FROM outreach_queue WHERE id = ?", (queue_id,)).fetchone()
        if not item:
            raise ValueError(f"Queue item {queue_id} not found")

        content = edited_content if edited_content else item["content"]
        conn.execute(
            """UPDATE outreach_queue SET status = 'approved', content = ?, approved_by = ?, approved_at = ?
               WHERE id = ?""",
            (content, approved_by, _now_iso(), queue_id),
        )
        _log_activity(
            conn, "outreach_approved", item["lead_id"],
            f"Approved {item['channel']} touch",
            "outreach_queue", approved_by,
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM outreach_queue WHERE id = ?", (queue_id,)).fetchone())
    finally:
        conn.close()


def hold_queue_item(queue_id: int, reason: Optional[str] = None) -> dict:
    return _set_queue_status(queue_id, "held", reason)


def reject_queue_item(queue_id: int, reason: Optional[str] = None) -> dict:
    return _set_queue_status(queue_id, "rejected", reason)


def skip_queue_item(queue_id: int, reason: Optional[str] = None) -> dict:
    return _set_queue_status(queue_id, "skipped", reason)


def _set_queue_status(queue_id: int, status: str, reason: Optional[str]) -> dict:
    conn = _get_db()
    try:
        item = conn.execute("SELECT * FROM outreach_queue WHERE id = ?", (queue_id,)).fetchone()
        if not item:
            raise ValueError(f"Queue item {queue_id} not found")

        conn.execute(
            "UPDATE outreach_queue SET status = ? WHERE id = ?",
            (status, queue_id),
        )
        _log_activity(
            conn, f"outreach_{status}", item["lead_id"],
            f"{status.title()}: {reason or '(no reason)'}",
            "outreach_queue", "gregory",
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM outreach_queue WHERE id = ?", (queue_id,)).fetchone())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def list_sequences(active_only: bool = True) -> list[dict]:
    conn = _get_db()
    try:
        if active_only:
            rows = conn.execute("SELECT * FROM sequences WHERE active = 1 ORDER BY name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM sequences ORDER BY name").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            steps = conn.execute(
                "SELECT * FROM sequence_steps WHERE sequence_id = ? ORDER BY step_order",
                (d["id"],),
            ).fetchall()
            d["steps"] = [dict(s) for s in steps]
            d["active_enrollments"] = conn.execute(
                "SELECT COUNT(*) FROM lead_sequences WHERE sequence_id = ? AND status = 'active'",
                (d["id"],),
            ).fetchone()[0]
            result.append(d)
        return result
    finally:
        conn.close()


def list_queue(status: Optional[str] = None) -> list[dict]:
    conn = _get_db()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM outreach_queue WHERE status = ? ORDER BY scheduled_for",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM outreach_queue ORDER BY scheduled_for").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    # Simple CLI: python skills/sequence_engine.py process
    cmd = sys.argv[1] if len(sys.argv) > 1 else "process"
    if cmd == "process":
        drafted = process_due_touches()
        print(f"Drafted {len(drafted)} touches")
        for d in drafted:
            print(f"  lead={d['lead_id']} channel={d['channel']} queue_id={d['queue_id']}")
    elif cmd == "list":
        for s in list_sequences():
            print(f"{s['id']}: {s['name']} ({s['active_enrollments']} active, {len(s['steps'])} steps)")
    else:
        print(f"Unknown command: {cmd}")
