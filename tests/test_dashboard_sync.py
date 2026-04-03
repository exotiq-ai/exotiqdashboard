"""
Tests for skills/dashboard_sync.py

Verifies that sync_dashboard() correctly writes all 5 JSON output files,
reconstructs nested lead structure from flat SQLite rows, computes stats
accurately, guards against divide-by-zero in conversion rates, and parses
JSON string fields back to arrays.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import skills.dashboard_sync as ds_module
from skills.dashboard_sync import (
    sync_dashboard,
    _build_lead_object,
    _parse_json_field,
    _safe_divide,
)


# ---------------------------------------------------------------------------
# Shared test fixtures and helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc).isoformat()

FLAT_LEAD_ROW = {
    "id": "lead_mia_001",
    "company": "Exotic Rentals Miami",
    "contact_first_name": "Sofia",
    "contact_last_name": "Reyes",
    "contact_email": "sofia@example.com",
    "contact_phone": "+1-305-555-0199",
    "contact_linkedin": "https://linkedin.com/in/sofia-reyes",
    "contact_ig_personal": "@sofia_reyes",
    "company_ig_handle": "@exoticmia",
    "company_ig_followers": 12500,
    "company_website": "https://exoticmia.com",
    "company_address": "Miami, FL",
    "company_google_rating": 4.7,
    "company_google_reviews": 210,
    "fleet_size": 14,
    "fleet_size_confidence": "high",
    "fleet_vehicle_types": '["Lamborghini", "Ferrari"]',
    "fleet_vehicle_types_source": "ig_profile",
    "scoring_score": 5,
    "scoring_confidence": "high",
    "scoring_rationale": "High followers and fleet size",
    "scoring_scored_at": NOW,
    "scoring_previous_score": 4,
    "outreach_status": "DM Sent",
    "outreach_dm_draft": "Hey Sofia...",
    "outreach_template_used": "A",
    "outreach_client_review": "Y",
    "outreach_approval_status": "APPROVED",
    "outreach_dm1_sent": NOW,
    "outreach_dm2_sent": None,
    "outreach_dm3_sent": None,
    "outreach_response_received": True,
    "outreach_response_category": "Interested",
    "outreach_calendly_sent": None,
    "outreach_demo_scheduled": False,
    "ghl_contact_id": "ghl_123",
    "ghl_opportunity_id": "opp_456",
    "ghl_pipeline_stage": "Demo Scheduled",
    "ghl_last_sync": NOW,
    "ghl_in_ghl": 1,
    "ghl_tags": '["vip", "miami"]',
    "market": "Miami",
    "lead_source": "instagram",
    "enrichment_history": '["apollo", "ig_profile"]',
    "notes": "Strong prospect",
    "created_at": NOW,
    "updated_at": NOW,
}

FLAT_LEAD_ROW_2 = {
    **FLAT_LEAD_ROW,
    "id": "lead_mia_002",
    "company": "Speed Rides",
    "scoring_score": 3,
    "outreach_approval_status": "PENDING",
    "outreach_dm1_sent": None,
    "outreach_response_received": False,
    "ghl_in_ghl": 0,
    "ghl_tags": None,
    "fleet_vehicle_types": None,
    "enrichment_history": None,
    "market": "Phoenix Scottsdale",
}

FLAT_LEAD_ROW_UNSCORED = {
    **FLAT_LEAD_ROW,
    "id": "lead_mia_003",
    "company": "Unknown Fleet Co",
    "scoring_score": None,
    "outreach_approval_status": None,
    "outreach_dm1_sent": None,
    "outreach_response_received": False,
    "ghl_in_ghl": 0,
    "market": "Miami",
}

ALL_LEADS = [FLAT_LEAD_ROW, FLAT_LEAD_ROW_2, FLAT_LEAD_ROW_UNSCORED]


def _make_mock_conn(activity_rows=None, ghl_rows=None, ghl_error_rows=None):
    """Build a mock sqlite3.Connection whose .execute().fetchall() returns test data."""
    if activity_rows is None:
        activity_rows = []
    if ghl_rows is None:
        ghl_rows = []
    if ghl_error_rows is None:
        ghl_error_rows = []

    activity_dicts = [
        {"id": i + 1, "timestamp": NOW, "type": "test", "lead_id": None,
         "description": f"event {i}", "source": None, "agent": "pytest"}
        for i in range(len(activity_rows))
    ]

    ghl_sync_dicts = [
        {"id": i + 1, "timestamp": NOW, "direction": "outbound", "lead_id": None,
         "ghl_contact_id": None, "endpoint": "/contacts/", "http_status": 200,
         "payload_summary": "{}", "error_message": None}
        for i in range(len(ghl_rows))
    ]

    def _make_fetchall(data):
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [_dict_to_row(d) for d in data]
        return mock_result

    def _dict_to_row(d):
        """Wrap a plain dict so dict(row) works as well as row["key"]."""
        row = MagicMock()
        row.__iter__ = MagicMock(return_value=iter(d.items()))
        row.keys = MagicMock(return_value=list(d.keys()))
        row.__getitem__ = MagicMock(side_effect=d.__getitem__)
        return row

    conn = MagicMock()

    call_count = [0]

    def execute_side_effect(sql, *args, **kwargs):
        sql_upper = sql.strip().upper()
        call_count[0] += 1
        if "ACTIVITY_LOG" in sql_upper:
            return _make_fetchall(activity_dicts)
        elif "GHL_SYNC_LOG" in sql_upper and ("HTTP_STATUS >= 400" in sql_upper or "ERROR_MESSAGE" in sql_upper):
            return _make_fetchall(ghl_error_rows)
        elif "GHL_SYNC_LOG" in sql_upper:
            return _make_fetchall(ghl_sync_dicts)
        return _make_fetchall([])

    conn.execute.side_effect = execute_side_effect
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


# ---------------------------------------------------------------------------
# Test: output directory is created if it does not exist
# ---------------------------------------------------------------------------

class TestOutputDirCreation:
    def test_creates_nested_output_dir(self, tmp_path):
        mock_conn = _make_mock_conn()
        nested_subdir = "public/data/nested"
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=[]), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            sync_dashboard(output_dir=nested_subdir)

        assert (tmp_path / nested_subdir).is_dir(), (
            "sync_dashboard should create output_dir even when it does not exist"
        )

    def test_does_not_fail_if_dir_already_exists(self, tmp_path):
        existing = tmp_path / "public" / "data"
        existing.mkdir(parents=True)
        mock_conn = _make_mock_conn()
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=[]), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            # Should not raise
            sync_dashboard(output_dir="public/data")


# ---------------------------------------------------------------------------
# Test: all 5 files are written
# ---------------------------------------------------------------------------

class TestAllFilesWritten:
    def test_five_files_written(self, tmp_path):
        mock_conn = _make_mock_conn()
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=ALL_LEADS), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            result = sync_dashboard(output_dir="public/data")

        assert set(result["files_written"]) == {
            "leads.json",
            "activity.json",
            "stats.json",
            "ghl_sync_status.json",
            "pipeline_metrics.json",
        }

    def test_all_files_exist_on_disk(self, tmp_path):
        mock_conn = _make_mock_conn()
        out_dir = tmp_path / "public" / "data"
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=ALL_LEADS), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            sync_dashboard(output_dir="public/data")

        for fname in ["leads.json", "activity.json", "stats.json",
                      "ghl_sync_status.json", "pipeline_metrics.json"]:
            assert (out_dir / fname).exists(), f"{fname} was not written to disk"

    def test_return_dict_has_expected_keys(self, tmp_path):
        mock_conn = _make_mock_conn()
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=[]), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            result = sync_dashboard(output_dir="out")

        assert "files_written" in result
        assert "lead_count" in result
        assert "activity_count" in result


# ---------------------------------------------------------------------------
# Test: leads.json nested structure
# ---------------------------------------------------------------------------

class TestLeadsJsonStructure:
    def test_nested_contact_block(self, tmp_path):
        """contact fields from flat row are nested under 'contact' key."""
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert nested["contact"]["first_name"] == "Sofia"
        assert nested["contact"]["last_name"] == "Reyes"
        assert nested["contact"]["email"] == "sofia@example.com"
        assert nested["contact"]["phone"] == "+1-305-555-0199"
        assert nested["contact"]["linkedin"] == "https://linkedin.com/in/sofia-reyes"
        assert nested["contact"]["ig_personal"] == "@sofia_reyes"

    def test_nested_company_data_block(self, tmp_path):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert nested["company_data"]["ig_handle"] == "@exoticmia"
        assert nested["company_data"]["ig_followers"] == 12500
        assert nested["company_data"]["google_rating"] == 4.7
        assert nested["company_data"]["google_reviews"] == 210

    def test_nested_fleet_block(self, tmp_path):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert nested["fleet"]["size"] == 14
        assert nested["fleet"]["vehicle_types"] == ["Lamborghini", "Ferrari"]

    def test_nested_scoring_block(self, tmp_path):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert nested["scoring"]["score"] == 5
        assert nested["scoring"]["confidence"] == "high"
        assert nested["scoring"]["previous_score"] == 4

    def test_nested_outreach_block(self, tmp_path):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert nested["outreach"]["status"] == "DM Sent"
        assert nested["outreach"]["approval_status"] == "APPROVED"
        assert nested["outreach"]["dm1_sent"] == NOW

    def test_nested_ghl_block(self, tmp_path):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert nested["ghl"]["contact_id"] == "ghl_123"
        assert nested["ghl"]["in_ghl"] is True
        assert nested["ghl"]["tags"] == ["vip", "miami"]

    def test_top_level_fields_present(self, tmp_path):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert nested["id"] == "lead_mia_001"
        assert nested["company"] == "Exotic Rentals Miami"
        assert nested["market"] == "Miami"
        assert nested["lead_source"] == "instagram"
        assert isinstance(nested["enrichment_history"], list)
        assert nested["notes"] == "Strong prospect"

    def test_leads_json_is_valid_json_array(self, tmp_path):
        mock_conn = _make_mock_conn()
        out_dir = tmp_path / "public" / "data"
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=[FLAT_LEAD_ROW]), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            sync_dashboard(output_dir="public/data")

        data = json.loads((out_dir / "leads.json").read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "lead_mia_001"


# ---------------------------------------------------------------------------
# Test: stats.json by_score counts
# ---------------------------------------------------------------------------

class TestStatsJsonScoreCounts:
    def _get_stats(self, tmp_path, leads):
        mock_conn = _make_mock_conn()
        out_dir = tmp_path / "out"
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=leads), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            sync_dashboard(output_dir="out")
        return json.loads((out_dir / "stats.json").read_text())

    def test_score_5_counted(self, tmp_path):
        stats = self._get_stats(tmp_path, [FLAT_LEAD_ROW])
        assert stats["by_score"]["5"] == 1

    def test_score_3_counted(self, tmp_path):
        stats = self._get_stats(tmp_path, [FLAT_LEAD_ROW_2])
        assert stats["by_score"]["3"] == 1

    def test_unscored_counted(self, tmp_path):
        stats = self._get_stats(tmp_path, [FLAT_LEAD_ROW_UNSCORED])
        assert stats["by_score"]["unscored"] == 1

    def test_multiple_leads_aggregated(self, tmp_path):
        stats = self._get_stats(tmp_path, ALL_LEADS)
        assert stats["total_leads"] == 3
        assert stats["by_score"]["5"] == 1
        assert stats["by_score"]["3"] == 1
        assert stats["by_score"]["unscored"] == 1

    def test_by_market_counts(self, tmp_path):
        stats = self._get_stats(tmp_path, ALL_LEADS)
        # lead_mia_001 (Miami), lead_mia_003 (Miami) = 2; lead_mia_002 (Phoenix) = 1
        assert stats["by_market"]["Miami"] == 2
        assert stats["by_market"]["Phoenix Scottsdale"] == 1

    def test_ghl_synced_count(self, tmp_path):
        stats = self._get_stats(tmp_path, ALL_LEADS)
        # Only FLAT_LEAD_ROW has ghl_in_ghl=1
        assert stats["ghl_synced"] == 1

    def test_pending_approval_count(self, tmp_path):
        stats = self._get_stats(tmp_path, ALL_LEADS)
        # Only FLAT_LEAD_ROW_2 has PENDING
        assert stats["pending_approval"] == 1

    def test_stats_has_generated_at(self, tmp_path):
        stats = self._get_stats(tmp_path, [])
        assert "generated_at" in stats


# ---------------------------------------------------------------------------
# Test: conversion_rates do not divide by zero
# ---------------------------------------------------------------------------

class TestConversionRates:
    def test_safe_divide_zero_denominator(self):
        assert _safe_divide(10, 0) == 0.0

    def test_safe_divide_normal(self):
        assert _safe_divide(1, 4) == 0.25

    def test_safe_divide_rounds_to_3_decimal_places(self):
        result = _safe_divide(1, 3)
        assert result == round(1 / 3, 3)

    def _get_metrics(self, tmp_path, leads):
        mock_conn = _make_mock_conn()
        out_dir = tmp_path / "out"
        with patch.object(ds_module, "PROJECT_ROOT", tmp_path), \
             patch.object(ds_module, "get_all_leads", return_value=leads), \
             patch.object(ds_module, "get_db", return_value=mock_conn), \
             patch.object(ds_module, "log_activity"):
            sync_dashboard(output_dir="out")
        return json.loads((out_dir / "pipeline_metrics.json").read_text())

    def test_no_division_by_zero_with_empty_leads(self, tmp_path):
        metrics = self._get_metrics(tmp_path, [])
        rates = metrics["conversion_rates"]
        assert rates["lead_to_dm"] == 0.0
        assert rates["dm_to_response"] == 0.0
        assert rates["response_to_demo"] == 0.0

    def test_no_division_by_zero_no_dms_sent(self, tmp_path):
        """When dm1_sent is None for all leads, dm_to_response should be 0.0."""
        leads = [FLAT_LEAD_ROW_UNSCORED]  # dm1_sent=None
        metrics = self._get_metrics(tmp_path, leads)
        assert metrics["conversion_rates"]["dm_to_response"] == 0.0

    def test_no_division_by_zero_no_responses(self, tmp_path):
        """When no lead responded, response_to_demo should be 0.0."""
        leads = [FLAT_LEAD_ROW_2]  # response_received=False
        metrics = self._get_metrics(tmp_path, leads)
        assert metrics["conversion_rates"]["response_to_demo"] == 0.0

    def test_correct_lead_to_dm_rate(self, tmp_path):
        """1 out of 3 leads has dm1_sent set -- rate should be 0.333."""
        metrics = self._get_metrics(tmp_path, ALL_LEADS)
        # Only FLAT_LEAD_ROW has outreach_dm1_sent set
        assert metrics["conversion_rates"]["lead_to_dm"] == round(1 / 3, 3)


# ---------------------------------------------------------------------------
# Test: JSON string fields parsed back to arrays
# ---------------------------------------------------------------------------

class TestJsonStringFieldParsing:
    def test_fleet_vehicle_types_parsed_to_list(self):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert isinstance(nested["fleet"]["vehicle_types"], list)
        assert "Lamborghini" in nested["fleet"]["vehicle_types"]

    def test_ghl_tags_parsed_to_list(self):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert isinstance(nested["ghl"]["tags"], list)
        assert "vip" in nested["ghl"]["tags"]

    def test_enrichment_history_parsed_to_list(self):
        nested = _build_lead_object(FLAT_LEAD_ROW)
        assert isinstance(nested["enrichment_history"], list)
        assert "apollo" in nested["enrichment_history"]

    def test_none_json_field_returns_empty_list(self):
        nested = _build_lead_object(FLAT_LEAD_ROW_2)
        assert nested["fleet"]["vehicle_types"] == []
        assert nested["ghl"]["tags"] == []
        assert nested["enrichment_history"] == []

    def test_malformed_json_field_returns_empty_list(self):
        row = {**FLAT_LEAD_ROW, "fleet_vehicle_types": "not-json"}
        nested = _build_lead_object(row)
        assert nested["fleet"]["vehicle_types"] == []

    def test_parse_json_field_helper_with_valid_json(self):
        result = _parse_json_field('["a", "b"]')
        assert result == ["a", "b"]

    def test_parse_json_field_helper_with_none(self):
        assert _parse_json_field(None) == []

    def test_parse_json_field_helper_with_empty_string(self):
        assert _parse_json_field("") == []

    def test_parse_json_field_helper_with_custom_fallback(self):
        assert _parse_json_field(None, fallback={"default": True}) == {"default": True}
