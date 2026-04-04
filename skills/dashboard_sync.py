"""
dashboard_sync.py -- Data export layer for the Exotiq Lead Intelligence Pipeline.

Writes JSON files consumed by the React dashboard from the SQLite pipeline database.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

# Allow running as a standalone script
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.db_utils import get_db, log_activity, get_all_leads

PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _compute_annual_value(fleet_size) -> int:
    """Calculate annual SaaS contract value based on Exotiq pricing tiers."""
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


def _get_tier_name(fleet_size) -> str:
    """Return the pricing tier name for a given fleet size."""
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


def _parse_json_field(value: Any, fallback: Any = None) -> Any:
    """
    Safely parse a JSON string field from SQLite.

    Returns the parsed value, or fallback (default []) if the value is None,
    empty, or not valid JSON.
    """
    if fallback is None:
        fallback = []
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return fallback


def _safe_divide(numerator: float, denominator: float) -> float:
    """Divide numerator by denominator, returning 0.0 on divide-by-zero."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)


# ---------------------------------------------------------------------------
# Nested lead construction
# ---------------------------------------------------------------------------

def _compute_stale(updated_at: Any) -> tuple:
    """
    Return (stale: bool, days_since_activity: int).

    A lead is stale if updated_at is older than 7 days.
    """
    if not updated_at:
        return True, 9999
    try:
        # Handle both naive and aware timestamps
        ts_str = str(updated_at).rstrip("Z")
        if "+" in ts_str:
            ts_str = ts_str.split("+")[0]
        updated = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - updated
        days = delta.days
        return days >= 7, days
    except (ValueError, TypeError):
        return True, 9999


def _build_lead_object(row: dict) -> dict:
    """
    Reconstruct the canonical nested lead JSON structure from a flat SQLite row.
    """
    stale, days_since = _compute_stale(row.get("updated_at"))
    return {
        "id": row.get("id"),
        "company": row.get("company"),
        "contact": {
            "first_name": row.get("contact_first_name"),
            "last_name": row.get("contact_last_name"),
            "title": row.get("contact_title"),
            "email": row.get("contact_email"),
            "phone": row.get("contact_phone"),
            "linkedin": row.get("contact_linkedin"),
            "ig_personal": row.get("contact_ig_personal"),
        },
        "company_data": {
            "ig_handle": row.get("company_ig_handle"),
            "ig_followers": row.get("company_ig_followers"),
            "website": row.get("company_website"),
            "address": row.get("company_address"),
            "google_rating": row.get("company_google_rating"),
            "google_reviews": row.get("company_google_reviews"),
        },
        "fleet": {
            "size": row.get("fleet_size"),
            "size_confidence": row.get("fleet_size_confidence"),
            "vehicle_types": _parse_json_field(row.get("fleet_vehicle_types")),
            "vehicle_types_source": row.get("fleet_vehicle_types_source"),
        },
        "scoring": {
            "score": row.get("scoring_score"),
            "confidence": row.get("scoring_confidence"),
            "rationale": row.get("scoring_rationale"),
            "scored_at": row.get("scoring_scored_at"),
            "previous_score": row.get("scoring_previous_score"),
        },
        "outreach": {
            "status": row.get("outreach_status"),
            "dm_draft": row.get("outreach_dm_draft"),
            "template_used": row.get("outreach_template_used"),
            "client_review": row.get("outreach_client_review"),
            "approval_status": row.get("outreach_approval_status"),
            "do_not_say": _parse_json_field(row.get("outreach_do_not_say")),
            "dm1_sent": row.get("outreach_dm1_sent"),
            "dm2_sent": row.get("outreach_dm2_sent"),
            "dm3_sent": row.get("outreach_dm3_sent"),
            "response_received": row.get("outreach_response_received"),
            "response_category": row.get("outreach_response_category"),
            "response_date": row.get("outreach_response_date"),
            "calendly_sent": row.get("outreach_calendly_sent"),
            "demo_scheduled": row.get("outreach_demo_scheduled"),
        },
        "pricing": {
            "annual_value": _compute_annual_value(row.get("fleet_size")),
            "tier": _get_tier_name(row.get("fleet_size")),
        },
        "ghl": {
            "contact_id": row.get("ghl_contact_id"),
            "opportunity_id": row.get("ghl_opportunity_id"),
            "pipeline_stage": row.get("ghl_pipeline_stage"),
            "last_sync": row.get("ghl_last_sync"),
            "in_ghl": bool(row.get("ghl_in_ghl", False)),
            "tags": _parse_json_field(row.get("ghl_tags")),
        },
        "market": row.get("market"),
        "lead_source": row.get("lead_source"),
        "enrichment_history": _parse_json_field(row.get("enrichment_history")),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "stale": stale,
        "days_since_activity": days_since,
    }


# ---------------------------------------------------------------------------
# Per-file generators
# ---------------------------------------------------------------------------

def _write_leads(output_dir: Path, leads: list[dict]) -> int:
    """Write leads.json and return the number of leads written."""
    nested = [_build_lead_object(row) for row in leads]
    (output_dir / "leads.json").write_text(
        json.dumps(nested, indent=2), encoding="utf-8"
    )
    return len(nested)


def _write_activity(output_dir: Path, conn: sqlite3.Connection) -> int:
    """Write activity.json (last 500 entries, newest first). Returns row count."""
    rows = conn.execute(
        """
        SELECT id, timestamp, type, lead_id, description, source, agent
        FROM activity_log
        ORDER BY timestamp DESC, id DESC
        LIMIT 500
        """
    ).fetchall()

    entries = [dict(row) for row in rows]
    (output_dir / "activity.json").write_text(
        json.dumps(entries, indent=2), encoding="utf-8"
    )
    return len(entries)


def _write_stats(output_dir: Path, leads: list[dict]) -> dict:
    """Write stats.json and return the stats dict."""
    by_score: dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "unscored": 0}
    by_market: dict[str, int] = {}
    by_status: dict[str, int] = {}
    ghl_synced = 0
    pending_approval = 0
    approved = 0

    for lead in leads:
        # by_score
        score = lead.get("scoring_score")
        if score is None:
            by_score["unscored"] += 1
        else:
            key = str(int(score))
            if key in by_score:
                by_score[key] += 1
            else:
                by_score["unscored"] += 1

        # by_market
        market = lead.get("market") or "Unknown"
        by_market[market] = by_market.get(market, 0) + 1

        # by_status
        status = lead.get("outreach_status") or "Unknown"
        by_status[status] = by_status.get(status, 0) + 1

        # GHL synced
        if lead.get("ghl_in_ghl"):
            ghl_synced += 1

        # approval counts
        approval = lead.get("outreach_approval_status")
        if approval == "PENDING":
            pending_approval += 1
        elif approval == "APPROVED":
            approved += 1

    stats = {
        "total_leads": len(leads),
        "by_score": by_score,
        "by_market": by_market,
        "by_status": by_status,
        "ghl_synced": ghl_synced,
        "pending_approval": pending_approval,
        "approved": approved,
        "generated_at": _now_iso(),
    }
    (output_dir / "stats.json").write_text(
        json.dumps(stats, indent=2), encoding="utf-8"
    )
    return stats


def _write_ghl_sync_status(output_dir: Path, conn: sqlite3.Connection, leads: list[dict]) -> None:
    """Write ghl_sync_status.json."""
    total_in_ghl = sum(1 for lead in leads if lead.get("ghl_in_ghl"))
    total_not_in_ghl = len(leads) - total_in_ghl

    recent_rows = conn.execute(
        """
        SELECT *
        FROM ghl_sync_log
        ORDER BY timestamp DESC, id DESC
        LIMIT 20
        """
    ).fetchall()
    recent_syncs = [dict(row) for row in recent_rows]

    last_sync_at = recent_syncs[0]["timestamp"] if recent_syncs else None

    error_rows = conn.execute(
        """
        SELECT *
        FROM ghl_sync_log
        WHERE http_status >= 400 OR error_message IS NOT NULL
        ORDER BY timestamp DESC, id DESC
        """
    ).fetchall()
    sync_errors = [dict(row) for row in error_rows]

    payload = {
        "total_in_ghl": total_in_ghl,
        "total_not_in_ghl": total_not_in_ghl,
        "recent_syncs": recent_syncs,
        "last_sync_at": last_sync_at,
        "sync_errors": sync_errors,
        "generated_at": _now_iso(),
    }
    (output_dir / "ghl_sync_status.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _write_pipeline_metrics(output_dir: Path, leads: list[dict], conn: sqlite3.Connection) -> None:
    """Write pipeline_metrics.json."""
    total_leads = len(leads)
    scored = sum(1 for lead in leads if lead.get("scoring_score") is not None)
    approved_for_outreach = sum(
        1 for lead in leads if lead.get("outreach_approval_status") == "APPROVED"
    )
    dm1_sent = sum(1 for lead in leads if lead.get("outreach_dm1_sent") is not None)
    responded = sum(1 for lead in leads if lead.get("outreach_response_received"))
    demo_scheduled = sum(1 for lead in leads if lead.get("outreach_demo_scheduled"))

    # demo_completed: leads with demo_scheduled=True and a response (proxy -- no dedicated column)
    demo_completed = 0

    # per-market breakdown
    by_market: dict[str, dict] = {}
    for lead in leads:
        market = lead.get("market") or "Unknown"
        entry = by_market.setdefault(market, {"leads": 0, "dm_sent": 0, "responded": 0})
        entry["leads"] += 1
        if lead.get("outreach_dm1_sent") is not None:
            entry["dm_sent"] += 1
        if lead.get("outreach_response_received"):
            entry["responded"] += 1

    # velocity: leads added / DMs sent in last 7 days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    leads_last_7 = sum(
        1 for lead in leads
        if lead.get("created_at") and lead["created_at"] >= cutoff
    )
    dms_last_7 = sum(
        1 for lead in leads
        if lead.get("outreach_dm1_sent") and lead["outreach_dm1_sent"] >= cutoff
    )

    payload = {
        "funnel": {
            "total_leads": total_leads,
            "scored": scored,
            "approved_for_outreach": approved_for_outreach,
            "dm1_sent": dm1_sent,
            "responded": responded,
            "demo_scheduled": demo_scheduled,
            "demo_completed": demo_completed,
        },
        "conversion_rates": {
            "lead_to_dm": _safe_divide(dm1_sent, total_leads),
            "dm_to_response": _safe_divide(responded, dm1_sent),
            "response_to_demo": _safe_divide(demo_scheduled, responded),
        },
        "by_market": by_market,
        "velocity": {
            "leads_added_last_7_days": leads_last_7,
            "dms_sent_last_7_days": dms_last_7,
        },
        "generated_at": _now_iso(),
    }
    (output_dir / "pipeline_metrics.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def sync_dashboard(output_dir: str = "public/data") -> dict:
    """
    Export all pipeline data to JSON files for the dashboard.

    Args:
        output_dir: Directory path relative to project root where JSON files are written.
                    Created if it does not exist.

    Returns:
        dict with keys: files_written (list of filenames), lead_count, activity_count
    """
    out = PROJECT_ROOT / output_dir
    out.mkdir(parents=True, exist_ok=True)

    leads = get_all_leads()

    conn = get_db()
    try:
        lead_count = _write_leads(out, leads)
        activity_count = _write_activity(out, conn)
        _write_stats(out, leads)
        _write_ghl_sync_status(out, conn, leads)
        _write_pipeline_metrics(out, leads, conn)
    finally:
        conn.close()

    files_written = [
        "leads.json",
        "activity.json",
        "stats.json",
        "ghl_sync_status.json",
        "pipeline_metrics.json",
    ]

    log_activity(
        type="dashboard_sync",
        description=f"Exported {lead_count} leads and {activity_count} activity entries to {output_dir}",
        agent="dashboard_sync",
    )

    return {
        "files_written": files_written,
        "lead_count": lead_count,
        "activity_count": activity_count,
    }


if __name__ == "__main__":
    result = sync_dashboard()
    print(json.dumps(result, indent=2))
