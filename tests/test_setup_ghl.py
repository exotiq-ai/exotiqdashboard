# tests/test_setup_ghl.py
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ghl.setup_ghl import (
    CUSTOM_FIELD_DEFS,
    PIPELINE_STAGES,
    ensure_custom_fields,
    ensure_pipeline,
    get_location_id,
    write_config,
)


def _mock_client(get_returns=None, post_returns=None):
    client = MagicMock()
    if get_returns is not None:
        client.get.return_value = get_returns
    if post_returns is not None:
        client.post.return_value = post_returns
    return client


class TestGetLocationId:
    def test_extracts_location_id_from_first_result(self):
        client = _mock_client(get_returns={
            "locations": [{"id": "loc-123", "name": "Exotiq"}]
        })
        assert get_location_id(client) == "loc-123"
        client.get.assert_called_once_with(
            "/locations/search", params={"limit": 20}
        )

    def test_raises_when_locations_empty(self):
        client = _mock_client(get_returns={"locations": []})
        with pytest.raises(RuntimeError, match="No locations found"):
            get_location_id(client)

    def test_raises_when_locations_key_missing(self):
        client = _mock_client(get_returns={})
        with pytest.raises(RuntimeError, match="No locations found"):
            get_location_id(client)


class TestEnsureCustomFields:
    def test_skips_fields_that_already_exist(self):
        existing = {
            "customFields": [
                {"id": "cf-001", "fieldKey": "contact.lead_score", "name": "Lead Score"},
                {"id": "cf-002", "fieldKey": "contact.fleet_size", "name": "Fleet Size"},
            ]
        }
        client = _mock_client(get_returns=existing)
        # post should only be called for the 13 missing fields
        client.post.return_value = {
            "customField": {"id": "cf-new", "fieldKey": "contact.ig_handle"}
        }
        result = ensure_custom_fields(client, "loc-123")
        assert client.post.call_count == len(CUSTOM_FIELD_DEFS) - 2
        assert result["lead_score"] == "cf-001"
        assert result["fleet_size"] == "cf-002"

    def test_creates_all_fields_when_none_exist(self):
        client = _mock_client(get_returns={"customFields": []})
        client.post.return_value = {"customField": {"id": "cf-new"}}
        ensure_custom_fields(client, "loc-123")
        assert client.post.call_count == len(CUSTOM_FIELD_DEFS)

    def test_all_15_field_keys_present(self):
        expected_keys = {
            "lead_score", "lead_score_confidence", "fleet_size",
            "fleet_size_confidence", "ig_handle", "ig_followers",
            "google_rating", "google_reviews", "vehicle_types",
            "dm_template_used", "dm_draft", "do_not_say",
            "enrichment_sources", "openclaw_lead_id", "pipeline_entry_date",
        }
        assert {d["key"] for d in CUSTOM_FIELD_DEFS} == expected_keys

    def test_dropdown_fields_include_options(self):
        dropdown = [d for d in CUSTOM_FIELD_DEFS if d["dataType"] == "DROPDOWN"]
        for d in dropdown:
            assert "options" in d and len(d["options"]) > 0


class TestEnsurePipeline:
    def test_skips_creation_if_pipeline_exists(self):
        existing = {
            "pipelines": [{
                "id": "pip-001",
                "name": "Exotiq Operator Sales",
                "stages": [{"id": "stg-001", "name": "New Lead"}],
            }]
        }
        client = _mock_client(get_returns=existing)
        result = ensure_pipeline(client, "loc-123")
        client.post.assert_not_called()
        assert result["pipeline_id"] == "pip-001"
        assert result["stages"]["New Lead"] == "stg-001"

    def test_creates_pipeline_with_16_stages_when_missing(self):
        client = _mock_client(get_returns={"pipelines": []})
        stage_objs = [
            {"id": f"stg-{i:03d}", "name": s}
            for i, s in enumerate(PIPELINE_STAGES)
        ]
        client.post.return_value = {
            "pipeline": {
                "id": "pip-new",
                "name": "Exotiq Operator Sales",
                "stages": stage_objs,
            }
        }
        result = ensure_pipeline(client, "loc-123")
        client.post.assert_called_once()
        payload = client.post.call_args.args[1]
        assert payload["name"] == "Exotiq Operator Sales"
        assert len(payload["stages"]) == 16
        assert result["pipeline_id"] == "pip-new"

    def test_pipeline_stages_are_all_16_in_order(self):
        expected = [
            "New Lead",
            "Gregory -- Personal Outreach",
            "DM Drafted",
            "DM Sent",
            "Follow-Up 1 Due",
            "Follow-Up 2 Due",
            "Responded -- Warm",
            "Responded -- Cold",
            "Call Scheduled",
            "Demo Scheduled",
            "Demo Complete",
            "Pilot Proposed",
            "Pilot Active",
            "Customer",
            "Not a Fit",
            "Nurture",
        ]
        assert PIPELINE_STAGES == expected


class TestWriteConfig:
    def test_writes_valid_json_to_path(self, tmp_path):
        config_path = str(tmp_path / "ghl_config.json")
        write_config(
            location_id="loc-123",
            custom_field_ids={"lead_score": "cf-001", "fleet_size": "cf-002"},
            pipeline_result={"pipeline_id": "pip-001", "stages": {"New Lead": "stg-001"}},
            config_path=config_path,
        )
        data = json.loads(Path(config_path).read_text())
        assert data["location_id"] == "loc-123"
        assert data["pipeline_id"] == "pip-001"
        assert data["custom_fields"]["lead_score"] == "cf-001"
        assert data["stages"]["New Lead"] == "stg-001"
