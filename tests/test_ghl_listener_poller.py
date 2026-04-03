# tests/test_ghl_listener_poller.py
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.ghl_listener_poller import (
    _handle_appointment_create,
    _handle_contact_update,
    _handle_inbound_message,
    _handle_note_create,
    _handle_opportunity_status_update,
    poll_event_queue,
    process_event,
)


def _make_event(event_type: str, **kwargs) -> dict:
    base = {
        "type": event_type,
        "received_at": "2026-04-03T12:00:00Z",
        "locationId": "loc-123",
    }
    base.update(kwargs)
    return base


class TestHandleContactUpdate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_updates_contact_fields(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event(
            "ContactUpdate",
            contactId="ghl-001",
            contact={"email": "new@email.com", "phone": "+1555000"},
        )
        _handle_contact_update(event)
        fields = mock_update.call_args.args[1]
        assert fields["contact_email"] == "new@email.com"
        assert fields["contact_phone"] == "+1555000"

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_noop_when_lead_not_found(self, mock_find, mock_log):
        mock_find.return_value = None
        _handle_contact_update(_make_event("ContactUpdate", contactId="unknown"))
        # no exception -- just returns


class TestHandleOpportunityStatusUpdate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_updates_pipeline_stage(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event(
            "OpportunityStatusUpdate",
            contactId="ghl-001",
            opportunity={"pipelineStage": {"name": "Responded -- Warm"}},
        )
        _handle_opportunity_status_update(event)
        fields = mock_update.call_args.args[1]
        assert fields["ghl_pipeline_stage"] == "Responded -- Warm"
        assert fields["outreach_status"] == "Responded -- Warm"

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_demo_scheduled_sets_flag(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event(
            "OpportunityStatusUpdate",
            contactId="ghl-001",
            opportunity={"pipelineStage": {"name": "Demo Scheduled"}},
        )
        _handle_opportunity_status_update(event)
        fields = mock_update.call_args.args[1]
        assert fields["outreach_demo_scheduled"] == 1


class TestHandleNoteCreate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.get_lead")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_appends_note_to_existing(self, mock_find, mock_update, mock_get, mock_log):
        mock_find.return_value = "lead_mia_001"
        mock_get.return_value = {"id": "lead_mia_001", "notes": "Old note.", "contact_phone": None, "fleet_size": None}
        event = _make_event("NoteCreate", contactId="ghl-001", note={"body": "New intel."})
        _handle_note_create(event)
        fields = mock_update.call_args.args[1]
        assert "Old note." in fields["notes"]
        assert "New intel." in fields["notes"]

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.get_lead")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_sets_note_when_none_exists(self, mock_find, mock_update, mock_get, mock_log):
        mock_find.return_value = "lead_mia_001"
        mock_get.return_value = {"id": "lead_mia_001", "notes": None, "contact_phone": None, "fleet_size": None}
        event = _make_event("NoteCreate", contactId="ghl-001", note={"body": "First note."})
        _handle_note_create(event)
        fields = mock_update.call_args.args[1]
        assert "First note." in fields["notes"]


class TestHandleInboundMessage:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_sets_response_received(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("InboundMessage", contactId="ghl-001",
                            message={"body": "Hey, sounds interesting."})
        _handle_inbound_message(event)
        fields = mock_update.call_args.args[1]
        assert fields["outreach_response_received"] == 1

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_positive_message_categorized_as_interested(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("InboundMessage", contactId="ghl-001",
                            message={"body": "Yes, I'm interested! Let's schedule."})
        _handle_inbound_message(event)
        assert mock_update.call_args.args[1]["outreach_response_category"] == "interested"

    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_negative_message_categorized_as_cold(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("InboundMessage", contactId="ghl-001",
                            message={"body": "Not interested, please stop."})
        _handle_inbound_message(event)
        assert mock_update.call_args.args[1]["outreach_response_category"] == "cold"


class TestHandleAppointmentCreate:
    @patch("skills.ghl_listener_poller.log_activity")
    @patch("skills.ghl_listener_poller.update_lead")
    @patch("skills.ghl_listener_poller._find_lead_by_ghl_id")
    def test_sets_demo_scheduled(self, mock_find, mock_update, mock_log):
        mock_find.return_value = "lead_mia_001"
        event = _make_event("AppointmentCreate", contactId="ghl-001",
                            appointment={"startTime": "2026-04-10T14:00:00Z", "title": "Demo"})
        _handle_appointment_create(event)
        assert mock_update.call_args.args[1]["outreach_demo_scheduled"] == 1


class TestPollEventQueue:
    def test_processes_and_archives_event_files(self, tmp_path):
        queue_dir = tmp_path / "event_queue"
        queue_dir.mkdir()
        processed_dir = queue_dir / "processed"

        event_data = {
            "type": "ContactUpdate",
            "contactId": "ghl-001",
            "contact": {"email": "test@test.com"},
            "received_at": "2026-04-03T12:00:00Z",
        }
        event_file = queue_dir / "1234567890_ContactUpdate.json"
        event_file.write_text(json.dumps(event_data))

        with patch("skills.ghl_listener_poller._handle_contact_update"), \
             patch("skills.ghl_listener_poller._find_lead_by_ghl_id", return_value="lead_001"), \
             patch("skills.ghl_listener_poller.update_lead"), \
             patch("skills.ghl_listener_poller.log_activity"):
            result = poll_event_queue(queue_path=str(queue_dir))

        assert result["processed"] == 1
        assert result["errors"] == 0
        assert not event_file.exists()
        assert (processed_dir / "1234567890_ContactUpdate.json").exists()

    def test_ignores_non_json_files(self, tmp_path):
        queue_dir = tmp_path / "eq"
        queue_dir.mkdir()
        (queue_dir / ".gitkeep").write_text("")
        result = poll_event_queue(queue_path=str(queue_dir))
        assert result["processed"] == 0

    def test_handles_malformed_json_gracefully(self, tmp_path):
        queue_dir = tmp_path / "eq"
        queue_dir.mkdir()
        (queue_dir / "123_bad.json").write_text("{not valid json")
        with patch("skills.ghl_listener_poller.log_activity"):
            result = poll_event_queue(queue_path=str(queue_dir))
        assert result["errors"] == 1

    def test_returns_zero_counts_when_queue_dir_missing(self, tmp_path):
        result = poll_event_queue(queue_path=str(tmp_path / "nonexistent"))
        assert result == {"processed": 0, "errors": 0}
