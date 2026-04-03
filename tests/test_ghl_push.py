# tests/test_ghl_push.py
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.ghl_push import (
    _build_contact_payload,
    _build_tags,
    _compute_monetary_value,
    _load_config,
    push_approved_batch,
    push_lead_to_ghl,
)


MOCK_CONFIG = {
    "location_id": "loc-123",
    "pipeline_id": "pip-001",
    "stages": {
        "Gregory -- Personal Outreach": "stg-001",
        "DM Drafted": "stg-002",
        "New Lead": "stg-003",
    },
    "custom_fields": {
        "lead_score": "cf-001",
        "lead_score_confidence": "cf-002",
        "fleet_size": "cf-003",
        "fleet_size_confidence": "cf-004",
        "ig_handle": "cf-005",
        "ig_followers": "cf-006",
        "google_rating": "cf-007",
        "google_reviews": "cf-008",
        "vehicle_types": "cf-009",
        "dm_template_used": "cf-010",
        "dm_draft": "cf-011",
        "do_not_say": "cf-012",
        "enrichment_sources": "cf-013",
        "openclaw_lead_id": "cf-014",
        "pipeline_entry_date": "cf-015",
    },
}


def _make_lead(**overrides) -> dict:
    base = {
        "id": "lead_mia_001",
        "company": "Prestige Luxury Rentals",
        "contact_first_name": "Xavier",
        "contact_last_name": "Guerrero",
        "contact_email": "xavier@prestige.com",
        "contact_phone": "+17862024892",
        "company_address": "4019 NW 25th Street, Miami",
        "company_website": "prestigeluxuryrentals.com",
        "market": "Miami",
        "scoring_score": 4,
        "scoring_confidence": "HIGH",
        "fleet_size": 20,
        "fleet_size_confidence": "ESTIMATED",
        "company_ig_handle": "@prestige",
        "company_ig_followers": 5000,
        "company_google_rating": 4.7,
        "company_google_reviews": 100,
        "fleet_vehicle_types": json.dumps(["Lamborghini", "Ferrari"]),
        "outreach_approval_status": "APPROVED",
        "outreach_template_used": "D",
        "outreach_dm_draft": "Hey, Gregory here...",
        "outreach_do_not_say": json.dumps([]),
        "ghl_in_ghl": 0,
        "ghl_contact_id": None,
        "ghl_opportunity_id": None,
        "ghl_tags": json.dumps([]),
        "lead_source": "Apollo + IG Research",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _build_tags
# ---------------------------------------------------------------------------

class TestBuildTags:
    def test_always_includes_exotiq_pipeline(self):
        assert "exotiq-pipeline" in _build_tags(_make_lead())

    def test_score_tag(self):
        assert "score-4" in _build_tags(_make_lead(scoring_score=4))

    def test_market_lowercased_and_hyphenated(self):
        assert "phoenix-scottsdale" in _build_tags(_make_lead(market="Phoenix Scottsdale"))

    def test_fleet_tier_under_10(self):
        assert "under-10-fleet" in _build_tags(_make_lead(fleet_size=5))

    def test_fleet_tier_10_to_24(self):
        assert "10-to-24-fleet" in _build_tags(_make_lead(fleet_size=15))

    def test_fleet_tier_25_plus(self):
        assert "25-plus-fleet" in _build_tags(_make_lead(fleet_size=30))

    def test_score_5_gets_gregory_only(self):
        assert "gregory-only" in _build_tags(_make_lead(scoring_score=5, fleet_size=30))

    def test_score_4_no_gregory_only(self):
        assert "gregory-only" not in _build_tags(_make_lead(scoring_score=4, fleet_size=20))


# ---------------------------------------------------------------------------
# _compute_monetary_value
# ---------------------------------------------------------------------------

class TestComputeMonetaryValue:
    def test_formula_fleet_times_350_times_365_times_0_6(self):
        assert _compute_monetary_value(10) == round(10 * 350 * 365 * 0.6)

    def test_none_returns_zero(self):
        assert _compute_monetary_value(None) == 0

    def test_zero_returns_zero(self):
        assert _compute_monetary_value(0) == 0


# ---------------------------------------------------------------------------
# _build_contact_payload
# ---------------------------------------------------------------------------

class TestBuildContactPayload:
    def test_native_fields_mapped(self):
        payload = _build_contact_payload(_make_lead(), MOCK_CONFIG)
        assert payload["firstName"] == "Xavier"
        assert payload["lastName"] == "Guerrero"
        assert payload["email"] == "xavier@prestige.com"
        assert payload["phone"] == "+17862024892"
        assert payload["companyName"] == "Prestige Luxury Rentals"
        assert payload["locationId"] == "loc-123"
        assert payload["source"] == "OpenClaw Pipeline"

    def test_custom_fields_are_list_of_id_value_pairs(self):
        payload = _build_contact_payload(_make_lead(), MOCK_CONFIG)
        cf = payload["customFields"]
        assert isinstance(cf, list)
        cf_by_id = {item["id"]: item["field_value"] for item in cf}
        assert cf_by_id["cf-001"] == "4"              # lead_score
        assert cf_by_id["cf-014"] == "lead_mia_001"   # openclaw_lead_id

    def test_tags_included(self):
        payload = _build_contact_payload(
            _make_lead(scoring_score=4, fleet_size=20, market="Miami"), MOCK_CONFIG
        )
        assert "exotiq-pipeline" in payload["tags"]
        assert "score-4" in payload["tags"]
        assert "miami" in payload["tags"]


# ---------------------------------------------------------------------------
# _load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_valid_config(self, tmp_path):
        f = tmp_path / "ghl_config.json"
        f.write_text(json.dumps(MOCK_CONFIG))
        result = _load_config(str(f))
        assert result["location_id"] == "loc-123"

    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="ghl_config.json"):
            _load_config(str(tmp_path / "missing.json"))


# ---------------------------------------------------------------------------
# push_lead_to_ghl -- pre-flight failures
# ---------------------------------------------------------------------------

class TestPushLeadPreflightChecks:
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_raises_when_score_below_3(self, mock_get, mock_cfg):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(scoring_score=2)
        with pytest.raises(ValueError, match="score"):
            push_lead_to_ghl("lead_mia_001")

    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_raises_when_not_approved(self, mock_get, mock_cfg):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(outreach_approval_status="PENDING")
        with pytest.raises(ValueError, match="approval_status"):
            push_lead_to_ghl("lead_mia_001")

    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_raises_when_no_email_or_phone(self, mock_get, mock_cfg):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(contact_email=None, contact_phone=None)
        with pytest.raises(ValueError, match="email or phone"):
            push_lead_to_ghl("lead_mia_001")


# ---------------------------------------------------------------------------
# push_lead_to_ghl -- create vs. update
# ---------------------------------------------------------------------------

class TestPushLeadToGHL:
    def _setup_mocks(self, scoring_score=4, fleet_size=20):
        lead = _make_lead(scoring_score=scoring_score, fleet_size=fleet_size)
        return lead

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_creates_new_contact_when_no_duplicate(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": []}
        mock_client.post.side_effect = [
            {"contact": {"id": "ghl-contact-001"}},
            {"opportunity": {"id": "ghl-opp-001"}},
        ]
        result = push_lead_to_ghl("lead_mia_001")
        assert result["contact_id"] == "ghl-contact-001"
        assert result["opportunity_id"] == "ghl-opp-001"
        assert result["action"] == "created"
        update_fields = mock_upd.call_args.args[1]
        assert update_fields["ghl_contact_id"] == "ghl-contact-001"
        assert update_fields["ghl_in_ghl"] == 1

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_updates_existing_contact_when_duplicate_found(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead()
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": [{"id": "existing-ghl-001"}]}
        mock_client.put.return_value = {"contact": {"id": "existing-ghl-001"}}
        mock_client.post.return_value = {"opportunity": {"id": "opp-002"}}
        result = push_lead_to_ghl("lead_mia_001")
        mock_client.put.assert_called_once()
        assert result["contact_id"] == "existing-ghl-001"
        assert result["action"] == "updated"

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_score_5_uses_gregory_personal_outreach_stage(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(scoring_score=5, fleet_size=30)
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": []}
        mock_client.post.side_effect = [
            {"contact": {"id": "ghl-s5"}},
            {"opportunity": {"id": "opp-s5"}},
        ]
        push_lead_to_ghl("lead_mia_001")
        opp_payload = mock_client.post.call_args_list[1].args[1]
        assert opp_payload["pipelineStageId"] == "stg-001"  # Gregory stage

    @patch("skills.ghl_push._log_ghl_sync")
    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.update_lead")
    @patch("skills.ghl_push.GHLClient")
    @patch("skills.ghl_push._load_config")
    @patch("skills.ghl_push.get_lead")
    def test_score_4_uses_dm_drafted_stage(
        self, mock_get, mock_cfg, mock_cls, mock_upd, mock_log, mock_sync
    ):
        mock_cfg.return_value = MOCK_CONFIG
        mock_get.return_value = _make_lead(scoring_score=4, fleet_size=20)
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.get.return_value = {"contacts": []}
        mock_client.post.side_effect = [
            {"contact": {"id": "ghl-s4"}},
            {"opportunity": {"id": "opp-s4"}},
        ]
        push_lead_to_ghl("lead_mia_001")
        opp_payload = mock_client.post.call_args_list[1].args[1]
        assert opp_payload["pipelineStageId"] == "stg-002"  # DM Drafted


# ---------------------------------------------------------------------------
# push_approved_batch
# ---------------------------------------------------------------------------

class TestPushApprovedBatch:
    @patch("skills.ghl_push.push_lead_to_ghl")
    @patch("skills.ghl_push.get_db")
    def test_pushes_all_qualifying_leads(self, mock_get_db, mock_push):
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [
            {"id": "lead_001"}, {"id": "lead_002"}
        ]
        mock_push.return_value = {"contact_id": "c1", "opportunity_id": "o1", "action": "created"}
        result = push_approved_batch()
        assert result["pushed"] == 2
        assert result["errors"] == 0

    @patch("skills.ghl_push.log_activity")
    @patch("skills.ghl_push.push_lead_to_ghl")
    @patch("skills.ghl_push.get_db")
    def test_continues_after_validation_error(self, mock_get_db, mock_push, mock_log):
        from ghl.ghl_client import GHLValidationError
        mock_conn = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.execute.return_value.fetchall.return_value = [{"id": "lead_001"}]
        mock_push.side_effect = GHLValidationError("bad field")
        result = push_approved_batch()
        assert result["pushed"] == 0
        assert result["errors"] == 1
