"""
Shared database utilities for the Exotiq Lead Intelligence Pipeline.

All functions use parameterized queries -- no string interpolation of user data.
"""

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).parent.parent / "db" / "exotiq.db"


def get_db() -> sqlite3.Connection:
    """
    Return a SQLite connection to the Exotiq database.

    The connection has row_factory set to sqlite3.Row so callers can
    access columns by name.  The caller is responsible for closing it.

    Raises:
        RuntimeError: If the database file does not exist.
    """
    if not DB_PATH.exists():
        raise RuntimeError(
            f"Database not found at {DB_PATH}. Run db/init_db.py first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def log_activity(
    type: str,
    description: str,
    lead_id: Optional[str] = None,
    source: Optional[str] = None,
    agent: Optional[str] = None,
) -> int:
    """
    Append a row to the activity_log table.

    Args:
        type: Event category, e.g. "enrichment", "scoring", "dm_draft", "ghl_push".
        description: Human-readable description of the action taken.
        lead_id: The lead this event belongs to, or None for system-level events.
        source: Data source involved, e.g. "apollo", "ig_profile", "manual".
        agent: Skill module that generated this event, e.g. "lead_scoring".

    Returns:
        The rowid of the newly inserted log entry.

    Raises:
        RuntimeError: If the database is unavailable.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            """
            INSERT INTO activity_log (timestamp, type, lead_id, description, source, agent)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (_now_iso(), type, lead_id, description, source, agent),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_lead(lead_id: str) -> Optional[dict[str, Any]]:
    """
    Fetch a lead record by ID.

    Args:
        lead_id: The lead's primary key, e.g. "lead_mia_001".

    Returns:
        A dict of all lead columns, or None if not found.

    Raises:
        RuntimeError: If the database is unavailable.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        conn.close()


def update_lead(lead_id: str, fields: dict[str, Any]) -> bool:
    """
    Update specific columns on a lead record.

    Always sets updated_at to the current UTC timestamp.

    Args:
        lead_id: The lead's primary key.
        fields: Dict of column_name -> new_value pairs to update.

    Returns:
        True if a row was updated, False if lead_id was not found.

    Raises:
        ValueError: If fields dict is empty or contains invalid column names.
        RuntimeError: If the database is unavailable.
    """
    if not fields:
        raise ValueError("fields dict must not be empty")

    # Merge updated_at into the update set
    fields = {**fields, "updated_at": _now_iso()}

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [lead_id]

    conn = get_db()
    try:
        cursor = conn.execute(
            f"UPDATE leads SET {set_clause} WHERE id = ?",  # noqa: S608
            values,
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def insert_lead(lead: dict[str, Any]) -> None:
    """
    Insert a new lead record.

    Args:
        lead: Dict of column_name -> value. Must include 'id', 'company',
              'created_at', and 'updated_at'.

    Raises:
        ValueError: If required keys are missing.
        sqlite3.IntegrityError: If the id already exists.
        RuntimeError: If the database is unavailable.
    """
    required = {"id", "company", "created_at", "updated_at"}
    missing = required - lead.keys()
    if missing:
        raise ValueError(f"Lead dict is missing required keys: {missing}")

    cols = ", ".join(lead.keys())
    placeholders = ", ".join("?" for _ in lead)
    conn = get_db()
    try:
        conn.execute(
            f"INSERT INTO leads ({cols}) VALUES ({placeholders})",  # noqa: S608
            list(lead.values()),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_leads(
    market: Optional[str] = None,
    min_score: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Return all leads, optionally filtered by market and/or minimum score.

    Args:
        market: If provided, only return leads with this market value.
        min_score: If provided, only return leads with scoring_score >= this value.

    Returns:
        List of lead dicts, ordered by scoring_score DESC, created_at DESC.

    Raises:
        RuntimeError: If the database is unavailable.
    """
    where_clauses: list[str] = []
    params: list[Any] = []

    if market is not None:
        where_clauses.append("market = ?")
        params.append(market)
    if min_score is not None:
        where_clauses.append("scoring_score >= ?")
        params.append(min_score)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT * FROM leads {where_sql} ORDER BY scoring_score DESC, created_at DESC",  # noqa: S608
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
