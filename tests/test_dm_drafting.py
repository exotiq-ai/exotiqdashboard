"""
Tests for skills/dm_drafting.py

All database I/O is patched via unittest.mock so tests run without a live DB.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.dm_drafting import (
    _MAX_WORDS,
    _build_do_not_say,
    _build_dm_text,
    _check_forbidden_content,
    _enforce_word_limit,
    _replace_em_dashes,
    _resolve_fleet_context,
    _resolve_handle,
    _resolve_vehicle_mention,
    _select_template,
    draft_dm,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_lead(
    lead_id: str = "lead_test_001",
    company: str = "Apex Exotics",
    market: str = "Miami",
    scoring_score: int = None,
    outreach_status: str = None,
    fleet_vehicle_types: str = None,
    fleet_size: int = None,
    contact_ig_personal: str = None,
    company_ig_handle: str = None,
    notes: str = None,
) -> dict:
    """Build a minimal lead dict for testing."""
    return {
        "id": lead_id,
        "company": company,
        "market": market,
        "scoring_score": scoring_score,
        "outreach_status": outreach_status,
        "fleet_vehicle_types": fleet_vehicle_types,
        "fleet_size": fleet_size,
        "contact_ig_personal": contact_ig_personal,
        "company_ig_handle": company_ig_handle,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Template selection
# ---------------------------------------------------------------------------


class TestSelectTemplate:
    """Verify that _select_template picks the correct letter for each condition."""

    def test_score_3_returns_d(self):
        lead = _make_lead(scoring_score=3)
        # score=3 with no fleet_vehicle_types -> D (E requires vehicle types)
        assert _select_template(lead) == "D"

    def test_score_4_returns_d(self):
        lead = _make_lead(scoring_score=4)
        assert _select_template(lead) == "D"

    def test_score_5_returns_b(self):
        # score=5 but no fleet_vehicle_types -> B
        lead = _make_lead(scoring_score=5)
        assert _select_template(lead) == "B"

    def test_score_none_returns_d(self):
        lead = _make_lead(scoring_score=None)
        assert _select_template(lead) == "D"

    def test_score_2_returns_d(self):
        """Scores below 3 should default to D."""
        lead = _make_lead(scoring_score=2)
        assert _select_template(lead) == "D"

    def test_score_3_with_vehicles_returns_e(self):
        lead = _make_lead(
            scoring_score=3,
            fleet_vehicle_types='["Lamborghini Huracan"]',
        )
        assert _select_template(lead) == "E"

    def test_score_5_with_vehicles_returns_e(self):
        """E takes priority over B when vehicles are present and score >= 3."""
        lead = _make_lead(
            scoring_score=5,
            fleet_vehicle_types='["Ferrari 488"]',
        )
        assert _select_template(lead) == "E"

    def test_failed_outreach_returns_f(self):
        lead = _make_lead(scoring_score=5, outreach_status="failed")
        assert _select_template(lead) == "F"

    def test_error_outreach_returns_f(self):
        lead = _make_lead(outreach_status="error")
        assert _select_template(lead) == "F"

    def test_f_beats_e(self):
        """F should win even when E criteria are also met."""
        lead = _make_lead(
            scoring_score=5,
            fleet_vehicle_types='["McLaren 720S"]',
            outreach_status="failed",
        )
        assert _select_template(lead) == "F"

    def test_f_beats_b(self):
        lead = _make_lead(scoring_score=5, outreach_status="bounced")
        assert _select_template(lead) == "F"

    def test_outreach_status_case_insensitive(self):
        lead = _make_lead(outreach_status="FAILED")
        assert _select_template(lead) == "F"

    def test_none_outreach_status_does_not_trigger_f(self):
        lead = _make_lead(scoring_score=3, outreach_status=None)
        assert _select_template(lead) == "D"

    def test_score_1_returns_d(self):
        lead = _make_lead(scoring_score=1)
        assert _select_template(lead) == "D"


# ---------------------------------------------------------------------------
# Variable resolution helpers
# ---------------------------------------------------------------------------


class TestResolveHandle:
    def test_prefers_contact_ig_personal(self):
        lead = _make_lead(
            contact_ig_personal="@johnexotics",
            company_ig_handle="@apexrentals",
        )
        assert _resolve_handle(lead) == "johnexotics"

    def test_strips_at_sign(self):
        lead = _make_lead(contact_ig_personal="@speed_demon")
        assert _resolve_handle(lead) == "speed_demon"

    def test_falls_back_to_company_ig_handle(self):
        lead = _make_lead(
            contact_ig_personal=None,
            company_ig_handle="@apexrentals",
        )
        assert _resolve_handle(lead) == "apexrentals"

    def test_falls_back_to_company_name(self):
        lead = _make_lead(
            contact_ig_personal=None,
            company_ig_handle=None,
            company="Apex Exotics LLC",
        )
        assert _resolve_handle(lead) == "Apex Exotics LLC"

    def test_empty_ig_fields_use_company(self):
        lead = _make_lead(contact_ig_personal="", company_ig_handle="")
        assert _resolve_handle(lead) == "Apex Exotics"


class TestResolveFleetContext:
    def test_with_fleet_size(self):
        lead = _make_lead(fleet_size=8)
        assert _resolve_fleet_context(lead) == "running 8 cars"

    def test_without_fleet_size(self):
        lead = _make_lead(fleet_size=None)
        assert _resolve_fleet_context(lead) == "running a solid fleet"

    def test_zero_fleet_size_uses_default(self):
        """fleet_size=0 is falsy so should return default phrase."""
        lead = _make_lead(fleet_size=0)
        assert _resolve_fleet_context(lead) == "running a solid fleet"


class TestResolveVehicleMention:
    def test_returns_first_vehicle(self):
        lead = _make_lead(fleet_vehicle_types='["Lamborghini Urus", "Ferrari 488"]')
        assert _resolve_vehicle_mention(lead) == "Lamborghini Urus"

    def test_single_vehicle(self):
        lead = _make_lead(fleet_vehicle_types='["Rolls-Royce Phantom"]')
        assert _resolve_vehicle_mention(lead) == "Rolls-Royce Phantom"

    def test_none_returns_fleet(self):
        lead = _make_lead(fleet_vehicle_types=None)
        assert _resolve_vehicle_mention(lead) == "fleet"

    def test_invalid_json_returns_fleet(self):
        lead = _make_lead(fleet_vehicle_types="not json")
        assert _resolve_vehicle_mention(lead) == "fleet"

    def test_empty_list_returns_fleet(self):
        lead = _make_lead(fleet_vehicle_types="[]")
        assert _resolve_vehicle_mention(lead) == "fleet"


# ---------------------------------------------------------------------------
# Word count enforcement
# ---------------------------------------------------------------------------


class TestEnforceWordLimit:
    def test_short_text_unchanged(self):
        text = "Hello there friend."
        assert _enforce_word_limit(text, max_words=150) == text

    def test_exactly_at_limit_unchanged(self):
        words = " ".join(["word"] * 150)
        result = _enforce_word_limit(words, max_words=150)
        assert result == words
        assert not result.endswith("...")

    def test_over_limit_truncated(self):
        words = " ".join(["word"] * 160)
        result = _enforce_word_limit(words, max_words=150)
        assert result.endswith("...")
        actual_words = result[:-3].split()
        assert len(actual_words) == 150

    def test_truncation_at_word_boundary(self):
        text = " ".join(f"w{i}" for i in range(200))
        result = _enforce_word_limit(text, max_words=150)
        # Should be exactly 150 words before "..."
        parts = result[:-3].split()
        assert len(parts) == 150

    def test_one_word_over_limit(self):
        words = " ".join(["word"] * 151)
        result = _enforce_word_limit(words, max_words=150)
        assert result.endswith("...")
        assert len(result[:-3].split()) == 150

    def test_max_words_param_respected(self):
        words = " ".join(["word"] * 20)
        result = _enforce_word_limit(words, max_words=10)
        assert result.endswith("...")
        assert len(result[:-3].split()) == 10


# ---------------------------------------------------------------------------
# Em-dash replacement
# ---------------------------------------------------------------------------


class TestReplaceEmDashes:
    def test_replaces_unicode_em_dash(self):
        text = "Hey there\u2014Gregory here."
        result = _replace_em_dashes(text)
        assert "\u2014" not in result
        assert " -- " in result

    def test_replaces_html_entity(self):
        text = "Follow up&mdash;properly."
        result = _replace_em_dashes(text)
        assert "&mdash;" not in result
        assert " -- " in result

    def test_no_em_dash_unchanged(self):
        text = "This is a normal sentence -- already using double hyphens."
        assert _replace_em_dashes(text) == text

    def test_multiple_em_dashes_replaced(self):
        text = "A\u2014B\u2014C"
        result = _replace_em_dashes(text)
        assert result == "A -- B -- C"


# ---------------------------------------------------------------------------
# Forbidden content detection
# ---------------------------------------------------------------------------


class TestCheckForbiddenContent:
    def test_calendly_detected(self):
        result = _check_forbidden_content("Book via calendly.com")
        assert "Calendly" in result

    def test_dollar_sign_detected(self):
        result = _check_forbidden_content("Only $500/day")
        assert "$" in result

    def test_percent_detected(self):
        result = _check_forbidden_content("Save 20%")
        assert "%" in result

    def test_word_percent_detected(self):
        result = _check_forbidden_content("Save twenty percent today")
        assert "percent" in result

    def test_cost_detected(self):
        result = _check_forbidden_content("No hidden cost here")
        assert "cost" in result

    def test_price_detected(self):
        result = _check_forbidden_content("Ask about price")
        assert "price" in result

    def test_fee_detected(self):
        result = _check_forbidden_content("A small fee applies")
        assert "fee" in result

    def test_ai_tools_detected(self):
        result = _check_forbidden_content("We use AI tools to find leads")
        assert "AI tools" in result

    def test_ai_powered_detected(self):
        result = _check_forbidden_content("Our AI-powered platform")
        assert "AI-powered" in result

    def test_clean_text_returns_empty_list(self):
        clean = "Hey there -- Gregory here, founder of Exotiq AI."
        result = _check_forbidden_content(clean)
        assert result == []

    def test_case_insensitive(self):
        result = _check_forbidden_content("CALENDLY is blocked")
        assert "Calendly" in result


# ---------------------------------------------------------------------------
# DO NOT SAY list generation
# ---------------------------------------------------------------------------


class TestBuildDoNotSay:
    def test_always_includes_base_items(self):
        lead = _make_lead()
        items = _build_do_not_say(lead)
        assert "competitor names" in items
        assert "pricing" in items
        assert "Calendly links" in items

    def test_call_only_adds_phone_note(self):
        lead = _make_lead(notes="Please call only, no DM")
        items = _build_do_not_say(lead)
        assert "direct outreach -- use phone" in items

    def test_no_dm_in_notes_adds_phone_note(self):
        lead = _make_lead(notes="no dm preference")
        items = _build_do_not_say(lead)
        assert "direct outreach -- use phone" in items

    def test_score_5_adds_automated_tools(self):
        lead = _make_lead(scoring_score=5)
        items = _build_do_not_say(lead)
        assert "automated outreach tools" in items

    def test_score_4_does_not_add_automated_tools(self):
        lead = _make_lead(scoring_score=4)
        items = _build_do_not_say(lead)
        assert "automated outreach tools" not in items

    def test_no_notes_no_extra_items(self):
        lead = _make_lead(notes=None, scoring_score=3)
        items = _build_do_not_say(lead)
        assert len(items) == 3

    def test_notes_case_insensitive_call_only(self):
        lead = _make_lead(notes="CALL ONLY please")
        items = _build_do_not_say(lead)
        assert "direct outreach -- use phone" in items


# ---------------------------------------------------------------------------
# draft_dm integration (all DB calls mocked)
# ---------------------------------------------------------------------------


def _make_mock_cursor(lastrowid: int = 42) -> MagicMock:
    """Return a mock cursor with a lastrowid."""
    cursor = MagicMock()
    cursor.lastrowid = lastrowid
    return cursor


def _patch_db(lastrowid: int = 42):
    """Context manager that patches get_db to return a mock connection."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value = _make_mock_cursor(lastrowid)
    mock_conn.__enter__ = lambda s: s
    mock_conn.__exit__ = MagicMock(return_value=False)
    return patch("skills.dm_drafting.get_db", return_value=mock_conn)


class TestDraftDm:
    """Integration tests for draft_dm() with all external I/O mocked."""

    def _run_draft(
        self,
        lead: dict,
        draft_id: int = 42,
    ) -> tuple[dict, MagicMock, MagicMock, MagicMock]:
        """
        Run draft_dm with all DB/utility functions patched.

        Returns:
            Tuple of (result_dict, mock_get_lead, mock_update_lead, mock_log_activity)
        """
        with (
            patch("skills.dm_drafting.get_lead", return_value=lead) as mock_get,
            patch("skills.dm_drafting.update_lead", return_value=True) as mock_update,
            patch("skills.dm_drafting.log_activity", return_value=1) as mock_log,
            _patch_db(lastrowid=draft_id),
        ):
            result = draft_dm(lead["id"])
            return result, mock_get, mock_update, mock_log

    # -- Result shape --

    def test_returns_required_keys(self):
        lead = _make_lead(scoring_score=3, company_ig_handle="@apexrentals")
        result, *_ = self._run_draft(lead)
        assert set(result.keys()) == {"lead_id", "template_used", "dm_text", "word_count", "draft_id"}

    def test_lead_id_in_result(self):
        lead = _make_lead(lead_id="lead_mia_001", scoring_score=3)
        result, *_ = self._run_draft(lead)
        assert result["lead_id"] == "lead_mia_001"

    def test_draft_id_from_insert(self):
        lead = _make_lead(scoring_score=3)
        result, *_ = self._run_draft(lead, draft_id=99)
        assert result["draft_id"] == 99

    def test_word_count_correct(self):
        lead = _make_lead(scoring_score=3)
        result, *_ = self._run_draft(lead)
        assert result["word_count"] == len(result["dm_text"].split())

    # -- Template selection in draft_dm --

    def test_score_3_uses_d(self):
        lead = _make_lead(scoring_score=3)
        result, *_ = self._run_draft(lead)
        assert result["template_used"] == "D"

    def test_score_5_no_vehicles_uses_b(self):
        lead = _make_lead(scoring_score=5, fleet_vehicle_types=None)
        result, *_ = self._run_draft(lead)
        assert result["template_used"] == "B"

    def test_score_3_with_vehicles_uses_e(self):
        lead = _make_lead(
            scoring_score=3,
            fleet_vehicle_types='["Ferrari 488"]',
        )
        result, *_ = self._run_draft(lead)
        assert result["template_used"] == "E"

    def test_failed_outreach_uses_f(self):
        lead = _make_lead(scoring_score=5, outreach_status="failed")
        result, *_ = self._run_draft(lead)
        assert result["template_used"] == "F"

    def test_none_score_uses_d(self):
        lead = _make_lead(scoring_score=None)
        result, *_ = self._run_draft(lead)
        assert result["template_used"] == "D"

    # -- Word count enforcement in draft_dm --

    def test_long_dm_is_truncated(self):
        """A template that would produce >150 words should be truncated."""
        # We build a lead where market is a very long string to force overflow
        long_market = " ".join(["VeryLongMarketName"] * 60)
        lead = _make_lead(scoring_score=3, market=long_market)
        result, *_ = self._run_draft(lead)
        assert result["word_count"] <= _MAX_WORDS
        if result["word_count"] == _MAX_WORDS:
            assert result["dm_text"].endswith("...")

    # -- Em-dash cleanup in draft_dm --

    def test_em_dash_not_in_output(self):
        lead = _make_lead(scoring_score=3)
        result, *_ = self._run_draft(lead)
        assert "\u2014" not in result["dm_text"]

    # -- Forbidden content guard --

    def test_raises_on_forbidden_content_in_template(self):
        """Patch _build_dm_text to inject a forbidden phrase, expect ValueError."""
        lead = _make_lead(scoring_score=3)
        with (
            patch("skills.dm_drafting.get_lead", return_value=lead),
            patch("skills.dm_drafting.update_lead", return_value=True),
            patch("skills.dm_drafting.log_activity", return_value=1),
            patch("skills.dm_drafting._build_dm_text", return_value="Book via Calendly now"),
            _patch_db(),
        ):
            with pytest.raises(ValueError, match="forbidden content"):
                draft_dm(lead["id"])

    def test_raises_when_lead_not_found(self):
        with patch("skills.dm_drafting.get_lead", return_value=None):
            with pytest.raises(ValueError, match="Lead not found"):
                draft_dm("lead_nonexistent")

    # -- Side-effect verification --

    def test_update_lead_called_with_correct_fields(self):
        lead = _make_lead(lead_id="lead_upd_001", scoring_score=4)
        result, _, mock_update, _ = self._run_draft(lead)

        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args[0][0] == "lead_upd_001"
        fields = call_args[0][1]
        assert fields["outreach_dm_draft"] == result["dm_text"]
        assert fields["outreach_template_used"] == result["template_used"]
        assert fields["outreach_client_review"] == "Y"
        assert fields["outreach_approval_status"] == "PENDING"

    def test_log_activity_called_with_dm_draft_type(self):
        lead = _make_lead(lead_id="lead_log_001", scoring_score=3)
        _, _, _, mock_log = self._run_draft(lead)

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        assert call_kwargs[1].get("type") == "dm_draft" or call_kwargs[0][0] == "dm_draft"

    def test_log_activity_agent_is_dm_drafting(self):
        lead = _make_lead(lead_id="lead_log_002", scoring_score=3)
        _, _, _, mock_log = self._run_draft(lead)

        # Check keyword arg or positional
        kwargs = mock_log.call_args[1]
        assert kwargs.get("agent") == "dm_drafting"

    def test_no_calendly_in_dm_text(self):
        lead = _make_lead(scoring_score=5)
        result, *_ = self._run_draft(lead)
        assert "calendly" not in result["dm_text"].lower()

    def test_no_pricing_in_dm_text(self):
        lead = _make_lead(scoring_score=4)
        result, *_ = self._run_draft(lead)
        dm_lower = result["dm_text"].lower()
        for word in ("$", "price", "cost", "fee"):
            assert word not in dm_lower

    # -- DO NOT SAY stored to dm_drafts --

    def test_do_not_say_stored_as_json(self):
        lead = _make_lead(scoring_score=3)
        mock_conn = MagicMock()
        mock_conn.execute.return_value = _make_mock_cursor(7)

        with (
            patch("skills.dm_drafting.get_lead", return_value=lead),
            patch("skills.dm_drafting.update_lead", return_value=True),
            patch("skills.dm_drafting.log_activity", return_value=1),
            patch("skills.dm_drafting.get_db", return_value=mock_conn),
        ):
            draft_dm(lead["id"])

        # Verify the do_not_say arg passed to the INSERT is valid JSON
        insert_call = mock_conn.execute.call_args_list[0]
        do_not_say_arg = insert_call[0][1][3]  # 4th bind param
        parsed = json.loads(do_not_say_arg)
        assert isinstance(parsed, list)
        assert "competitor names" in parsed
        assert "pricing" in parsed
        assert "Calendly links" in parsed

    # -- Market variable in DM --

    def test_market_appears_in_dm(self):
        lead = _make_lead(scoring_score=3, market="Las Vegas")
        result, *_ = self._run_draft(lead)
        assert "Las Vegas" in result["dm_text"]

    def test_none_market_falls_back(self):
        lead = _make_lead(scoring_score=3, market=None)
        result, *_ = self._run_draft(lead)
        assert "your market" in result["dm_text"]
