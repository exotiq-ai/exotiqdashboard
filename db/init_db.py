#!/usr/bin/env python3
"""
Initialize the Exotiq SQLite database.

Creates db/exotiq.db and runs db/schema.sql.
Safe to re-run -- all CREATE statements use IF NOT EXISTS.
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "exotiq.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db() -> None:
    """Create the database and apply the schema."""
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema.sql not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(1)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"Database initialized at: {DB_PATH.resolve()}")

    # Verify tables exist
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

    print(f"Tables created: {', '.join(tables)}")


if __name__ == "__main__":
    init_db()
