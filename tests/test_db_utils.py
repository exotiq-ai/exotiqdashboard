"""
Tests for skills/db_utils.py

Uses a temporary SQLite database so tests are isolated from the real db.
"""

import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills import db_utils


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path):
    """Redirect all db_utils calls to a fresh temporary database."""
    temp_db = tmp_path / "test_exotiq.db"
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(temp_db)
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()

    with patch.object(db_utils, "DB_PATH", temp_db):
        yield temp_db


def _insert_test_lead(lead_id: str = "lead_test_001") -> None:
    """Helper: insert a minimal lead for testing."""
    from skills.db_utils import insert_lead
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    insert_lead({
        "id": lead_id,
        "company": "Test Rentals LLC",
        "market": "Miami",
        "created_at": now,
        "updated_at": now,
    })


class TestGetDb:
    def test_returns_connection(self):
        conn = db_utils.get_db()
        assert conn is not None
        conn.close()

    def test_row_factory_set(self):
        conn = db_utils.get_db()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='leads'"
        ).fetchone()
        assert row["name"] == "leads"
        conn.close()

    def test_raises_when_db_missing(self, tmp_path):
        missing = tmp_path / "does_not_exist.db"
        with patch.object(db_utils, "DB_PATH", missing):
            with pytest.raises(RuntimeError, match="Database not found"):
                db_utils.get_db()


class TestLogActivity:
    def test_logs_entry_returns_rowid(self):
        rowid = db_utils.log_activity(
            type="test_event",
            description="unit test event",
            lead_id="lead_test_001",
            source="pytest",
            agent="test_db_utils",
        )
        assert isinstance(rowid, int)
        assert rowid >= 1

    def test_log_entry_readable(self):
        db_utils.log_activity(
            type="scoring",
            description="Scored lead at 4",
            lead_id="lead_mia_001",
            agent="lead_scoring",
        )
        conn = db_utils.get_db()
        row = conn.execute(
            "SELECT * FROM activity_log WHERE type = 'scoring'"
        ).fetchone()
        conn.close()
        assert row["description"] == "Scored lead at 4"
        assert row["lead_id"] == "lead_mia_001"
        assert row["agent"] == "lead_scoring"

    def test_system_event_no_lead_id(self):
        rowid = db_utils.log_activity(
            type="system",
            description="Pipeline started",
        )
        assert rowid is not None


class TestGetLead:
    def test_returns_none_for_missing(self):
        result = db_utils.get_lead("lead_nonexistent")
        assert result is None

    def test_returns_dict_for_existing(self):
        _insert_test_lead("lead_test_002")
        result = db_utils.get_lead("lead_test_002")
        assert result is not None
        assert result["id"] == "lead_test_002"
        assert result["company"] == "Test Rentals LLC"

    def test_all_columns_present(self):
        _insert_test_lead("lead_test_003")
        result = db_utils.get_lead("lead_test_003")
        assert "scoring_score" in result
        assert "ghl_in_ghl" in result
        assert "enrichment_history" in result


class TestUpdateLead:
    def test_updates_field(self):
        _insert_test_lead("lead_upd_001")
        updated = db_utils.update_lead("lead_upd_001", {"scoring_score": 4})
        assert updated is True

        result = db_utils.get_lead("lead_upd_001")
        assert result["scoring_score"] == 4

    def test_returns_false_for_missing_lead(self):
        updated = db_utils.update_lead("lead_nonexistent", {"scoring_score": 3})
        assert updated is False

    def test_raises_on_empty_fields(self):
        with pytest.raises(ValueError, match="must not be empty"):
            db_utils.update_lead("lead_test_001", {})

    def test_updated_at_is_refreshed(self):
        from datetime import datetime, timezone, timedelta
        old_ts = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        from skills.db_utils import insert_lead
        insert_lead({
            "id": "lead_ts_001",
            "company": "TS Rentals",
            "created_at": old_ts,
            "updated_at": old_ts,
        })
        db_utils.update_lead("lead_ts_001", {"notes": "updated note"})
        result = db_utils.get_lead("lead_ts_001")
        assert result["updated_at"] > old_ts


class TestGetAllLeads:
    def test_returns_empty_list_for_empty_db(self):
        result = db_utils.get_all_leads()
        assert result == []

    def test_filters_by_market(self):
        from skills.db_utils import insert_lead
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        insert_lead({"id": "lead_mia_f01", "company": "A", "market": "Miami", "created_at": now, "updated_at": now})
        insert_lead({"id": "lead_phx_f01", "company": "B", "market": "Phoenix", "created_at": now, "updated_at": now})

        result = db_utils.get_all_leads(market="Miami")
        assert len(result) == 1
        assert result[0]["id"] == "lead_mia_f01"

    def test_filters_by_min_score(self):
        from skills.db_utils import insert_lead
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        insert_lead({"id": "lead_sc_01", "company": "High", "scoring_score": 5, "created_at": now, "updated_at": now})
        insert_lead({"id": "lead_sc_02", "company": "Low", "scoring_score": 2, "created_at": now, "updated_at": now})

        result = db_utils.get_all_leads(min_score=4)
        assert len(result) == 1
        assert result[0]["id"] == "lead_sc_01"
