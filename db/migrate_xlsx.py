#!/usr/bin/env python3
"""
Migrate Miami_Operators_Clean_2.xlsx into the Exotiq SQLite database.

Usage:
    python db/migrate_xlsx.py [path/to/Miami_Operators_Clean_2.xlsx]

If no path is given, looks for the file at the project root.

Output:
    Migration report to stdout -- counts per market, warnings, skipped rows.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import openpyxl

# Project root
ROOT = Path(__file__).parent.parent
DEFAULT_XLSX_PATH = ROOT / "Miami_Operators_Clean_2.xlsx"

# Add project root to path so we can import skills
sys.path.insert(0, str(ROOT))
from skills.db_utils import get_db, log_activity

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tabs to skip entirely
SKIP_TABS = {"Export Summary"}

# Tabs that are metadata (import separately, not as leads)
METADATA_TABS = {"Daily Activity Log", "Lead Source Tracker"}

# Market abbreviations for lead ID generation
MARKET_ABBREVS: dict[str, str] = {
    "Miami Operators": "mia",
    "Phoenix Scottsdale": "phx",
    "Dallas Fort Worth": "dfw",
    "Atlanta": "atl",
    "NYC": "nyc",
    "Las Vegas": "lv",
    "Los Angeles": "la",
    "SF Bay Area": "sf",
    "DC DMV": "dc",
}

# xlsx column name -> SQLite column name
# Column names are matched case-insensitively and stripped of whitespace
COLUMN_MAP: dict[str, str] = {
    "company": "company",
    "first name": "contact_first_name",
    "last name": "contact_last_name",
    "title": "contact_title",
    "email": "contact_email",
    "company email": "_company_email_raw",  # processed: may be phone
    "linkedin url (personal)": "contact_linkedin",
    "ig handle (personal)": "contact_ig_personal",
    "ig handle (company)": "company_ig_handle",
    "city + state": "market",
    "fleet size": "fleet_size",
    "lead score": "scoring_score",
    "enrichment notes": "_enrichment_notes_raw",  # processed
    "recent car post": "_recent_car_post_raw",    # processed -> fleet_vehicle_types
    "status": "outreach_status",
    "draft dm": "_draft_dm_raw",
    "approved dm": "_approved_dm_raw",
    "dm1 sent date": "outreach_dm1_sent",
    "dm2 sent date": "outreach_dm2_sent",
    "dm2 copy": "_dm2_copy_raw",
    "dm3 sent date": "outreach_dm3_sent",
    "dm3 copy": "_dm3_copy_raw",
    "response received": "outreach_response_received",
    "response category": "outreach_response_category",
    "response date": "outreach_response_date",
    "calendly sent": "outreach_calendly_sent",
    "demo scheduled": "outreach_demo_scheduled",
    "lead source": "lead_source",
    "notes": "notes",
    "client review (y/n)": "_client_review_raw",
    "client review": "_client_review_raw",
    "client notes": "_client_notes_raw",
    "outreach sent": "_outreach_sent_raw",      # derive from dm1_sent
    "market": "market",
    "outreach type": "_skip",                   # metadata only
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_col(name: Any) -> str:
    """Lowercase and strip a column header name."""
    if name is None:
        return ""
    return str(name).strip().lower()


def _is_phone(value: str) -> bool:
    """
    Return True if the value looks like a phone number rather than an email.
    Detects: +1XXXXXXXXXX, all-digit strings (with spaces/dashes), US formats.
    """
    cleaned = re.sub(r"[\s\-\(\)\.]+", "", value)
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return cleaned.isdigit() and len(cleaned) >= 7


def _parse_boolean(value: Any) -> Optional[bool]:
    """Convert Y/N/Yes/No/True/False/1/0 to bool or None."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("y", "yes", "true", "1"):
        return True
    if s in ("n", "no", "false", "0"):
        return False
    return None


def _clean_int(value: Any) -> Optional[int]:
    """Parse an integer value, returning None on failure."""
    if value is None:
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def _clean_str(value: Any) -> Optional[str]:
    """Strip and return a string, or None if empty."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _clean_date(value: Any) -> Optional[str]:
    """
    Convert a date/datetime value to ISO 8601 string or None.
    Handles datetime objects from openpyxl and string formats.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc).isoformat()
    s = str(value).strip()
    if not s:
        return None
    # Try common date formats
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    # Return as-is if we can't parse -- record warning
    return s


def _parse_vehicle_types(raw: Any) -> Optional[str]:
    """
    Parse a 'Recent Car Post' field into a JSON array string.
    The field may contain car names separated by commas, newlines, or slashes.
    Returns a JSON-encoded list, or None if empty.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Split on commas, newlines, slashes
    parts = re.split(r"[,\n/]+", s)
    vehicles = [p.strip() for p in parts if p.strip()]
    if not vehicles:
        return None
    return json.dumps(vehicles)


def _parse_enrichment_notes(raw: Any) -> tuple[Optional[str], list[dict]]:
    """
    Parse the Enrichment Notes field.

    Returns (notes_text, enrichment_history_entries).
    The field is free text, sometimes structured. We preserve it in notes
    and add a single enrichment_history entry if non-empty.
    """
    if raw is None:
        return None, []
    s = str(raw).strip()
    if not s:
        return None, []
    # Return as notes; we don't parse structured intel here -- too variable
    history_entry = {
        "action": "manual_notes",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields_updated": ["notes"],
        "source": "manual",
        "raw": s,
    }
    return s, [history_entry]


def _row_is_empty(row: tuple) -> bool:
    """Return True if all cells in the row are None or empty strings."""
    return all(
        v is None or (isinstance(v, str) and v.strip() == "")
        for v in row
    )


# ---------------------------------------------------------------------------
# Core migration
# ---------------------------------------------------------------------------

class MigrationReport:
    """Accumulates migration stats for the final stdout report."""

    def __init__(self) -> None:
        self.imported: dict[str, int] = {}   # tab -> count
        self.skipped: dict[str, int] = {}    # tab -> count
        self.warnings: list[str] = []

    def record_import(self, tab: str) -> None:
        self.imported[tab] = self.imported.get(tab, 0) + 1

    def record_skip(self, tab: str, reason: str) -> None:
        self.skipped[tab] = self.skipped.get(tab, 0) + 1
        self.warnings.append(f"[{tab}] Skipped row: {reason}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def print(self) -> None:
        total = sum(self.imported.values())
        print("\n========================================")
        print("  Exotiq XLSX Migration Report")
        print("========================================")
        print(f"\nTotal leads imported: {total}")
        print("\nPer-market counts:")
        for tab, count in self.imported.items():
            print(f"  {tab}: {count}")
        total_skipped = sum(self.skipped.values())
        print(f"\nSkipped rows: {total_skipped}")
        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for w in self.warnings[:50]:  # cap at 50 for readability
                print(f"  - {w}")
            if len(self.warnings) > 50:
                print(f"  ... and {len(self.warnings) - 50} more")
        print("\n========================================\n")


def _build_column_index(headers: tuple) -> dict[str, int]:
    """
    Map normalized header names to their column indices.
    Returns {normalized_name: 0-based_index}.
    """
    return {
        _normalize_col(h): i
        for i, h in enumerate(headers)
        if h is not None
    }


def _get_cell(row: tuple, col_index: dict[str, int], normalized_key: str) -> Any:
    """Return cell value for normalized column key, or None if not found."""
    idx = col_index.get(normalized_key)
    if idx is None:
        return None
    if idx >= len(row):
        return None
    return row[idx]


def _map_row_to_lead(
    row: tuple,
    col_index: dict[str, int],
    tab_name: str,
    seq: int,
    migration_ts: str,
    report: MigrationReport,
) -> Optional[dict[str, Any]]:
    """
    Convert a single xlsx row to a lead dict ready for INSERT.

    Returns None if the row should be skipped.
    """
    if _row_is_empty(row):
        return None

    # Require at minimum a company name
    company = _clean_str(_get_cell(row, col_index, "company"))
    if not company:
        report.record_skip(tab_name, "No company name")
        return None

    market_abbrev = MARKET_ABBREVS.get(tab_name, tab_name[:3].lower())
    lead_id = f"lead_{market_abbrev}_{seq:03d}"

    # Determine market from tab name (fallback to 'city + state' column)
    market_from_col = _clean_str(_get_cell(row, col_index, "market")) or \
                      _clean_str(_get_cell(row, col_index, "city + state"))
    market = market_from_col or tab_name

    # Client review determines confidence
    client_review_raw = _clean_str(
        _get_cell(row, col_index, "client review (y/n)")
        or _get_cell(row, col_index, "client review")
    )
    client_review_bool = _parse_boolean(client_review_raw)
    client_review = "Y" if client_review_bool else "N"
    confidence = "CONFIRMED" if client_review_bool else "ESTIMATED"

    # Handle company_email which may be phone
    company_email_raw = _clean_str(_get_cell(row, col_index, "company email"))
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    plain_email = _clean_str(_get_cell(row, col_index, "email"))
    if plain_email:
        contact_email = plain_email

    if company_email_raw:
        if _is_phone(company_email_raw):
            contact_phone = company_email_raw
            report.warn(f"[{tab_name}] Row {seq}: 'Company Email' remapped to phone: {company_email_raw}")
        else:
            # Use as email if we don't already have one
            if not contact_email:
                contact_email = company_email_raw

    # Enrichment notes
    enrichment_notes_raw = _get_cell(row, col_index, "enrichment notes")
    enrichment_notes_text, enrichment_history_entries = _parse_enrichment_notes(
        enrichment_notes_raw
    )

    # Client notes (append to notes)
    client_notes = _clean_str(_get_cell(row, col_index, "client notes"))
    notes_col = _clean_str(_get_cell(row, col_index, "notes"))
    notes_parts = [p for p in [notes_col, enrichment_notes_text, client_notes] if p]
    notes_combined = "\n---\n".join(notes_parts) if notes_parts else None

    # DM draft: prefer "Approved DM" (sets approval APPROVED), fallback "Draft DM"
    approved_dm = _clean_str(_get_cell(row, col_index, "approved dm"))
    draft_dm = _clean_str(_get_cell(row, col_index, "draft dm"))
    if approved_dm:
        outreach_dm_draft = approved_dm
        outreach_approval_status = "APPROVED"
    elif draft_dm:
        outreach_dm_draft = draft_dm
        outreach_approval_status = "PENDING"
    else:
        outreach_dm_draft = None
        outreach_approval_status = None

    # DM history appended to enrichment_history
    dm2_copy = _clean_str(_get_cell(row, col_index, "dm2 copy"))
    dm3_copy = _clean_str(_get_cell(row, col_index, "dm3 copy"))
    for copy_text, label in [(dm2_copy, "dm2_copy"), (dm3_copy, "dm3_copy")]:
        if copy_text:
            enrichment_history_entries.append({
                "action": label,
                "timestamp": migration_ts,
                "fields_updated": ["outreach_dm_draft"],
                "source": "manual",
                "raw": copy_text,
            })

    fleet_size_raw = _clean_int(_get_cell(row, col_index, "fleet size"))
    scoring_score_raw = _clean_int(_get_cell(row, col_index, "lead score"))

    lead: dict[str, Any] = {
        "id": lead_id,
        "company": company,
        "market": market,

        # Contact
        "contact_first_name": _clean_str(_get_cell(row, col_index, "first name")),
        "contact_first_name_source": "manual",
        "contact_first_name_confidence": confidence,
        "contact_last_name": _clean_str(_get_cell(row, col_index, "last name")),
        "contact_last_name_source": "manual",
        "contact_last_name_confidence": confidence,
        "contact_title": _clean_str(_get_cell(row, col_index, "title")),
        "contact_title_source": "manual",
        "contact_title_confidence": confidence,
        "contact_email": contact_email,
        "contact_email_source": "manual" if contact_email else None,
        "contact_email_confidence": confidence if contact_email else None,
        "contact_phone": contact_phone,
        "contact_phone_source": "manual" if contact_phone else None,
        "contact_phone_confidence": confidence if contact_phone else None,
        "contact_linkedin": _clean_str(_get_cell(row, col_index, "linkedin url (personal)")),
        "contact_ig_personal": _clean_str(_get_cell(row, col_index, "ig handle (personal)")),

        # Company
        "company_ig_handle": _clean_str(_get_cell(row, col_index, "ig handle (company)")),
        "company_ig_followers": None,
        "company_ig_followers_source": None,
        "company_ig_followers_confidence": None,
        "company_website": None,
        "company_address": None,
        "company_google_rating": None,
        "company_google_rating_source": None,
        "company_google_rating_confidence": None,
        "company_google_reviews": None,
        "company_google_reviews_source": None,
        "company_google_reviews_confidence": None,

        # Fleet
        "fleet_size": fleet_size_raw,
        "fleet_size_source": "manual" if fleet_size_raw is not None else None,
        "fleet_size_confidence": confidence if fleet_size_raw is not None else None,
        "fleet_vehicle_types": _parse_vehicle_types(_get_cell(row, col_index, "recent car post")),
        "fleet_vehicle_types_source": "manual",

        # Scoring
        "scoring_score": scoring_score_raw,
        "scoring_confidence": confidence if scoring_score_raw is not None else None,
        "scoring_rationale": None,
        "scoring_scored_at": migration_ts if scoring_score_raw is not None else None,
        "scoring_previous_score": None,

        # Outreach
        "outreach_status": _clean_str(_get_cell(row, col_index, "status")),
        "outreach_dm_draft": outreach_dm_draft,
        "outreach_template_used": None,
        "outreach_client_review": client_review,
        "outreach_approval_status": outreach_approval_status,
        "outreach_do_not_say": json.dumps([]),
        "outreach_dm1_sent": _clean_date(_get_cell(row, col_index, "dm1 sent date")),
        "outreach_dm2_sent": _clean_date(_get_cell(row, col_index, "dm2 sent date")),
        "outreach_dm3_sent": _clean_date(_get_cell(row, col_index, "dm3 sent date")),
        "outreach_response_received": _parse_boolean(
            _get_cell(row, col_index, "response received")
        ),
        "outreach_response_category": _clean_str(
            _get_cell(row, col_index, "response category")
        ),
        "outreach_response_date": _clean_date(_get_cell(row, col_index, "response date")),
        "outreach_calendly_sent": _clean_date(_get_cell(row, col_index, "calendly sent")),
        "outreach_demo_scheduled": _parse_boolean(
            _get_cell(row, col_index, "demo scheduled")
        ),

        # GHL -- all null/false for migrated rows
        "ghl_contact_id": None,
        "ghl_opportunity_id": None,
        "ghl_pipeline_stage": None,
        "ghl_last_sync": None,
        "ghl_in_ghl": False,
        "ghl_tags": json.dumps([]),

        # Meta
        "lead_source": _clean_str(_get_cell(row, col_index, "lead source")),
        "enrichment_history": json.dumps(enrichment_history_entries),
        "notes": notes_combined,
        "created_at": migration_ts,
        "updated_at": migration_ts,
    }

    return lead


def _import_metadata_tab(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    tab_name: str,
    conn,
    migration_ts: str,
    report: MigrationReport,
) -> None:
    """
    Import a metadata tab (Daily Activity Log, Lead Source Tracker) as activity_log entries.
    """
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return

    # Use headers from first row
    headers = rows[0]
    data_rows = rows[1:]
    imported = 0

    for row in data_rows:
        if _row_is_empty(row):
            continue
        # Represent each row as a JSON string in the description
        row_data = {
            str(headers[i]): str(v) if v is not None else None
            for i, v in enumerate(row)
            if i < len(headers) and headers[i] is not None
        }
        conn.execute(
            """
            INSERT INTO activity_log (timestamp, type, lead_id, description, source, agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                migration_ts,
                f"xlsx_import_{tab_name.lower().replace(' ', '_')}",
                None,
                json.dumps(row_data),
                "xlsx_migration",
                "migrate_xlsx",
            ),
        )
        imported += 1

    report.warn(f"[{tab_name}] Imported {imported} metadata rows as activity_log entries")


def migrate(xlsx_path: Path) -> None:
    """
    Main migration entry point.

    Args:
        xlsx_path: Path to the xlsx file.

    Raises:
        FileNotFoundError: If the xlsx file does not exist.
        RuntimeError: If the database is not initialized.
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(
            f"xlsx not found: {xlsx_path}\n"
            "Drop Miami_Operators_Clean_2.xlsx into the project root and re-run."
        )

    migration_ts = datetime.now(timezone.utc).isoformat()
    report = MigrationReport()

    print(f"Opening workbook: {xlsx_path}")
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)

    conn = get_db()
    conn.row_factory = None  # raw tuples during migration for performance

    try:
        for tab_name in wb.sheetnames:
            ws = wb[tab_name]

            if tab_name in SKIP_TABS:
                print(f"  Skipping tab: {tab_name}")
                continue

            if tab_name in METADATA_TABS:
                print(f"  Importing metadata tab: {tab_name}")
                _import_metadata_tab(ws, tab_name, conn, migration_ts, report)
                continue

            if tab_name not in MARKET_ABBREVS:
                report.warn(f"Unknown tab '{tab_name}' -- treating as lead tab with abbrev 'unk'")

            print(f"  Importing leads from: {tab_name}")
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                report.warn(f"[{tab_name}] No rows found")
                continue

            headers = rows[0]
            col_index = _build_column_index(headers)
            data_rows = rows[1:]
            seq = 1

            for row in data_rows:
                if _row_is_empty(row):
                    continue

                lead = _map_row_to_lead(
                    row, col_index, tab_name, seq, migration_ts, report
                )
                if lead is None:
                    continue

                # Check for duplicate ID and increment seq until unique
                while True:
                    existing = conn.execute(
                        "SELECT id FROM leads WHERE id = ?", (lead["id"],)
                    ).fetchone()
                    if existing is None:
                        break
                    seq += 1
                    market_abbrev = MARKET_ABBREVS.get(tab_name, tab_name[:3].lower())
                    lead["id"] = f"lead_{market_abbrev}_{seq:03d}"

                cols = ", ".join(lead.keys())
                placeholders = ", ".join("?" for _ in lead)
                try:
                    conn.execute(
                        f"INSERT INTO leads ({cols}) VALUES ({placeholders})",  # noqa: S608
                        list(lead.values()),
                    )
                    report.record_import(tab_name)
                    seq += 1
                except Exception as exc:
                    report.record_skip(tab_name, f"INSERT failed for '{lead.get('company')}': {exc}")

        conn.commit()

    finally:
        conn.close()
        wb.close()

    # Log the migration event
    log_activity(
        type="xlsx_migration",
        description=(
            f"Migrated {sum(report.imported.values())} leads from {xlsx_path.name}"
        ),
        source="xlsx_migration",
        agent="migrate_xlsx",
    )

    report.print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = DEFAULT_XLSX_PATH

    migrate(path)
